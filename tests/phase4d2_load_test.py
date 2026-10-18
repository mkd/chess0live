#!/usr/bin/env python3
"""Check operational admission, clock measurement and failure refusal without engines.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import check_phase4d2_load as load


def output(move='e2e4',tb=0):
    return ['info depth 1 seldepth 1 score cp 0 nodes 1 time 1 nps 1000 hashfull 0 tbhits 0 pv '+move,
            'info nodes 1 time 1 nps 1000 hashfull 0 tbhits '+str(tb),'bestmove '+move]


def events(scenario,elapsed=100,stop=None):
    result=[{'direction':'to_engine','line':scenario['go'],'monotonic_ns':1000000000}]
    if stop is not None:result.append({'direction':'to_engine','line':'stop','monotonic_ns':1000000000+stop*1000000})
    result.append({'direction':'from_engine','line':'bestmove e2e4','monotonic_ns':1000000000+elapsed*1000000})
    return result


class LoadTests(unittest.TestCase):
    def test_clock_receipt_checks_deadline(self):
        scenario=load.SCENARIOS[1]
        self.assertTrue(load.measure(events(scenario,250),output(),'startpos',scenario)['on_time'])
        self.assertFalse(load.measure(events(scenario,251),output(),'startpos',scenario)['on_time'])

    def test_cancellation_checks_stop_latency(self):
        scenario=load.SCENARIOS[2]
        self.assertTrue(load.measure(events(scenario,1100,100),output(),'startpos',scenario)['on_time'])
        self.assertFalse(load.measure(events(scenario,1101,100),output(),'startpos',scenario)['on_time'])
        with self.assertRaises(ValueError):load.measure(events(scenario,50,100),output(),'startpos',scenario)

    def test_timestamp_identity_and_duplicates_rejected(self):
        scenario=load.SCENARIOS[0]
        for broken in (events(scenario)[:1], events(scenario)+events(scenario)[-1:]):
            with self.subTest(broken=broken),self.assertRaises(ValueError):load.measure(broken,output(),'startpos',scenario)
        wrong=events(scenario);wrong[-1]['line']='bestmove d2d4'
        with self.assertRaises(ValueError):load.measure(wrong,output(),'startpos',scenario)

    def test_illegal_pv_and_tablebase_activity_rejected(self):
        scenario=load.SCENARIOS[0]
        with self.assertRaises(ValueError):load.measure(events(scenario),output('e2e5'),'startpos',scenario)
        with self.assertRaisesRegex(ValueError,'tablebase'):load.measure(events(scenario),output(tb=1),'startpos',scenario)

    def test_aggregate_resource_admission(self):
        policy={'max_cpu_workers':8,'memory_fraction':.5}
        with patch.object(load,'current_budget',return_value=policy),patch.object(load,'physical_memory',return_value=64*1024**3):
            result=load.admission(98511183)
            self.assertEqual(result['resident_engines'],16)
            self.assertEqual(result['active_search_workers'],8)
            self.assertGreater(result['estimated_memory_bytes'],8*1024**3)

    def test_insufficient_workers_memory_or_unknown_memory_rejected(self):
        for workers,memory in ((7,64*1024**3),(8,1024**3),(8,None)):
            with self.subTest(workers=workers,memory=memory),patch.object(load,'current_budget',return_value={'max_cpu_workers':workers,'memory_fraction':.5}),patch.object(load,'physical_memory',return_value=memory),self.assertRaises(ValueError):load.admission(98511183)

    def test_existing_output_refused_before_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'evidence.json';path.write_text('preserve')
            with patch.object(load,'RecordedEngine') as engine,self.assertRaises(ValueError):load.run('missing','missing',path)
            engine.assert_not_called();self.assertEqual(path.read_text(),'preserve')

    def test_wrong_binary_refused_before_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            binary=Path(directory)/'binary';network=Path(directory)/'network'
            binary.write_bytes(b'not frozen');network.write_bytes(b'not frozen')
            with patch.object(load,'RecordedEngine') as engine,self.assertRaisesRegex(ValueError,'frozen'):load.run(binary,network,Path(directory)/'output.json')
            engine.assert_not_called()


if __name__=='__main__':unittest.main()
