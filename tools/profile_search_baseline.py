#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Compare exact search work under one explicit preset on exposed cold/warm roots.

Use tools/run.py to prepare the pinned chess referee automatically. This small
screen is for result-preserving implementation changes: every completed
iteration must agree. Elapsed-time ratios are observations, never Elo evidence.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import time

from bench import digest
from compare_bench import reject_errors, resource_check, run_order, search_signature
from profile_cache import board_for
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'tests/data/countermove-profile.json'
NETWORK = ROOT / 'networks/nn-1a298aa575a0.nnue'
NETWORK_SHA256 = '1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2'
OPTIONS = {
    'Threads': '1', 'Hash': '64', 'Time Policy': 'classic', 'Ponder': 'false',
    'Move Overhead': '20', 'Late Move Reductions': 'true',
    'Deep Quiet Reductions': 'false', 'Capture Ordering': 'mvv-lva',
    'Countermove Ordering': 'false', 'Null Move Pruning': 'false',
    'Reverse Futility Pruning': 'false', 'QSearch SEE Pruning': 'false',
    'ProbCut': 'false', 'SyzygyPath': '<empty>', 'SyzygyProbeLimit': '0',
    'Search Diagnostics': 'false',
}
PRESETS = ('default', 'see-ordering', 'all-on')
OPTION_TYPES = {name: ('spin' if name in ('Threads', 'Hash', 'Move Overhead', 'SyzygyProbeLimit')
                      else 'combo' if name in ('Time Policy', 'Capture Ordering')
                      else 'string' if name == 'SyzygyPath' else 'check') for name in OPTIONS}
OPTION_TYPES['EvalFile'] = 'string'
TOOL_SOURCES = ('tools/profile_search_baseline.py', 'tests/profile_search_baseline_test.py',
                'tools/bench.py', 'tools/compare_bench.py', 'tools/profile_cache.py',
                'tools/profile_search.py', 'tools/resources.py', 'tools/uci_client.py',
                'requirements-match.txt', 'networks/manifest.json')


def publish(path, report):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def remaining(deadline, maximum):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError('Total search baseline deadline expired')
    return min(value, maximum)


def load_positions():
    """Use all existing exposed roots; never select roots from their results."""
    document = json.loads(CORPUS.read_text(encoding='utf-8'))
    positions = document.get('positions') if isinstance(document, dict) else None
    if not isinstance(positions, list) or len(positions) != 15:
        raise ValueError('Expected all fifteen exposed development roots')
    ids = set()
    for item in positions:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id']
                or item['id'] in ids or not isinstance(item.get('position'), str)):
            raise ValueError('Each development root needs a unique ID and UCI position')
        ids.add(item['id'])
        board_for(item['position'])
    return positions


def source_paths():
    paths = {name: ROOT / name for name in TOOL_SOURCES}
    # Capture the candidate's actual local implementation, even when uncommitted.
    for base in ('src', 'include', 'third_party/fathom/src'):
        for path in sorted((ROOT / base).rglob('*')):
            if path.is_file() and path.suffix in ('.cpp', '.hpp', '.c', '.h'):
                paths[str(path.relative_to(ROOT))] = path
    paths['Makefile'] = ROOT / 'Makefile'
    return paths


def options_for(preset='default'):
    """Return independent per-run settings; never mutate the accepted defaults."""
    if preset not in PRESETS:
        raise ValueError('Unknown search preset: ' + str(preset))
    options = dict(OPTIONS)
    if preset in ('see-ordering', 'all-on'):
        options['Capture Ordering'] = 'see'
    if preset == 'all-on':
        for name in ('Deep Quiet Reductions', 'Countermove Ordering', 'Null Move Pruning',
                     'Reverse Futility Pruning', 'QSearch SEE Pruning', 'ProbCut'):
            options[name] = 'true'
    return options


