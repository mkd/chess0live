#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Exercise bounded comparison integrity with explicitly synthetic UCI results."""
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import profile_search_baseline as p


def reply(depth=2, nodes=20):
    return [f'info depth {d} seldepth {d+1} score cp 10 nodes {nodes*d} time {d} nps 1000 hashfull 0 tbhits 0 pv g1h3 g8h6'
            for d in range(1, depth+1)] + ['bestmove g1h3 ponder g8h6']


class FakeEngine:
    instances = []
    fail_candidate = False
    mutate_candidate = False
    bad_exit = False
    stray_after_search = False
    partial_timeout = False

    def __init__(self, path):
        self.path = path
        self.transcript = []
        self.commands = []
        self.closed = False
        self.depth = 2
        self.after_search = False
        self.process = SimpleNamespace(pid=1000 + len(self.instances), poll=lambda:
            (7 if self.bad_exit and self.path.name == 'candidate' else 0) if self.closed else None)
        self.instances.append(self)

    def __enter__(self): return self
    def __exit__(self, *args): self.closed = True
    def send(self, command):
        self.commands.append(command)
        if command.startswith('go depth '): self.depth = int(command.split()[-1])

    def until(self, prefix, timeout=30):
        if prefix == 'uciok':
            result = ['option name ' + name + ' type ' + p.OPTION_TYPES[name] + ' default test' for name in (*p.OPTIONS, 'EvalFile')] + ['uciok']
        elif prefix == 'readyok':
            result = (['bestmove g1h3', 'readyok'] if self.after_search and self.stray_after_search else ['readyok'])
            self.after_search = False
        else:
            result = reply(self.depth, 21 if self.fail_candidate and self.path.name == 'candidate' else 20)
            if self.partial_timeout and self.path.name == 'candidate':
                self.transcript.extend(result[:1])
                raise TimeoutError('synthetic partial search timeout')
            if self.mutate_candidate and self.path.name == 'candidate':
                self.path.write_bytes(b'changed')
            self.after_search = True
        self.transcript.extend(result)
        return result


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.baseline, self.candidate, self.network = [self.root/name for name in ('baseline', 'candidate', 'network')]
        for file in (self.baseline, self.candidate, self.network): file.write_bytes(b'test artifact')
        self.positions = [dict(id='opening-01', position='startpos')]
        FakeEngine.instances = []
        FakeEngine.fail_candidate = FakeEngine.mutate_candidate = False
        FakeEngine.bad_exit = FakeEngine.stray_after_search = FakeEngine.partial_timeout = False

    def run_profile(self, output_name='output', **kwargs):
        with ExitStack() as stack:
            for name, value in [('Engine', FakeEngine), ('load_positions', lambda: self.positions),
                                ('source_paths', lambda: {}), ('CORPUS', self.network),
                                ('NETWORK_SHA256', p.digest(self.network)),
                                ('resource_check', lambda *a: dict(active_search_workers=1, resident_engines=2))]:
                stack.enter_context(patch.object(p, name, value))
            return p.profile(self.baseline, self.candidate, self.root/output_name, network=self.network,
                             depth=2, repetitions=1, quiet_host=True, **kwargs)

    def sample(self, role, temperature, repetition=0):
        return dict(repetition=repetition, position_index=0, role=role, temperature=temperature,
                    status='complete', elapsed_seconds=.002, result=p.validate_result(reply(), p.board_for('startpos'), 2))

    def samples(self, repetitions=1):
        return [self.sample(role,temp,r) for r in range(repetitions) for role in ('baseline','candidate') for temp in ('cold','warm')]

    def test_complete_real_exposed_corpus(self):
        positions=p.load_positions(); self.assertEqual(len(positions),15)
        self.assertEqual(positions[0]['position'],'startpos')

    def test_corpus_rejects_missing_duplicate_or_invalid_root(self):
        data=json.loads(p.CORPUS.read_text()); file=self.root/'corpus.json'
        for mutate in (lambda d:d['positions'].pop(), lambda d:d['positions'].__setitem__(1,d['positions'][0]),
                       lambda d:d['positions'][0].update(position='startpos moves e2e5')):
            bad=copy.deepcopy(data);mutate(bad);file.write_text(json.dumps(bad))
            with patch.object(p,'CORPUS',file),self.assertRaises(ValueError):p.load_positions()

    def test_current_options_explicit(self):
        self.assertEqual(p.OPTIONS['Late Move Reductions'],'true')
        for name in ('ProbCut','Null Move Pruning','Deep Quiet Reductions','Countermove Ordering','Reverse Futility Pruning','QSearch SEE Pruning','Ponder','Search Diagnostics'):
            self.assertEqual(p.OPTIONS[name],'false')
        self.assertEqual(p.OPTIONS['Threads'],'1');self.assertEqual(p.OPTIONS['SyzygyProbeLimit'],'0')

    def test_presets_are_exact_and_independent(self):
        original = dict(p.OPTIONS)
        self.assertEqual(p.options_for(), original)
        self.assertEqual(p.options_for('see-ordering'), dict(original, **{'Capture Ordering':'see'}))
        changes = {'Capture Ordering':'see', **{name:'true' for name in (
            'Deep Quiet Reductions','Countermove Ordering','Null Move Pruning',
            'Reverse Futility Pruning','QSearch SEE Pruning','ProbCut')}}
        self.assertEqual(p.options_for('all-on'), dict(original, **changes))
        for preset in p.PRESETS:
            changed = p.options_for(preset)
            changed['Threads'] = '99'
        self.assertEqual(p.OPTIONS, original)
        self.assertEqual(p.options_for(), original)

    def test_unknown_preset_rejected_before_launch(self):
        with self.assertRaisesRegex(ValueError, 'Unknown search preset'):
            self.run_profile(preset='some-options')
        self.assertEqual(FakeEngine.instances, [])
        self.assertFalse((self.root/'output').exists())

    def test_each_preset_applied_to_both_builds_without_leaking(self):
        for preset in ('see-ordering','all-on','default'):
            FakeEngine.instances = []
            report = self.run_profile(output_name=preset, preset=preset)
            options = dict(p.options_for(preset), EvalFile=str(self.network.resolve()))
            self.assertEqual(report['settings']['preset'], preset)
            self.assertEqual(report['settings']['options'], options)
            commands = ['setoption name '+name+' value '+value for name,value in options.items()]
            for engine in FakeEngine.instances:
                self.assertEqual([c for c in engine.commands if c.startswith('setoption ')], commands)

    def test_cli_forwards_explicit_preset(self):
        with patch.object(p,'profile',return_value={'summary':{}}) as call, redirect_stdout(io.StringIO()):
            self.assertEqual(p.main(['--baseline',str(self.baseline),'--candidate',str(self.candidate),
                                    '--output',str(self.root/'output'),'--quiet-host','--preset','all-on']),0)
        self.assertEqual(call.call_args.kwargs['preset'],'all-on')

    def test_exact_iterations_and_legal_pvs(self):
        value=p.validate_result(reply(),p.board_for('startpos'),2)
        self.assertEqual(value['engine_elapsed_ms'],2)
        self.assertEqual(value['signature']['iterations'][-1]['nodes'],40)

    def test_illegal_pv_bestmove_and_ponder_rejected(self):
        for old,new in [('pv g1h3 g8h6','pv g1h3 e2e4'),('bestmove g1h3','bestmove e2e5'),('ponder g8h6','ponder e2e4')]:
            with self.subTest(new=new),self.assertRaises(ValueError):p.validate_result([line.replace(old,new) for line in reply()],p.board_for('startpos'),2)

    def test_unfinished_bound_score_and_diagnostics_rejected(self):
        for lines in (reply()[:-1], [line.replace('score cp 10','score cp 10 lowerbound') for line in reply()],
                      ['info string unexpected']+reply(),reply()+['info nodes 40']):
            with self.assertRaises(ValueError):p.validate_result(lines,p.board_for('startpos'),2)

    def test_invalid_time_hash_hits_and_nodes_rejected(self):
        for old,new in [('time 2','time -2'),('time 2','time 0'),('hashfull 0','hashfull 1001'),
                        ('tbhits 0','tbhits 1'),('nodes 40','nodes 19'),('time 2','time 2 time 2')]:
            with self.subTest(new=new),self.assertRaises(ValueError):p.validate_result([line.replace(old,new) for line in reply()],p.board_for('startpos'),2)

    def test_summary_complete_matrix(self):
        result=p.summarize(self.samples(),self.positions,1)
        self.assertTrue(result['exact_search_parity']);self.assertEqual(result['groups']['cold']['aggregate_speed_ratio'],1)

    def test_summary_refuses_missing_duplicate_incomplete(self):
        for samples in (self.samples()[:-1],self.samples()+self.samples()[:1]):
            with self.assertRaises(ValueError):p.summarize(samples,self.positions,1)
        samples=self.samples();samples[0]['status']='searching'
        with self.assertRaises(ValueError):p.summarize(samples,self.positions,1)

    def test_signature_difference_never_becomes_speed_claim(self):
        for key in ('nodes','seldepth','score','pv'):
            samples=self.samples();row=samples[2]['result']['signature']['iterations'][0]
            row[key]={'nodes':99,'seldepth':99,'score':{'unit':'cp','value':11},'pv':['e2e4']}[key]
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'signature mismatch'):p.summarize(samples,self.positions,1)

    def test_repetition_nondeterminism_refused(self):
        samples=self.samples(2)
        for sample in samples:
            if sample['repetition']==1 and sample['temperature']=='cold':sample['result']['signature']['iterations'][0]['nodes']=21
        with self.assertRaisesRegex(ValueError,'not deterministic'):p.summarize(samples,self.positions,2)

    def test_invalid_timing_refused(self):
        for value in (0,-1,float('nan'),float('inf')):
            samples=self.samples();samples[0]['elapsed_seconds']=value
            with self.assertRaises(ValueError):p.summarize(samples,self.positions,1)

    def test_alternating_role_order(self):
        self.assertEqual(p.run_order(0,0),('baseline','candidate'));self.assertEqual(p.run_order(1,0),('candidate','baseline'))

    def test_real_orchestration_success_with_synthetic_engines(self):
        result=self.run_profile();self.assertEqual(result['status'],'passed');self.assertEqual(len(result['samples']),4)
        self.assertTrue(all(engine.closed for engine in FakeEngine.instances))
        self.assertEqual(result['exit_codes'],{'baseline':0,'candidate':0})
        self.assertEqual(len(set(result['pids'].values())),2)
        self.assertEqual(result['received_transcripts'],dict(zip(('baseline','candidate'),[e.transcript for e in FakeEngine.instances])))
        for sample in result['samples']:
            self.assertEqual(sample['post_search_commands'],['isready'])
            self.assertEqual(sample['post_search_output'],['readyok'])
            self.assertEqual(sample['received_transcript'],sample['output']+['readyok'])
        for engine in FakeEngine.instances:
            self.assertEqual(engine.commands.count('ucinewgame'),1)
            self.assertEqual(engine.commands.count('go depth 2'),2)
            self.assertIn('setoption name Late Move Reductions value true',engine.commands)

    def test_nonzero_exit_retained_as_failure(self):
        FakeEngine.bad_exit = True
        with self.assertRaisesRegex(ValueError,'exit successfully'):self.run_profile()
        report=json.loads((self.root/'output/report.json').read_text())
        self.assertEqual(report['status'],'failed')
        self.assertEqual(report['exit_codes'],{'baseline':0,'candidate':7})
        self.assertEqual(len(report['samples']),4)
        self.assertTrue(all(e.closed for e in FakeEngine.instances))

    def test_post_search_stray_output_retained_as_failure(self):
        FakeEngine.stray_after_search = True
        with self.assertRaisesRegex(ValueError,'after completed search'):self.run_profile()
        report=json.loads((self.root/'output/report.json').read_text())
        self.assertEqual(report['status'],'failed')
        sample=report['samples'][0]
        self.assertNotEqual(sample['status'],'complete')
        self.assertEqual(sample['post_search_output'],['bestmove g1h3','readyok'])
        self.assertEqual(sample['received_transcript'],sample['output']+sample['post_search_output'])
        self.assertTrue(all(e.closed for e in FakeEngine.instances))

    def test_partial_search_timeout_retains_evidence_and_exits(self):
        FakeEngine.partial_timeout = True
        with self.assertRaisesRegex(TimeoutError,'partial search'):self.run_profile()
        report=json.loads((self.root/'output/report.json').read_text())
        self.assertEqual(report['status'],'failed')
        sample=report['samples'][-1]
        self.assertEqual(sample['role'],'candidate')
        self.assertEqual(sample['output'],reply()[:1])
        self.assertEqual(sample['received_transcript'],reply()[:1])
        self.assertEqual(report['exit_codes'],{'baseline':0,'candidate':0})
        self.assertTrue(all(e.closed for e in FakeEngine.instances))

    def test_failed_parity_preserves_raw_report_and_cleans_children(self):
        FakeEngine.fail_candidate=True
        with self.assertRaisesRegex(ValueError,'signature mismatch'):self.run_profile()
        saved=json.loads((self.root/'output/report.json').read_text());self.assertEqual(saved['status'],'failed')
        self.assertEqual(len(saved['samples']),4);self.assertTrue(all(e.closed for e in FakeEngine.instances))

    def test_artifact_drift_refused(self):
        FakeEngine.mutate_candidate=True
        with self.assertRaisesRegex(ValueError,'changed during'):self.run_profile()
        self.assertEqual(json.loads((self.root/'output/report.json').read_text())['status'],'failed')

    def test_existing_output_never_overwritten(self):
        (self.root/'output').mkdir();(self.root/'output/keep').write_text('owner')
        with self.assertRaisesRegex(ValueError,'already exists'):self.run_profile()
        self.assertEqual((self.root/'output/keep').read_text(),'owner')

    def test_require_quiet_host_and_bounded_limits(self):
        with self.assertRaisesRegex(ValueError,'quiet-host'):p.profile(self.baseline,self.candidate,self.root/'out')
        for args in ({'depth':9},{'depth':True},{'repetitions':0},{'repetitions':4},{'search_timeout':31},{'total_timeout':301}):
            with self.assertRaises(ValueError):p.profile(self.baseline,self.candidate,self.root/'out',quiet_host=True,**args)

    def test_missing_duplicate_and_wrong_type_options_refused(self):
        engine=FakeEngine(self.baseline)
        identity=engine.until('uciok')
        for lines in (identity[1:],identity+[identity[0]],
                      [line.replace('Threads type spin','Threads type check') for line in identity]):
            with patch.object(engine,'until',return_value=lines),self.assertRaises(ValueError):
                p.prepare(engine,self.network,p.time.monotonic()+10)

    def test_unexpected_setup_reply_refused(self):
        engine=FakeEngine(self.baseline);identity=engine.until('uciok')
        for reply_lines in (['info string error: invalid option','readyok'],['bestmove g1h3','readyok']):
            with patch.object(engine,'until',side_effect=[identity,reply_lines]),self.assertRaises(ValueError):
                p.prepare(engine,self.network,p.time.monotonic()+10)

    def test_total_deadline_is_shared(self):
        with patch.object(p.time,'monotonic',return_value=9):self.assertEqual(p.remaining(10,30),1)
        with patch.object(p.time,'monotonic',return_value=10),self.assertRaises(TimeoutError):p.remaining(10,30)


if __name__=='__main__':unittest.main()
