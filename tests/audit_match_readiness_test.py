#!/usr/bin/env python3
"""Engine-free raw evidence and corruption checks for the finite readiness audit.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import audit_match_readiness as audit
import chess
import chess.pgn


def policy(aggregate=False):
    return {'local_time': '2026-10-20T15:00:00+03:00', 'source': 'daytime',
            'timezone': 'Europe/Helsinki', 'percent': 50, 'logical_cpus': 18,
            'max_cpu_workers': 9, 'memory_fraction': .5,
            'active_search_workers': 4 if aggregate else 1, 'resident_engines': 8 if aggregate else 2,
            'physical_memory_bytes': 64*1024**3,
            'estimated_memory_bytes': 6*1024**3 if aggregate else 1200*1024**2}


class RawGameTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='chess0live-readiness-audit-')
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        audit.inputs.clear(); audit.search_windows.clear()
        self.pair = {'pair_id': 'p000001', 'opening_id': 'synthetic', 'opening_key': 'synthetic',
                     'starting_fen': chess.STARTING_FEN, 'moves': []}
        self.run = {'engines': {role: {'network': '/synthetic.nnue',
                                     'experiment_options': audit.ROLE_OPTIONS[role]}
                                for role in ('candidate', 'opponent')}}
        self.events, stamp = [], 0
        def event(direction, role, line):
            nonlocal stamp
            stamp += 1_000_000
            self.events.append({'monotonic_ns': stamp, 'engine': role, 'direction': direction, 'line': line})
            return stamp
        engines = {}
        for role in self.run['engines']:
            options = {'Hash': 64, 'Threads': 1, 'Move Overhead': 20, 'Search Diagnostics': False,
                       'EvalFile': '/synthetic.nnue', 'SyzygyPath': '', 'Ponder': False}
            options.update({name: value == 'true' if value in ('true', 'false') else
                            int(value) if name == 'SyzygyProbeLimit' else value
                            for name, value in audit.ROLE_OPTIONS[role].items()})
            engines[role] = {'options': options, 'ponder': False, 'pid': 9999999}
            for name, value in options.items():
                event('to_engine', role, f'setoption name {name} value {str(value).lower() if isinstance(value, bool) else value}')
            event('to_engine', role, 'ucinewgame')
        board, pgn = chess.Board(), chess.pgn.Game()
        node, clocks, moves = pgn, {'white': 3., 'black': 3.}, []
        for token in ('f2f3', 'e7e5', 'g2g4', 'd8h4'):
            color = 'white' if board.turn else 'black'
            role = 'candidate' if board.turn else 'opponent'
            history = ' '.join(m.uci() for m in board.move_stack)
            event('to_engine', role, 'position startpos'+(' moves '+history if history else ''))
            begin = event('to_engine', role, f'go wtime {round(clocks["white"]*1000)} btime {round(clocks["black"]*1000)} winc 50 binc 50')
            event('from_engine', role, f'info depth 1 score cp 0 nodes 1 time 1 pv {token}')
            end = event('from_engine', role, 'bestmove '+token)
            elapsed = (end-begin)/1e9
            row = {'color': color, 'engine': role, 'ply': board.ply()+1, 'move': token,
                   'clock_before': clocks[color], 'elapsed_seconds': elapsed, 'played': True}
            clocks[color] += .05-elapsed; row['clock_after'] = clocks[color]; moves.append(row)
            board.push_uci(token); node = node.add_variation(board.peek()); node.set_clock(clocks[color])
        pgn.headers.update(Result='0-1', Termination='checkmate')
        (self.folder/'game.pgn').write_text(str(pgn)+'\n')
        self.record = {'game_id': 'p000001-1', 'pair_id': 'p000001', 'opening_id': 'synthetic',
                       'opening_key': 'synthetic', 'candidate_color': 'white', 'engines': engines,
                       'resource_policy': policy(), 'moves': moves, 'played_plies': 4, 'opening_plies': 0,
                       'final_fen': board.fen(), 'clocks': clocks, 'pgn': 'game.pgn',
                       'protocol_log': 'game.protocol.jsonl', 'status': 'complete', 'termination': 'checkmate',
                       'result': '0-1', 'candidate_score': 0.}

    def replay(self):
        (self.folder/'game.protocol.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in self.events))
        return audit.audit_game(self.folder, self.run, self.record, self.pair)

    def test_complete_legal_raw_game(self):
        result = self.replay()
        self.assertEqual((result['searches'], result['pv_lines'], result['legal_plies']), (4, 4, 4))

    def test_corrupt_move(self):
        self.record['moves'][0]['move'] = 'e2e5'
        with self.assertRaises(ValueError): self.replay()

    def test_corrupt_receipt(self):
        next(e for e in self.events if e['line'].startswith('bestmove '))['monotonic_ns'] += 100
        with self.assertRaisesRegex(ValueError, 'Receipt clock'): self.replay()

    def test_illegal_pv(self):
        next(e for e in self.events if ' pv ' in e['line'])['line'] = 'info depth 1 pv e2e5'
        with self.assertRaises(ValueError): self.replay()

    def test_wrong_increment(self):
        event = next(e for e in self.events if e['line'].startswith('go '))
        event['line'] = event['line'].replace('winc 50', 'winc 51')
        with self.assertRaisesRegex(ValueError, 'Increment differs'): self.replay()

    def test_experimental_option_changed(self):
        event = next(e for e in self.events if 'name Null Move Pruning' in e['line'])
        event['line'] = event['line'].replace('false', 'true')
        with self.assertRaisesRegex(ValueError, 'options differ'): self.replay()

    def test_unsolicited_bestmove(self):
        self.events[-1]['line'] = 'bestmove d8h4 ponder a1a8'
        with self.assertRaises(ValueError): self.replay()

    def test_missing_reply(self):
        self.events.pop()
        with self.assertRaisesRegex(ValueError, 'Missing final search'): self.replay()

    def test_wrong_pgn_result(self):
        path = self.folder/'game.pgn'; path.write_text(path.read_text().replace('[Result "0-1"]', '[Result "1-0"]'))
        with self.assertRaises(ValueError): self.replay()


class LimitsTests(unittest.TestCase):
    def windows(self, count=4):
        return [{'shard': f'shard-{i}', 'start_ns': i, 'end_ns': 20+i} for i in range(count)]

    def test_four_way_overlap(self):
        result = audit.overlap(self.windows())
        self.assertEqual(result, {'peak_active_searches': 4, 'four_active_duration_ns': 17})

    def test_three_way_insufficient(self):
        with self.assertRaises(ValueError): audit.overlap(self.windows(3))

    def test_five_way_excess(self):
        with self.assertRaises(ValueError): audit.overlap(self.windows(5))

    def test_same_shard_overlap(self):
        windows = self.windows(); windows[-1]['shard'] = 'shard-0'
        with self.assertRaises(ValueError): audit.overlap(windows)

    def test_touching_intervals_not_concurrent(self):
        with self.assertRaises(ValueError):
            audit.overlap([{'shard': f'shard-{i}', 'start_ns': i*10, 'end_ns': (i+1)*10} for i in range(4)])

    def test_resources(self):
        audit.resource_policy(policy()); audit.resource_policy(policy(True), aggregate=True)

    def test_unknown_memory_rejected(self):
        value = policy(); value['physical_memory_bytes'] = None
        with self.assertRaises(ValueError): audit.resource_policy(value)

    def test_aggregate_memory_rejected(self):
        value = policy(True); value['physical_memory_bytes'] = 8*1024**3
        with self.assertRaises(ValueError): audit.resource_policy(value, aggregate=True)

    def test_bad_evidence_saved_as_failure(self):
        with tempfile.TemporaryDirectory() as path, patch.object(audit, 'ROOT', Path(path)):
            result = audit.audit(path)
        self.assertFalse(result['operational_acceptance']); self.assertTrue(result['errors'])

    def test_cli_never_overwrites_report(self):
        with tempfile.TemporaryDirectory() as path:
            report = Path(path)/'report.json'; report.write_text('preserve')
            with self.assertRaises(FileExistsError): audit.main(['--campaign', path, '--output', str(report)])
            self.assertEqual(report.read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