def prepare(engine, network, deadline, preset='default'):
    options = dict(options_for(preset), EvalFile=str(network))
    engine.send('uci')
    identity = engine.until('uciok', timeout=remaining(deadline, 20))
    reject_errors(identity)
    for name in options:
        declarations = [line for line in identity if line.startswith('option name ' + name + ' type ')]
        if (len(declarations) != 1
                or declarations[0].split(' type ', 1)[1].split()[0] != OPTION_TYPES[name]):
            raise ValueError('Missing/duplicate/wrong-type required UCI option: ' + name)
    commands = ['setoption name ' + name + ' value ' + value for name, value in options.items()] + ['isready']
    for command in commands:
        engine.send(command)
    output = engine.until('readyok', timeout=remaining(deadline, 30))
    reject_errors(output)
    if any(line.startswith('bestmove') for line in output):
        raise ValueError('Unexpected search result during setup')
    return dict(identity=identity, commands=commands, output=output)


def validate_result(lines, board, depth):
    """Check every exact iteration and independently replay all reported moves."""
    if not lines or not lines[-1].startswith('bestmove '):
        raise ValueError('Search must finish with exactly one bestmove')
    if any(line.startswith('info string ') for line in lines):
        raise ValueError('Unexpected diagnostics in uninstrumented search')
    signature = search_signature(lines, depth)
    times = []
    previous_nodes = 0
    for row, line in zip(signature['iterations'], [line for line in lines if line.startswith('info depth ')]):
        if row['nodes'] < previous_nodes or row['seldepth'] < 0:
            raise ValueError('Invalid cumulative nodes or selective depth')
        previous_nodes = row['nodes']
        probe = board.copy()
        for move in row['pv']:
            probe.push_uci(move)
        tokens = line.split()
        for field in ('time', 'nps', 'hashfull', 'tbhits'):
            if tokens.count(field) != 1:
                raise ValueError('Missing/duplicate UCI search field: ' + field)
            value = tokens[tokens.index(field) + 1]
            if not value.isascii() or not value.isdecimal():
                raise ValueError('Invalid unsigned UCI search field: ' + field)
            number = int(value)
            if (field == 'hashfull' and number > 1000) or (field == 'tbhits' and number != 0):
                raise ValueError('Unexpected tablebase hit or invalid hash occupancy')
            if field == 'time':
                times.append(number)
        if len(times) > 1 and times[-1] < times[-2]:
            raise ValueError('Engine iteration time moved backwards')
    after = board.copy()
    after.push_uci(signature['bestmove'])
    if signature['ponder']:
        after.push_uci(signature['ponder'])
    return dict(signature=signature, engine_elapsed_ms=times[-1], iteration_times_ms=times)


def summarize(samples, positions, repetitions):
    """Require the complete paired matrix and identical deterministic work."""
    lookup = {}
    for sample in samples:
        key = (sample['repetition'], sample['position_index'], sample['role'], sample['temperature'])
        if key in lookup or sample.get('status') != 'complete':
            raise ValueError('Duplicate or incomplete baseline observation')
        lookup[key] = sample
    expected = {(r, i, role, temperature) for r in range(repetitions) for i in range(len(positions))
                for role in ('baseline', 'candidate') for temperature in ('cold', 'warm')}
    if set(lookup) != expected:
        raise ValueError('Incomplete search comparison matrix')
    pairs = []
    for temperature in ('cold', 'warm'):
        for i, position in enumerate(positions):
            first = None
            for r in range(repetitions):
                a, b = [lookup[r, i, role, temperature] for role in ('baseline', 'candidate')]
                if a['result']['signature'] != b['result']['signature']:
                    raise ValueError('Search signature mismatch: ' + position['id'] + ' ' + temperature)
                signature = a['result']['signature']
                if first is not None and signature != first:
                    raise ValueError('Repeated search was not deterministic: ' + position['id'])
                first = signature
                times = [sample['elapsed_seconds'] for sample in (a, b)]
                if any(not math.isfinite(t) or t <= 0 for t in times):
                    raise ValueError('Invalid elapsed measurement')
                pairs.append(dict(position_id=position['id'], repetition=r, temperature=temperature,
                                  nodes=signature['iterations'][-1]['nodes'], baseline_seconds=times[0],
                                  candidate_seconds=times[1], speed_ratio=times[0] / times[1]))
    groups = {}
    for temperature in ('cold', 'warm'):
        selected = [pair for pair in pairs if pair['temperature'] == temperature]
        ratios = [pair['speed_ratio'] for pair in selected]
        baseline = sum(pair['baseline_seconds'] for pair in selected)
        candidate = sum(pair['candidate_seconds'] for pair in selected)
        groups[temperature] = dict(pairs=len(selected), nodes=sum(pair['nodes'] for pair in selected),
                                   baseline_seconds=baseline, candidate_seconds=candidate,
                                   aggregate_speed_ratio=baseline / candidate,
                                   median_paired_speed_ratio=statistics.median(ratios),
                                   geometric_mean_speed_ratio=math.exp(statistics.mean(math.log(r) for r in ratios)),
                                   minimum_paired_speed_ratio=min(ratios), maximum_paired_speed_ratio=max(ratios))
    return dict(exact_search_parity=True, groups=groups, pairs=pairs,
                ratio_definition='baseline wall seconds / candidate wall seconds; above one is faster here',
                interpretation='Finite exposed workload, no Elo, significance interval or universal speed claim')


