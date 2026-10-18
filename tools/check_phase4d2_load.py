#!/usr/bin/env python3
"""One bounded eight-worker operational check on already exposed benchmark roots.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Frozen before the first search: 16 resident engines in eight on/off pairs,
Threads=1, Hash=64, classic timing, overhead=20, all unrelated experiments off.
Four waves of eight concurrent requests: 1000+100 ms clock; 250+25 ms clock;
infinite interrupted after 100 ms; 1000+100 ms reuse after cancellation.
The first, third and fourth waves use pair member slot%2; the second uses
the opposite member. The fourth wave reuses all canceled engine instances.
Each wave contains four LMR-on and four LMR-off engines. There are no games,
holdout inputs, tuning, repetitions, result-dependent retries or Elo inference.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import queue
import subprocess
import threading
import time

from bench import POSITIONS, digest
from compare_bench import physical_memory
from profile_search import reject_errors
from profile_smp import board_for, validate_result
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
ENGINE_SHA256 = 'bda061408f4ff8339e2fc8f7d3536525373e8a790f7209a35418162928168f7f'
NETWORK_SHA256 = '1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2'
SCENARIOS = (
    {'id': 'clock-1000', 'go': 'go wtime 1000 btime 1000 winc 100 binc 100', 'clock_ms': 1000},
    {'id': 'clock-250', 'go': 'go wtime 250 btime 250 winc 25 binc 25', 'clock_ms': 250},
    {'id': 'cancel', 'go': 'go infinite', 'stop_after_ms': 100, 'stop_limit_ms': 1000},
    {'id': 'reuse', 'go': 'go wtime 1000 btime 1000 winc 100 binc 100', 'clock_ms': 1000},
)
SOURCES = ('tools/check_phase4d2_load.py', 'tests/phase4d2_load_test.py', 'tools/bench.py',
           'tools/profile_smp.py', 'tools/profile_search.py', 'tools/compare_bench.py',
           'tools/resources.py', 'tools/uci_client.py', 'requirements-match.txt')


class RecordedEngine(Engine):
    """Timestamp line receipt before queuing; retain stderr separately."""
    def __init__(self, path):
        self.events, self.errors = [], []
        self.process = subprocess.Popen([str(path)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        self.lines, self.transcript = queue.Queue(), []
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.error_reader = threading.Thread(target=self._read_errors, daemon=True)
        self.reader.start(); self.error_reader.start()

    def send(self, command):
        self.events.append({'direction': 'to_engine', 'line': command, 'monotonic_ns': time.monotonic_ns()})
        super().send(command)

    def _read(self):
        for raw in self.process.stdout:
            line = raw.rstrip('\r\n')
            self.events.append({'direction': 'from_engine', 'line': line, 'monotonic_ns': time.monotonic_ns()})
            self.lines.put(line)
        self.lines.put(None)

    def _read_errors(self):
        for raw in self.process.stderr:
            self.errors.append({'line': raw.rstrip('\r\n'), 'monotonic_ns': time.monotonic_ns()})

    def close(self):
        super().close()
        self.error_reader.join(timeout=1)
        self.process.stderr.close()


def admission(network_bytes):
    policy = dict(current_budget())
    reservation = 8 * (2*64*1024**2 + 8*network_bytes + 256*1024**2)
    memory = physical_memory()
    policy.update(active_search_workers=8, resident_engines=16,
                  estimated_memory_bytes=reservation, physical_memory_bytes=memory,
                  memory_estimate_is_hard_cap=False)
    if policy['max_cpu_workers'] < 8 or not memory or reservation > memory*policy['memory_fraction']:
        raise ValueError('Eight-worker reservation exceeds current resource budget')
    return policy


def measure(events, lines, position, scenario):
    result = validate_result(lines, board_for(position), 'movetime', None)
    go = [e for e in events if e['direction'] == 'to_engine' and e['line'] == scenario['go']]
    best = [e for e in events if e['direction'] == 'from_engine' and e['line'].startswith('bestmove ')]
    if len(go) != 1 or len(best) != 1 or best[0]['line'] != lines[-1] or best[0]['monotonic_ns'] < go[0]['monotonic_ns']:
        raise ValueError('Missing, repeated, mismatched or reversed request/reply timestamps')
    elapsed = (best[0]['monotonic_ns'] - go[0]['monotonic_ns']) / 1e6
    result.update(go_ns=go[0]['monotonic_ns'], bestmove_ns=best[0]['monotonic_ns'], reader_elapsed_ms=elapsed)
    if 'clock_ms' in scenario:
        result['on_time'] = elapsed <= scenario['clock_ms']
    else:
        stop = [e for e in events if e['direction'] == 'to_engine' and e['line'] == 'stop']
        if len(stop) != 1 or best[0]['monotonic_ns'] < stop[0]['monotonic_ns']:
            raise ValueError('Infinite search completed before stop or lacks its stop receipt')
        result['stop_latency_ms'] = (best[0]['monotonic_ns'] - stop[0]['monotonic_ns']) / 1e6
        result['on_time'] = result['stop_latency_ms'] <= scenario['stop_limit_ms']
    if result['final_aggregate'].get('tbhits') != 0:
        raise ValueError('Unexpected tablebase activity')
    return result


def run(binary, network, output):
    binary, network, output = map(lambda p: Path(p).resolve(), (binary, network, output))
    raw = output.parent / 'load-protocol'
    if output.exists() or raw.exists():
        raise ValueError('Output already exists; preserve the single attempt')
    if digest(binary) != ENGINE_SHA256 or digest(network) != NETWORK_SHA256:
        raise ValueError('Unexpected frozen executable or network')
    policy = admission(network.stat().st_size)
    paths = {name: ROOT/name for name in SOURCES}
    paths.update(engine=binary, network=network)
    pins = {name: {'path': str(path), 'sha256': digest(path)} for name,path in paths.items()}
    boards = [board_for(position) for position in POSITIONS]
    if len(boards) != 3:
        raise ValueError('Expected three exposed benchmark roots')
    output.parent.mkdir(parents=True, exist_ok=True); raw.mkdir()
    report = {'schema_version': 1, 'status': 'running', 'started_utc': datetime.now(timezone.utc).isoformat(),
              'purpose': 'Bounded exposed operational check; no strength inference or held-out searches',
              'scenarios': SCENARIOS, 'positions': POSITIONS, 'assets': pins,
              'admissions': [policy], 'samples': [], 'engines': []}
    start = time.monotonic(); engines = []
    def remaining():
        left = 115 - (time.monotonic() - start)
        if left <= 0: raise TimeoutError('Bounded load check exceeded 115 seconds before cleanup')
        return min(10, left)
    try:
        for slot in range(16):
            remaining()
            engine = RecordedEngine(binary); engines.append(engine)
            engine.send('uci'); identity = engine.until('uciok', timeout=remaining()); reject_errors(identity)
            options = {'Hash': '64', 'Threads': '1', 'EvalFile': str(network), 'Move Overhead': '20',
                       'Ponder': 'false', 'Time Policy': 'classic', 'Capture Ordering': 'mvv-lva',
                       'Search Diagnostics': 'false', 'Countermove Ordering': 'false',
                       'SyzygyPath': '<empty>', 'SyzygyProbeLimit': '0',
                       'Late Move Reductions': str(bool(slot % 2)).lower()}
            for name,value in options.items():
                if not any(line.startswith('option name '+name+' type ') for line in identity):
                    raise ValueError('Missing required option '+name)
                engine.send('setoption name '+name+' value '+value)
            engine.send('isready'); reject_errors(engine.until('readyok', timeout=remaining()))
            report['engines'].append({'slot': slot, 'pid': engine.process.pid, 'options': options})
        for wave, scenario in enumerate(SCENARIOS):
            report['admissions'].append(admission(network.stat().st_size))
            barrier = threading.Barrier(9, timeout=remaining())
            selected = [(slot*2 + ((slot + wave % 2) % 2)) for slot in range(8)]
            # Reuse the canceled members in the last wave rather than changing roles.
            if scenario['id'] == 'reuse': selected = [slot*2 + slot%2 for slot in range(8)]
            for slot,index in enumerate(selected):
                engine = engines[index]
                if wave == 0 or wave == 1:
                    engine.send('ucinewgame')
                engine.send('position '+POSITIONS[slot % 3]); engine.send('isready')
                reject_errors(engine.until('readyok', timeout=remaining()))
            def request(slot):
                index = selected[slot]; engine = engines[index]
                offset = len(engine.events)
                barrier.wait(); engine.send(scenario['go'])
                if 'stop_after_ms' in scenario:
                    time.sleep(scenario['stop_after_ms']/1000); engine.send('stop')
                lines = engine.until('bestmove ', timeout=remaining())
                engine.send('isready'); ready = engine.until('readyok', timeout=remaining())
                if ready != ['readyok']: raise ValueError('Unsolicited output after bestmove')
                events = engine.events[offset:]
                result = measure(events, lines, POSITIONS[slot%3], scenario)
                if engine.errors: raise ValueError('Unexpected stderr')
                return {'wave': wave, 'scenario': scenario['id'], 'worker': slot, 'engine_slot': index,
                        'lmr': bool(index%2), 'position_index': slot%3, 'output': lines, 'result': result}
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = [pool.submit(request,slot) for slot in range(8)]
                barrier.wait()
                failures = []
                for future in futures:
                    try: report['samples'].append(future.result())
                    except BaseException as error: failures.append(repr(error))
                if failures: raise RuntimeError('Wave errors: '+ '; '.join(failures))
            wave_samples = report['samples'][-8:]
            if sum(sample['lmr'] for sample in wave_samples) != 4: raise ValueError('Unbalanced LMR roles')
            # All eight request/reply intervals must overlap, proving exercised load.
            overlap = min(sample['result']['bestmove_ns'] for sample in wave_samples) - max(sample['result']['go_ns'] for sample in wave_samples)
            report.setdefault('wave_overlap_ms', []).append(overlap/1e6)
            if overlap <= 0: raise ValueError('Eight concurrent search intervals did not overlap')
            if not all(sample['result']['on_time'] for sample in wave_samples): raise ValueError('Clock or cancellation deadline failed')
        if any(digest(path) != pins[name]['sha256'] for name,path in paths.items()):
            raise ValueError('Input drift during operational check')
        report['status'] = 'PASS'
    except BaseException as error:
        report.update(status='FAIL', error=repr(error))
    finally:
        for engine in engines:
            try: engine.close()
            except BaseException as error: report.update(status='FAIL', cleanup_error=repr(error))
        report['all_processes_closed'] = all(engine.process.poll() is not None for engine in engines)
        report['stderr_lines'] = sum(len(engine.errors) for engine in engines)
        if not report['all_processes_closed'] or report['stderr_lines']: report['status'] = 'FAIL'
        report['elapsed_seconds'] = time.monotonic() - start
        if report['elapsed_seconds'] > 120: report.update(status='FAIL', bound_error='Exceeded 120-second attempt bound')
        for index,engine in enumerate(engines):
            with (raw/('engine-%02d.json'%index)).open('x') as stream:
                json.dump({'pid':engine.process.pid,'events':engine.events,'stderr':engine.errors},stream,indent=2)
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        with output.open('x') as stream: json.dump(report,stream,indent=2)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine',type=Path,required=True); parser.add_argument('--network',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); result=run(args.engine,args.network,args.output)
    print(json.dumps({key:result[key] for key in ('status','elapsed_seconds','all_processes_closed','stderr_lines')},indent=2))
    raise SystemExit(0 if result['status']=='PASS' else 1)


if __name__ == '__main__': main()
