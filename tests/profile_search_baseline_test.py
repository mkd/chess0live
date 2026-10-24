#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Exercise bounded comparison integrity with explicitly synthetic UCI results."""
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import sys
import tempfile
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

    def __init__(self, path):
        self.path = path
        self.transcript = []
        self.commands = []
        self.closed = False
        self.depth = 2
        self.instances.append(self)

    def __enter__(self): return self
    def __exit__(self, *args): self.closed = True
    def send(self, command):
        self.commands.append(command)
        if command.startswith('go depth '): self.depth = int(command.split()[-1])

    def until(self, prefix, timeout=30):
        if prefix == 'uciok':
            result = ['option name ' + name + ' type ' + p.OPTION_TYPES[name] + ' default test' for name in (*p.OPTIONS, 'EvalFile')] + ['uciok']
        elif prefix == 'readyok': result = ['readyok']
        else:
            result = reply(self.depth, 21 if self.fail_candidate and self.path.name == 'candidate' else 20)
            if self.mutate_candidate and self.path.name == 'candidate':
                self.path.write_bytes(b'changed')
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

    def run_profile(self, **kwargs):
        with ExitStack() as stack:
            for name, value in [('Engine', FakeEngine), ('load_positions', lambda: self.positions),
                                ('source_paths', lambda: {}), ('CORPUS', self.network),
                                ('NETWORK_SHA256', p.digest(self.network)),
                                ('resource_check', lambda *a: dict(active_search_workers=1, resident_engines=2))]:
                stack.enter_context(patch.object(p, name, value))
            return p.profile(self.baseline, self.candidate, self.root/'output', network=self.network,
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
        for engine in FakeEngine.instances:
            self.assertEqual(engine.commands.count('ucinewgame'),1)
            self.assertEqual(engine.commands.count('go depth 2'),2)
            self.assertIn('setoption name Late Move Reductions value true',engine.commands)

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