def profile(baseline, candidate, output, *, network=NETWORK, depth=6, repetitions=2,
            search_timeout=10., total_timeout=240., quiet_host=False, preset='default'):
    if not quiet_host:
        raise ValueError('Declare --quiet-host after stopping other compute/build workloads')
    options = options_for(preset)
    if type(depth) is not int or not 1 <= depth <= 8 or type(repetitions) is not int or not 1 <= repetitions <= 3:
        raise ValueError('Use depth1..8 and repetitions1..3')
    for value, maximum in ((search_timeout, 30), (total_timeout, 300)):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError('Invalid bounded profile deadline')
    baseline, candidate, network, output = [Path(p).resolve() for p in (baseline, candidate, network, output)]
    if any(any(ord(c) < 32 for c in str(path)) for path in (baseline, candidate, network, output)):
        raise ValueError('Paths must fit on one UCI line')
    if output.exists():
        raise ValueError('Output already exists; choose a fresh result directory')
    positions = load_positions()
    boards = [board_for(position['position']) for position in positions]
    assets = dict(source_paths(), baseline=baseline, candidate=candidate, network=network, corpus=CORPUS)
    frozen = {name: dict(path=str(path), sha256=digest(path)) for name, path in assets.items()}
    if frozen['network']['sha256'] != NETWORK_SHA256:
        raise ValueError('Use the pinned network for this comparison')
    initial_policy = resource_check(network, 64)
    report = dict(schema_version=1, status='running', started_utc=datetime.now(timezone.utc).isoformat(),
                  assets=frozen, positions=positions, platform=platform.platform(), machine=platform.machine(),
                  git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  git_status=subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
                  settings=dict(preset=preset, options=dict(options, EvalFile=str(network)), depth=depth, repetitions=repetitions,
                                search_timeout_seconds=search_timeout, total_timeout_seconds=total_timeout),
                  quiet_host_declared=True, initial_resource_policy=initial_policy,
                  setup={}, pids={}, samples=[], timing='One active worker, two resident engines; cold/warm pair then alternate AB/BA; no extra warmup; readiness outside measurement')
    output.mkdir(parents=True, exist_ok=False)
    target = output / 'report.json'
    publish(target, report)
    deadline = time.monotonic() + total_timeout
    engines = {}
    try:
        with ExitStack() as stack:
            for role, path in (('baseline', baseline), ('candidate', candidate)):
                engines[role] = stack.enter_context(Engine(path))
                report['pids'][role] = engines[role].process.pid
            for role, engine in engines.items():
                report['setup'][role] = prepare(engine, network, deadline, preset)
            for repetition in range(repetitions):
                for index, (position, board) in enumerate(zip(positions, boards)):
                    for role in run_order(repetition, index):
                        engine = engines[role]
                        for temperature in ('cold', 'warm'):
                            sample = dict(repetition=repetition, position_index=index, position_id=position['id'],
                                          role=role, temperature=temperature, status='preparing',
                                          resource_policy=resource_check(network, 64))
                            report['samples'].append(sample)
                            commands = (['ucinewgame'] if temperature == 'cold' else []) + [
                                'position ' + position['position'], 'isready']
                            sample['preparation_commands'] = commands
                            for command in commands:
                                engine.send(command)
                            sample['preparation_output'] = engine.until('readyok', timeout=remaining(deadline, 15))
                            if sample['preparation_output'] != ['readyok']:
                                raise ValueError('Unexpected output at readiness barrier')
                            sample.update(status='searching', go='go depth ' + str(depth))
                            begin = len(engine.transcript)
                            wall_start, monotonic_start = time.time_ns(), time.monotonic_ns()
                            try:
                                engine.send(sample['go'])
                                lines = engine.until('bestmove ', timeout=remaining(deadline, search_timeout))
                                elapsed = (time.monotonic_ns() - monotonic_start) / 1e9
                                wall_elapsed = (time.time_ns() - wall_start) / 1e9
                                sample.update(output=lines, elapsed_seconds=elapsed, wall_elapsed_seconds=wall_elapsed)
                                if abs(wall_elapsed - elapsed) > .5:
                                    raise ValueError('Host suspension or wall-clock discontinuity invalidated timing')
                                sample['result'] = validate_result(lines, board, depth)
                                # Readiness is outside timing. Fence every result,
                                # including the final one, against stray output.
                                sample['post_search_commands'] = ['isready']
                                engine.send('isready')
                                sample['post_search_output'] = engine.until('readyok', timeout=remaining(deadline, 15))
                                if sample['post_search_output'] != ['readyok']:
                                    raise ValueError('Unexpected output after completed search')
                                sample['status'] = 'complete'
                            finally:
                                sample.setdefault('output', engine.transcript[begin:])
                                sample['received_transcript'] = engine.transcript[begin:]
                                publish(target, report)
            report['summary'] = summarize(report['samples'], positions, repetitions)
        report['exit_codes'] = {role: engine.process.poll() for role, engine in engines.items()}
        if any(code != 0 for code in report['exit_codes'].values()):
            raise ValueError('An engine did not exit successfully')
        report['after_sha256'] = {name: digest(path) for name, path in assets.items()}
        if any(report['after_sha256'][name] != frozen[name]['sha256'] for name in assets):
            raise ValueError('A binary, input or implementation changed during the comparison')
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        report['exit_codes'] = {role: engine.process.poll() for role, engine in engines.items()}
        report['received_transcripts'] = {role: list(engine.transcript) for role, engine in engines.items()}
        if 'after_sha256' not in report:
            report['after_sha256'] = {}
            for name, path in assets.items():
                try:
                    report['after_sha256'][name] = digest(path)
                except OSError as error:
                    report['after_sha256'][name] = None
                    report.setdefault('after_hash_errors', {})[name] = str(error)
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        publish(target, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'candidate', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--network', type=Path, default=NETWORK)
    parser.add_argument('--depth', type=int, default=6)
    parser.add_argument('--repetitions', type=int, default=2)
    parser.add_argument('--search-timeout', type=float, default=10)
    parser.add_argument('--total-timeout', type=float, default=240)
    parser.add_argument('--quiet-host', action='store_true')
    parser.add_argument('--preset', choices=PRESETS, default='default',
                        help='Identical explicit search settings for both builds; default preserves accepted settings')
    args = parser.parse_args(argv)
    try:
        report = profile(args.baseline, args.candidate, args.output, network=args.network, depth=args.depth,
                         repetitions=args.repetitions, search_timeout=args.search_timeout,
                         total_timeout=args.total_timeout, quiet_host=args.quiet_host, preset=args.preset)
        print(json.dumps(report['summary'], indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, TimeoutError) as error:
        parser.exit(1, 'Search baseline failed: ' + str(error) + '\n')
    except KeyboardInterrupt:
        parser.exit(130, 'Interrupted; partial evidence retained.\n')


if __name__ == '__main__':
    main()
