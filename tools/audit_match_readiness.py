"""Independent four-worker match-readiness replay; no engine execution.

Adapted from the original Phase 3K raw-evidence auditor. This is a finite
operational gate, not a strength or general reliability qualification.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
import math
import os
import random
from pathlib import Path
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import chess
import chess.pgn

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"initial": 3.0, "increment": .05, "threads": 1, "hash_mb": 64,
            "move_overhead_ms": 20, "max_plies": 1024, "smoke": True,
            "startup_timeout": 30., "protocol_timeout": 5.}
EXPECTED_ENGINE_SHA = "eaf26b5f13e9de38cc8e5b8da06dc582ff935ca7c01e27e0dc7a6451146a77b9"
EXPECTED_NETWORK_SHA = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
inputs = {}
search_windows, bestmove_receipts, protocol_events = [], [], {}

def raw(path):
    path = Path(path)
    data = path.read_bytes()
    inputs[str(path.resolve())] = hashlib.sha256(data).hexdigest()
    return data

def read(path, lines=False):
    data = raw(path)
    return [json.loads(line) for line in data.splitlines()] if lines else json.loads(data)

def check(condition, message):
    if not condition:
        raise ValueError(message)

def near(a, b, message, tolerance=1e-8):
    check(math.isfinite(a) and math.isfinite(b) and abs(a-b) <= tolerance, message)

def position(command):
    words = command.split()
    check(words[:1] == ["position"], "Missing position prefix")
    check(words[1] in ("startpos", "fen"), "Unexpected position form")
    board = chess.Board() if words[1] == "startpos" else chess.Board(" ".join(words[2:8]))
    if "moves" in words:
        for token in words[words.index("moves")+1:]:
            board.push_uci(token)
    return board

def audit_game(folder, run, record, pair):
    for field in ('pgn', 'protocol_log'):
        check((folder/record[field]).resolve().is_relative_to(folder.resolve()), 'Game evidence escapes its folder')
    check(record["pair_id"] == pair["pair_id"], "Pair identifier differs")
    check(set(record["engines"]) == {"candidate", "opponent"}, "Game roles differ")
    for role, actual in record["engines"].items():
        expected = {"Hash": 64, "Threads": 1, "Move Overhead": 20,
                    "Search Diagnostics": False, "EvalFile": run["engines"][role]["network"],
                    "Time Policy": "classic", "Capture Ordering": "mvv-lva",
                    "Late Move Reductions": role == "candidate",
                    "Countermove Ordering": False, "Null Move Pruning": False,
                    "Reverse Futility Pruning": False, "QSearch SEE Pruning": False,
                    "SyzygyPath": "", "SyzygyProbeLimit": 0}
        check(all(actual["options"].get(key) == value for key, value in expected.items()),
              "Recorded actual engine settings differ")
        check(actual["ponder"] is False, "Ponder enabled")
    resource_policy(record["resource_policy"])
    check(record["opening_id"] == pair["opening_id"] and record["opening_key"] == pair["opening_key"], "Opening identity differs")
    board = chess.Board(pair["starting_fen"])
    for token in pair["moves"]:
        board.push_uci(token)
    clocks = {"white": 3., "black": 3.}
    contexts, played = [], []
    for move_event in record["moves"]:
        color = "white" if board.turn else "black"
        role = "candidate" if color == record["candidate_color"] else "opponent"
        check(move_event["color"] == color and move_event["engine"] == role and move_event["ply"] == board.ply()+1, "Move identity differs")
        near(move_event["clock_before"], clocks[color], "Clock continuity differs")
        contexts.append((board.copy(stack=True), dict(clocks), move_event))
        if "played" not in move_event:
            check(move_event is record["moves"][-1] and record["status"] != "complete", "Unfinished move in completed game")
            continue
        move = chess.Move.from_uci(move_event["move"])
        check(move in board.legal_moves, "Illegal journal move")
        elapsed = move_event["elapsed_seconds"]
        check(math.isfinite(elapsed) and elapsed >= 0, "Invalid elapsed duration")
        remaining = clocks[color] - elapsed
        if move_event["played"]:
            check(remaining >= 0, "Late move credited")
            clocks[color] = remaining + .05
            board.push(move)
            played.append(move.uci())
        else:
            check(remaining < 0 and record["termination"] == "time_forfeit", "Unplayed move not flagfall")
            clocks[color] = remaining
        near(move_event["clock_after"], clocks[color], "Increment/clock differs")
    check(record["played_plies"] == len(played) and record["opening_plies"] == len(pair["moves"]), "Ply counts differ")
    check(record["final_fen"] == board.fen(), "Final FEN differs")
    for color in clocks:
        near(record["clocks"][color], clocks[color], "Final clock differs")
    stream = io.StringIO(raw(folder / record["pgn"]).decode())
    pgn = chess.pgn.read_game(stream)
    check(chess.pgn.read_game(stream) is None, "Extra PGN game")
    check(pgn is not None and not pgn.errors, "PGN invalid")
    check(pgn.board().fen() == pair["starting_fen"], "PGN starting board differs")
    check([m.uci() for m in pgn.mainline_moves()] == pair["moves"] + played, "PGN history differs")
    check(pgn.end().board().fen() == board.fen(), "PGN final board differs")
    check(pgn.headers["Result"] == record["result"] and pgn.headers["Termination"] == record["termination"], "PGN outcome differs")
    for node, event in zip(list(pgn.mainline())[len(pair["moves"]):], [e for e in record["moves"] if e.get("played")]):
        near(node.clock(), event["clock_after"], "PGN clock differs", .000501)
    if record["status"] == "complete" and record["termination"] != "time_forfeit":
        outcome = board.outcome(claim_draw=True)
        check(outcome is not None and outcome.result() == record["result"] and outcome.termination.name.lower() == record["termination"], "Terminal result/claim differs")
    elif record["status"] == "complete":
        winner = not board.turn
        expected = "1/2-1/2" if board.has_insufficient_material(winner) else "1-0" if winner else "0-1"
        check(record["result"] == expected, "Flagfall result differs")
    else:
        check(record["result"] == "*" and record["candidate_score"] is None, "Incomplete game scored")
    if record["status"] == "complete":
        white_score = {"1-0": 1., "1/2-1/2": .5, "0-1": 0.}[record["result"]]
        check(record["candidate_score"] == (white_score if record["candidate_color"] == "white" else 1-white_score), "Candidate score differs")
    events = read(folder / record["protocol_log"], lines=True)
    protocol_events[f"{folder.name}/{record['protocol_log']}"] = events
    state = {role: {"options": {}, "board": None, "newgame": False} for role in ("candidate", "opponent")}
    active, previous, searches, pv_lines, pv_plies, ponders = None, -1, 0, 0, 0, 0
    for event in events:
        stamp, role, line = event["monotonic_ns"], event["engine"], event["line"]
        check(isinstance(stamp, int) and stamp >= previous, "Transcript order went backward")
        previous = stamp
        current = state[role]
        if event["direction"] == "to_engine":
            if line.startswith("setoption name ") and " value " in line:
                name, value = line[15:].split(" value ", 1)
                current["options"][name] = value
            elif line == "ucinewgame":
                current["newgame"] = True
            elif line.startswith("position "):
                current["board"] = position(line)
            elif line.startswith("go "):
                check(active is None and current["newgame"], "Overlapping/missing-newgame search")
                check(searches < len(contexts), "Extra search")
                expected_board, expected_clocks, move_event = contexts[searches]
                check(role == move_event["engine"], "Wrong searching role")
                actual_board = current["board"]
                check(actual_board.root().fen() == expected_board.root().fen() and actual_board.move_stack == expected_board.move_stack, "Search history differs")
                expected_options = {"Hash": "64", "Threads": "1", "Move Overhead": "20", "Search Diagnostics": "false", "EvalFile": run["engines"][role]["network"], "Ponder": "false", "Time Policy": "classic", "Capture Ordering": "mvv-lva", "Late Move Reductions": "true" if role == "candidate" else "false",
                                    "Countermove Ordering": "false", "Null Move Pruning": "false",
                                    "Reverse Futility Pruning": "false", "QSearch SEE Pruning": "false",
                                    "SyzygyPath": "", "SyzygyProbeLimit": "0"}
                check(all(current["options"].get(key) == value for key, value in expected_options.items()), "Actual common options differ")
                for name, value in run["engines"][role]["experiment_options"].items():
                    check(current["options"].get(name) == value, "Experimental options differ")
                words = line.split()
                check(len(words) == 9 and set(words[1::2]) == {"wtime", "btime", "winc", "binc"}, "Clock command shape differs")
                limits = {key: int(value) for key, value in zip(words[1::2], words[2::2])}
                for color, key in (("white", "wtime"), ("black", "btime")):
                    near(limits[key]/1000, expected_clocks[color], "Transmitted clock differs", .00101)
                check(limits["winc"] == limits["binc"] == 50, "Increment differs")
                active = (role, stamp, searches)
                searches += 1
        else:
            check(event["direction"] == "from_engine", "Unexpected stderr/direction")
            check("error:" not in line.lower(), "Protocol error recorded")
            option = re.match(r"option name (.+?) type (?:spin|check|combo|string) default (.*)", line)
            if option:
                value = re.split(r" (?:min|max|var) ", option[2], maxsplit=1)[0]
                current["options"][option[1]] = "" if option[1] == "SyzygyPath" and value == "<empty>" else value
            if line.startswith("info ") and not line.startswith("info string ") and " pv " in line:
                check(active is not None and active[0] == role, "PV outside active search")
                pv = current["board"].copy(stack=True)
                for token in line.split(" pv ", 1)[1].split():
                    pv.push_uci(token)
                    pv_plies += 1
                pv_lines += 1
            if line.startswith("bestmove "):
                check(active is not None and active[0] == role, "Unsolicited bestmove")
                move_event = contexts[active[2]][2]
                tokens = line.split()
                check(len(tokens) == 2 or (len(tokens) == 4 and tokens[2] == "ponder"), "Malformed bestmove")
                check(tokens[1] == move_event["move"], "Bestmove differs")
                near((stamp-active[1])/1e9, move_event["elapsed_seconds"], "Receipt clock differs")
                search_windows.append({"shard": folder.name, "start_ns": active[1], "end_ns": stamp})
                bestmove_receipts.append({"shard": folder.name, "stamp_ns": stamp})
                if "ponder" in tokens:
                    reply = current["board"].copy(stack=True)
                    reply.push_uci(tokens[1]); reply.push_uci(tokens[tokens.index("ponder")+1]); ponders += 1
                active = None
    check(active is None and searches == len(contexts), "Missing final search boundary")
    return {"game_id": record["game_id"], "status": record["status"], "termination": record["termination"], "result": record["result"], "legal_plies": len(pair["moves"])+len(played), "searches": searches, "pv_lines": pv_lines, "pv_plies": pv_plies, "ponders": ponders, "minimum_clock_slack_ms": min(((e["clock_before"]-e["elapsed_seconds"])*1000 for e in record["moves"] if "elapsed_seconds" in e), default=None)}


def resource_policy(policy, aggregate=False):
    """Recompute ordinary resource limits without importing runner policy code."""
    stamp = datetime.fromisoformat(policy["local_time"])
    check(stamp.tzinfo is not None, "Resource timestamp lacks timezone")
    local = stamp.astimezone(ZoneInfo("Europe/Helsinki"))
    nighttime = local.hour >= 23 or local.hour < 7
    percent = policy["percent"] if policy["source"] == "manual" else (80 if nighttime else 50)
    check(isinstance(percent, int) and not isinstance(percent, bool) and 1 <= percent <= 100, "Invalid resource percentage")
    check(policy["source"] in ("manual", "nighttime" if nighttime else "daytime"), "Unexpected resource source")
    check(policy["timezone"] == "Europe/Helsinki" and policy["percent"] == percent,
          "Ordinary resource percentage differs")
    check(policy["max_cpu_workers"] == max(1, math.floor(policy["logical_cpus"]*percent/100)),
          "CPU budget calculation differs")
    check(policy["max_cpu_workers"] >= 4 and policy["memory_fraction"] == percent/100,
          "Aggregate workers exceed budget")
    check(policy["active_search_workers"] == (4 if aggregate else 1) and
          policy["resident_engines"] == (8 if aggregate else 2), "Reservation shape differs")
    if aggregate:
        check(policy["estimated_memory_bytes"] == 6*1024**3, "Aggregate reservation differs")
    memory = policy["physical_memory_bytes"]
    check(memory is not None and (1 if aggregate else 4)*policy["estimated_memory_bytes"] <= memory*percent/100,
          "Aggregate memory reservation exceeds budget or lacks host evidence")


def pid_present(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True



PROTOCOL = 'docs/experiments/match-readiness-20261020.md'
OPENINGS = tuple(f'tests/data/match-readiness-20261020-{i:02d}.json' for i in range(1, 5))
OPENINGS_SHA256 = (
    '21c126afe5c6ebbe87ac07172454ffc47b36ec34201590a4d00b98d93f05dc65',
    '04f486e6cd1538bdb3acf6fc5e4a2c2aad32e42fecc15d37906ac13a9c3b7cbd',
    '5822c331a48dafcab2a5c4adadbafaf909dfa91310070bc71351d47fce70ade8',
    'a8e0121089a56eafe0a27cee91b317cfad3c5fb997385dcd11f7fbc225108edc')
SEEDS = tuple(range(20261020401, 20261020405))
ROLE_OPTIONS = {role: {'Time Policy': 'classic', 'Capture Ordering': 'mvv-lva',
                     'Late Move Reductions': 'true' if role == 'candidate' else 'false',
                     'Countermove Ordering': 'false', 'Null Move Pruning': 'false',
                     'Reverse Futility Pruning': 'false', 'QSearch SEE Pruning': 'false',
                     'SyzygyProbeLimit': '0'} for role in ('candidate', 'opponent')}


def overlap(windows):
    """Sweep half-open charged intervals; same-shard overlap is always invalid."""
    events = []
    for item in windows:
        start, end = item['start_ns'], item['end_ns']
        check(isinstance(start, int) and isinstance(end, int) and end >= start,
              'Invalid search interval')
        if end > start:
            events.extend(((start, 1, item['shard']), (end, -1, item['shard'])))
    active, peak, duration, previous = set(), 0, 0, None
    for stamp, delta, shard in sorted(events):
        if previous is not None and len(active) == 4:
            duration += stamp-previous
        if delta == -1:
            check(shard in active, 'Unmatched search end')
            active.remove(shard)
        else:
            check(shard not in active, 'Overlapping searches within one shard')
            active.add(shard)
        peak = max(peak, len(active))
        previous = stamp
    check(not active, 'Unclosed search interval')
    check(peak == 4 and duration > 0, 'Actual four-worker search overlap not established')
    return {'peak_active_searches': peak, 'four_active_duration_ns': duration}


def audit_launcher(directory, engine_sha, records_by_shard):
    launcher = read(directory/'launcher.json')
    check(launcher['schema_version'] == 1 and launcher['protocol_id'] == 'match-readiness-20261020-v1', 'Launcher schema/protocol differs')
    check(launcher['opening_manifest'] == [{'path': str((ROOT/name).resolve()), 'sha256': sha} for name, sha in zip(OPENINGS, OPENINGS_SHA256)], 'Opening manifest differs')
    check(launcher['engine_sha256'] == engine_sha == EXPECTED_ENGINE_SHA, 'Engine pin differs')
    check(launcher['network_sha256'] == EXPECTED_NETWORK_SHA, 'Network pin differs')
    check(launcher['source_hashes'] == launcher['source_hashes_after'], 'Sources changed during run')
    required = {'tools/match.py', 'tools/match_statistics.py', 'tools/resources.py',
                'tools/check_match_readiness.py', 'tools/audit_match_readiness.py', PROTOCOL, 'tests/data/match-readiness-20261020-generation.json', *OPENINGS}
    check(required <= set(launcher['source_hashes']), 'Required source pins absent')
    for name, expected in launcher['source_hashes'].items():
        check(hashlib.sha256(raw(ROOT/name)).hexdigest() == expected, 'Pinned source changed: '+name)
    check(launcher['protocol'] == raw(ROOT/PROTOCOL).decode(), 'Protocol snapshot differs')
    check(launcher['settings'] == EXPECTED, 'Launcher settings differ')
    check(launcher['active_search_workers'] == 4 and launcher['resident_engines'] == 8,
          'Aggregate concurrency differs')
    check(launcher['timeout_seconds'] == 180 and launcher['seeds'] == list(SEEDS),
          'Deadline or seeds differ')
    resource_policy(launcher['initial_resource_policy'], aggregate=True)
    check(launcher.get('integrity_unchanged') is True, 'Final integrity flag differs')
    started, finished = map(datetime.fromisoformat, (launcher['started_utc'], launcher['finished_utc']))
    check(started.tzinfo is not None and finished.tzinfo is not None and finished >= started,
          'Invalid campaign timestamps')
    near((finished-started).total_seconds(), launcher['elapsed_seconds'], 'Campaign duration differs', 1.)
    check(launcher['status'] == 'finished' and 0 <= launcher['elapsed_seconds'] <= 180,
          'Run incomplete or exceeds deadline including cleanup')
    admissions = launcher['admissions']
    identities = {(shard, r['game_id']) for shard, rows in records_by_shard.items() for r in rows}
    check(len(admissions) == 8 and {(a['shard'], a['game_id']) for a in admissions} == identities,
          'Resource admission identities differ')
    for admission in admissions:
        resource_policy(admission['policy'], aggregate=True)
        stamp = datetime.fromisoformat(admission['policy']['local_time'])
        row = next(r for r in records_by_shard[admission['shard']] if r['game_id'] == admission['game_id'])
        check(started <= stamp <= datetime.fromisoformat(row['started_utc']) <= finished,
              'Admission occurs outside its game boundary')
    events = launcher['resource_events']
    check(bool(events), 'Resource monitor has no observations')
    previous_ns = -1
    for event in events:
        resource_policy(event['policy'], aggregate=True)
        stamp = datetime.fromisoformat(event['policy']['local_time'])
        check(started <= stamp <= finished and 0 <= event['gap_seconds'] <= 5 and event['checked_ns'] > previous_ns,
              'Invalid resource monitor observation')
        if previous_ns >= 0:
            near((event['checked_ns']-previous_ns)/1e9, event['gap_seconds'],
                 'Resource monitor elapsed interval differs', .001)
        previous_ns = event['checked_ns']
    if search_windows:
        check(events[0]['checked_ns']-min(w['start_ns'] for w in search_windows) <= 5e9 and
              max(w['end_ns'] for w in search_windows)-events[-1]['checked_ns'] <= 5e9,
              'Resource observations do not cover active searches')
    pids = sorted({e['pid'] for rows in records_by_shard.values() for r in rows for e in r['engines'].values()})
    cleanup = launcher['cleanup']
    check(cleanup['engine_pids'] == pids and not cleanup['alive_pids'] and not cleanup['unverified_pids'],
          'Cleanup evidence differs or engine exit unverified')
    check(not any(pid_present(pid) for pid in pids), 'Recorded engine PID remains alive')
    return {'elapsed_seconds': launcher['elapsed_seconds'], 'closed_engine_pids': pids,
            'aggregate_reserved_memory_bytes': launcher['initial_resource_policy']['estimated_memory_bytes'],
            **overlap(search_windows)}


def audit_shard(folder, source, index):
    run = read(folder/'run.json')
    check(run['schema_version'] == 1 and run['settings'] == EXPECTED and run['chess_version'] == '1.11.2', 'Runner settings differ')
    persistence = run['persistence']
    check(persistence['bounds_include_in_flight'] is True and persistence['max_pending_bytes'] == 8*1024**2
          and persistence['max_pending_records'] == 4096 and persistence['deadline_seconds'] == 30.,
          'Persistence bounds differ')
    check(run['seed'] == SEEDS[index] and run['planned_pairs'] == len(run['plan']) == 1, 'Schedule differs')
    pair = run['plan'][0]
    check(pair['pair_id'] == 'p000001' and pair['opening_id'] == source['id'] and
          pair['moves'] == source['moves'] and pair['starting_fen'] == chess.STARTING_FEN,
          'Frozen full-history opening differs')
    key = hashlib.sha256(json.dumps({'fen': chess.STARTING_FEN, 'moves': source['moves']}, sort_keys=True).encode()).hexdigest()
    check(pair['opening_key'] == key, 'Opening key differs')
    first = random.Random(SEEDS[index]).choice(('white', 'black'))
    check(pair['first_candidate_color'] == first, 'Color ordering differs')
    copy = read(folder/'openings.json')
    check(copy['openings'] == [source] and
          hashlib.sha256(raw(folder/'openings.json')).hexdigest() == run['opening_suite']['sha256'],
          'Frozen opening copy differs')
    check(set(run['engines']) == {'candidate', 'opponent'}, 'Role set differs')
    for role, spec in run['engines'].items():
        check(spec['arguments'] == [] and spec['network_option'] == 'EvalFile' and
              spec['experiment_options'] == ROLE_OPTIONS[role], 'Experimental isolation differs')
        check(len(spec['artifacts']) == 2, 'Artifact membership differs')
        for artifact in spec['artifacts']:
            content = raw(artifact['path'])
            check(len(content) == artifact['bytes'] and hashlib.sha256(content).hexdigest() == artifact['sha256'],
                  'Frozen artifact changed')
        check(spec['artifacts'][0]['path'] == spec['executable'] and
              spec['artifacts'][0]['sha256'] == EXPECTED_ENGINE_SHA and
              spec['artifacts'][1]['path'] == spec['network'] and
              spec['artifacts'][1]['sha256'] == EXPECTED_NETWORK_SHA, 'Artifact identity differs')
    for entry in run['runner_sources']:
        check(hashlib.sha256(raw(ROOT/entry['path'])).hexdigest() == entry['sha256'], 'Runner source changed')
    check({s['path'] for s in run['runner_sources']} == {'tools/match.py', 'tools/match_statistics.py', 'tools/resources.py'},
          'Runner source membership differs')
    records = read(folder/'games.jsonl', lines=True)
    check(len(records) == 2 and [r['game_id'] for r in records] == ['p000001-1', 'p000001-2'], 'Game membership differs')
    check([r['candidate_color'] for r in records] == [first, 'black' if first == 'white' else 'white'], 'Color reversal differs')
    games = [audit_game(folder, run, row, pair) for row in records]
    summary = read(folder/'summary.json')
    check(summary['smoke'] is True and summary['inference_eligible'] is False, 'Strength inference not withheld')
    check(summary['game_status_counts'] == dict(Counter(r['status'] for r in records)) and
          summary['termination_counts'] == dict(Counter(r['termination'] for r in records)) and
          summary['recorded_games'] == 2, 'Summary counts differ')
    accepted = (run['status'] == 'finished' and summary['experiment_complete'] is True and
                all(r['status'] == 'complete' and r['termination'] != 'time_forfeit' and
                    not r.get('persistence_error') and not r.get('unexpected_stderr') for r in records))
    if all(r['status'] == 'complete' for r in records):
        check(summary['included_games'] == 2, 'Complete pair excluded')
        near(summary['score'], sum(r['candidate_score'] for r in records)/2, 'Summary score differs')
    else:
        check(summary['included_games'] == 0 and summary['score'] is None, 'Incomplete pair scored')
    return {'directory': str(folder), 'operational_acceptance': accepted, 'games': games}, records


def audit(campaign):
    """Retain checked inputs and earlier shard findings even after corrupt evidence."""
    inputs.clear(); search_windows.clear(); bestmove_receipts.clear(); protocol_events.clear()
    result = {'status': 'audit_failed', 'operational_acceptance': False, 'errors': [], 'shards': []}
    try:
        campaign = Path(campaign).resolve()
        check(chess.__version__ == '1.11.2', 'Referee version differs')
        check(len(OPENINGS_SHA256) == 4, 'Independent opening pins absent')
        sources = []
        for name, expected in zip(OPENINGS, OPENINGS_SHA256):
            check(hashlib.sha256(raw(ROOT/name)).hexdigest() == expected, 'Independent opening pin differs')
            document = read(ROOT/name)
            check(len(document['openings']) == 1, 'Opening suite membership differs')
            sources.extend(document['openings'])
        check(len(sources) == 4, 'Need four frozen roots')
        roots = set()
        for source in sources:
            board = position('position startpos moves '+' '.join(source['moves']))
            check(board.is_valid() and board.outcome(claim_draw=True) is None, 'Invalid/terminal opening')
            roots.add(' '.join(board.fen(en_passant='legal').split()[:4]))
        check(len(roots) == 4 and len({s['id'] for s in sources}) == 4, 'Duplicate opening roots/IDs')
        metadata = read(ROOT/'tests/data/match-readiness-20261020-generation.json')
        base = read(ROOT/metadata['base_exclusion']['path'])
        check(hashlib.sha256(raw(ROOT/metadata['base_exclusion']['path'])).hexdigest() == metadata['base_exclusion']['sha256'], 'Base exclusion pin differs')
        excluded = {entry['root_key'] for entry in base['roots']} | set(metadata['additional_excluded_roots'])
        check(not roots & excluded, 'Opening overlaps frozen public exclusion catalog')
        runs = sorted(campaign.glob('shard-*/run.json'))
        check([p.parent.name for p in runs] == [f'shard-{i}' for i in range(1, 5)], 'Shard membership differs')
        records = {}
        for index, path in enumerate(runs):
            report, rows = audit_shard(path.parent, sources[index], index)
            result['shards'].append(report); records[path.parent.name] = rows
        result['launcher'] = audit_launcher(campaign, EXPECTED_ENGINE_SHA, records)
        result['status'] = 'audit_passed'
        result['operational_acceptance'] = all(s['operational_acceptance'] for s in result['shards'])
    except Exception as error:
        result['errors'].append(f'{type(error).__name__}: {error}')
    result['inputs'] = dict(inputs)
    result['limitations'] = ['Finite operational screen; no strength or statistical reliability inference.',
                            'Charged boundaries are runner callback observations, not kernel arrival.',
                            'This short control does not reproduce the historical 60+0.6 qualification.',
                            'PID absence does not prove immunity from future PID reuse.']
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    result = audit(args.campaign)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({k: result[k] for k in ('status', 'operational_acceptance', 'errors')}))
    return 0 if result['operational_acceptance'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
