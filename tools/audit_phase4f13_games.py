#!/usr/bin/env python3
"""Audit the Phase 4F.13 raw game evidence at 15+0.15 without starting an engine.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

The result is a conditional experiment decision, never an automatic change to
the default engine policy. Failed and incomplete evidence remains reportable.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re
from zoneinfo import ZoneInfo

import chess
import chess.pgn

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ID = "phase4f13-nnue-2048-v1"
# Independent constants: raw evidence never inherits permission from a launcher.
DAYTIME_AUTHORIZATION = "phase4f13-daytime-20261030"
DAYTIME_WINDOW = "2026-10-30 14:00–22:45 Europe/Helsinki"
SETTINGS = {"initial": 15.0, "increment": 0.15, "hash_mb": 64, "threads": 1,
            "max_plies": 512, "startup_timeout": 30.0, "protocol_timeout": 5.0,
            "move_overhead_ms": 20, "smoke": False}


@dataclass(frozen=True)
class AuditProtocol:
    """Independently pinned expectations, never taken from a campaign manifest.

    The aggregate auditor supplies its own independent constants for each shard.
    This descriptor is deliberately independent of the launcher's configuration.
    """
    protocol_id: str
    pairs: int
    seed: int
    protocol_document: str
    role_options: tuple
    required_sources: tuple
    pinned_sha256: tuple
    entrypoint: str
    settings: tuple = tuple(SETTINGS.items())

    def options(self, role):
        return dict(dict(self.role_options)[role])

    def pins(self):
        return dict(self.pinned_sha256)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(a, b, message, tolerance=1e-8):
    require(math.isfinite(a) and math.isfinite(b) and abs(a-b) <= tolerance, message)


def compare_values(actual, expected, message):
    """Allow floating-point roundoff, but reject structural or categorical drift."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), message)
        for key in expected:
            compare_values(actual[key], expected[key], message + "/" + key)
    elif isinstance(expected, float):
        close(actual, expected, message, 1e-10)
    else:
        require(actual == expected, message)


def relative_elo(score):
    if score in (0, 1):
        return {"value": None, "interpretation": "positive_infinity" if score else "negative_infinity"}
    return {"value": 400 * math.log10(score / (1-score)), "interpretation": "finite"}


def statistics_for(records, plan, finished, pairs=32):
    """Recompute pair statistics independently of the match statistics module."""
    included, excluded, wdl = [], [], Counter(wins=0, draws=0, losses=0)
    points_histogram = {f"{v/2:.1f}": 0 for v in range(5)}
    for pair in plan:
        games = [g for g in records if g.get("pair_id") == pair["pair_id"]]
        valid = (len(games) == 2 and all(g.get("status") == "complete" for g in games)
                 and {g.get("candidate_color") for g in games} == {"white", "black"})
        if not valid:
            excluded.append(pair["pair_id"])
            continue
        points = []
        for game in games:
            white = {"1-0": 1., "1/2-1/2": .5, "0-1": 0.}[game["result"]]
            score = white if game["candidate_color"] == "white" else 1-white
            require(game["candidate_score"] == score, "Journal candidate score disagrees with result")
            points.append(score)
            wdl["wins" if score == 1 else "losses" if score == 0 else "draws"] += 1
        total = math.fsum(points)
        points_histogram[f"{total:.1f}"] += 1
        included.append({"pair_id": pair["pair_id"], "opening_key": pair["opening_key"],
                         "points": total, "score": total/2})
    score = math.fsum(p["score"] for p in included)/len(included) if included else None
    eligible = finished and len(included) == pairs and not excluded
    radius = math.sqrt(math.log(40)/(2*pairs)) if eligible else None
    interval = {"lower": max(0., score-radius), "upper": min(1., score+radius)} if eligible else None
    return {"wdl": dict(wdl), "pair_point_counts": points_histogram, "score": score,
            "included_pairs": len(included), "excluded_pairs": len(excluded),
            "included_games": len(included)*2, "excluded_games": len(records)-len(included)*2,
            "included_pair_scores": included, "radius": radius, "score_interval": interval,
            "inference_eligible": eligible,
            "relative_elo": relative_elo(score) if score is not None else {"value": None, "interpretation": "no_completed_pairs"},
            "relative_elo_interval": {k: relative_elo(v) for k, v in interval.items()} if interval else None}


def classify(statistics, complete, errors, candidate_forfeits):
    """Apply the predeclared gate; never promote an engine default."""
    if errors or not complete or not statistics.get("inference_eligible"):
        return "invalid_or_incomplete"
    if candidate_forfeits:
        return "operational_regression"
    interval = statistics["score_interval"]
    if interval["lower"] > .5:
        return "eligible_for_confirmation_review"
    if interval["upper"] < .5:
        return "negative_evidence"
    return "inconclusive"


class Audit:
    """Collect source digests and local failures while retaining a usable report."""
    def __init__(self, campaign, protocol):
        self.campaign = Path(campaign).resolve()
        self.protocol = protocol
        self.inputs = {}
        self.errors = []
        self.games = []
        self.live_source_differences = []

    def read(self, path, lines=False):
        path = Path(path).resolve()
        raw = path.read_bytes()
        self.inputs[str(path)] = hashlib.sha256(raw).hexdigest()
        return [json.loads(line) for line in raw.splitlines()] if lines else json.loads(raw)

    def asset(self, path, expected):
        path = Path(path).resolve()
        value = digest(path)
        self.inputs[str(path)] = value
        require(value == expected["sha256"], "Artifact hash changed: " + str(path))
        require(path.stat().st_size == expected["bytes"], "Artifact size changed: " + str(path))

    def match_file(self, name):
        path = (self.campaign / "match" / name).resolve()
        require(path.is_relative_to(self.campaign / "match"), "Match file escapes its directory")
        return path

    def manifest(self):
        launch = self.read(self.campaign / "launch.json")
        protocol_spec = self.protocol
        require(launch["schema_version"] == 1 and launch["protocol_id"] == protocol_spec.protocol_id, "Unknown campaign protocol")
        require(chess.__version__ == launch["chess_version"] == "1.11.2", "Incorrect referee version")
        config = launch["configuration"]
        require(config["pairs"] == protocol_spec.pairs and config["seed"] == protocol_spec.seed, "Campaign sample or seed changed")
        require(config["settings"] == dict(protocol_spec.settings) and config["ponder"] is False and config["diagnostics"] is False,
                "Campaign settings changed")
        require(canonical_digest(config) == launch["configuration_sha256"], "Configuration digest mismatch")
        assets = launch["assets"]
        for key, expected in protocol_spec.pins().items():
            require(assets[key]["sha256"] == expected, "Unpinned " + key)
            self.asset(assets[key]["path"], assets[key])
        engines = {entry["role"]: entry for entry in config["engines"]}
        require(len(config["engines"]) == 2 and set(engines) == {"candidate", "opponent"}, "Invalid engine roles")
        for role in ("candidate", "opponent"):
            spec = engines[role]
            require(spec["executable"] == assets["engine_" + role]["path"] and spec["network"] == assets["network"]["path"],
                    "Engine configuration does not use frozen assets")
            require(spec["arguments"] == [] and spec["network_option"] == "EvalFile" and
                    spec["extra_options"] == protocol_spec.options(role), "Experimental modes are not isolated")
        require(launch["match_directory"] == "match", "Unexpected match directory")
        sources = launch["sources"]
        required = set(protocol_spec.required_sources)
        require(required <= set(sources), "Required source hashes are missing")
        for path, expected in sources.items():
            require(re.fullmatch(r"[0-9a-f]{64}", expected["sha256"]) and expected["bytes"] > 0,
                    "Malformed source fingerprint")
            live = ROOT / path
            if not live.is_file() or digest(live) != expected["sha256"]:
                self.live_source_differences.append(path)
        after = launch.get("integrity_after")
        require(after is not None, "Campaign has no final integrity record")
        require(after["unchanged"] is True and after["configuration_sha256"] == launch["configuration_sha256"]
                and after["assets"] == assets and after["sources"] == sources, "Final integrity check failed")
        protocol = launch["protocol_document"]
        require(protocol["frozen_copy"] == "protocol.md" and protocol["source"] == protocol_spec.protocol_document, "Unexpected protocol snapshot path")
        raw = (self.campaign / "protocol.md").read_bytes()
        self.inputs[str(self.campaign / "protocol.md")] = hashlib.sha256(raw).hexdigest()
        require(hashlib.sha256(raw).hexdigest() == protocol["sha256"], "Protocol snapshot changed")
        require(sources[protocol["source"]]["sha256"] == protocol["sha256"], "Protocol differs from frozen source")
        policy = launch["launch_policy"]
        require(policy["timezone"] == "Europe/Helsinki", "Incorrect launch timezone")
        local = datetime.fromisoformat(policy["local_time"])
        started = datetime.fromisoformat(launch["started_utc"])
        require(local.tzinfo is not None and started.tzinfo is not None, "Launch timestamps lack timezone")
        require(local.isoformat() == local.astimezone(ZoneInfo("Europe/Helsinki")).isoformat(), "Incorrect Helsinki offset")
        night = local.hour >= 23 or local.hour < 7
        flag = policy["allow_daytime"]
        require(type(flag) is bool and policy["nighttime"] is night, "Launch permission or nighttime flag changed")
        if flag:
            permitted = local.date().isoformat() == "2026-10-30" and time(14) <= local.time() < time(22, 45)
            cutoff = datetime(2026, 10, 31, 7, tzinfo=ZoneInfo("Europe/Helsinki"))
        else:
            permitted = local.hour == 23 and local.minute < 30
            end_date = local.date()+timedelta(days=int(local.hour >= 7))
            cutoff = datetime.combine(end_date, time(7), tzinfo=ZoneInfo("Europe/Helsinki"))
        require(policy["daytime_authorization"] == (DAYTIME_AUTHORIZATION if flag else None)
                and policy["launch_window"] == (DAYTIME_WINDOW if flag else "23:00–23:30 Europe/Helsinki")
                and policy["launch_permitted"] is True and permitted,
                "Launch is outside its exact authorized date/window")
        require(datetime.fromisoformat(policy["cutoff_local"]) == cutoff and
                datetime.fromisoformat(policy["cutoff_utc"]) == cutoff, "Original Helsinki 07:00 cutoff changed")
        require(local <= started < cutoff and policy["remaining_seconds"] > 0, "Invalid launch/cutoff ordering")
        if launch["status"] == "finished":
            finished = datetime.fromisoformat(launch["finished_utc"])
            require(started <= finished <= cutoff, "Completed campaign exceeds its declared window")
        require(launch["preflight"]["opening_count"] == launch["preflight"]["distinct_roots"] == protocol_spec.pairs,
                "Preflight root count mismatch")
        self.launch = launch
        self.assets = assets
        return launch

    def plan(self, run):
        require(run["schema_version"] == 1 and run["settings"] == dict(self.protocol.settings) and run["planned_pairs"] == self.protocol.pairs
                and run["seed"] == self.protocol.seed and run["chess_version"] == "1.11.2", "Match differs from frozen protocol")
        suite_path = self.match_file("openings.json")
        require(digest(suite_path) == self.assets["openings"]["sha256"] == run["opening_suite"]["sha256"],
                "Match opening suite differs from launch")
        entries = self.read(suite_path)["openings"]
        require(len(entries) == self.protocol.pairs and len({e["id"] for e in entries}) == self.protocol.pairs,
                "Unexpected opening count or duplicate identifiers")
        definitions, final_roots = [], set()
        for entry in entries:
            board = chess.Board(entry.get("fen", chess.STARTING_FEN))
            start = board.fen()
            require(board.is_valid(), "Invalid opening start")
            for move in entry["moves"]:
                board.push_uci(move)
            require(board.is_valid() and board.outcome(claim_draw=True) is None, "Invalid or terminal opening")
            root = " ".join(board.fen().split()[:4])
            require(root not in final_roots, "Duplicate final opening root")
            final_roots.add(root)
            key = hashlib.sha256(json.dumps({"fen": start, "moves": entry["moves"]}, sort_keys=True).encode()).hexdigest()
            definitions.append({"opening_id": entry["id"], "opening_key": key,
                                "starting_fen": start, "moves": entry["moves"]})
        randomizer = random.Random(self.protocol.seed)
        randomizer.shuffle(definitions)
        expected = [dict(item, pair_id=f"p{i+1:06d}", first_candidate_color=randomizer.choice(("white", "black")))
                    for i, item in enumerate(definitions)]
        require(run["plan"] == expected, "Runner plan differs from fixed seed/full histories")
        for role in ("candidate", "opponent"):
            spec = run["engines"][role]
            require(spec["experiment_options"] == self.protocol.options(role) and spec["arguments"] == []
                    and spec["network_option"] == "EvalFile", "Runner experiment options changed")
            require(spec["executable"] == self.assets["engine_" + role]["path"] and spec["network"] == self.assets["network"]["path"],
                    "Runner engine paths changed")
            require(spec["artifacts"] == [self.assets["engine_" + role], self.assets["network"]], "Runner artifact freeze differs")
        for source in run["runner_sources"]:
            require(source["sha256"] == self.launch["sources"][source["path"]]["sha256"], "Runner source differs from launch")
        require({s["path"] for s in run["runner_sources"]} == {"tools/match.py", "tools/match_statistics.py", "tools/resources.py"},
                "Unexpected runner source list")
        return expected

    def transcript(self, record, contexts):
        """Cross-check actual UCI configuration and charged go/bestmove timestamps."""
        events = self.read(self.match_file(record["protocol_log"]), lines=True)
        common = {"Hash": "64", "Threads": "1", "Ponder": "false", "Search Diagnostics": "false",
                  "Move Overhead": "20", "EvalFile": self.assets["network"]["path"]}
        state = {role: {"options": {}, "position": None, "newgame": False} for role in ("candidate", "opponent")}
        active, index, finished, previous = None, 0, 0, -1
        for event in events:
            role, line, tick = event["engine"], event["line"], event["monotonic_ns"]
            require(tick >= previous, "Protocol timestamps run backward")
            previous = tick
            current = state[role]
            if event["direction"] == "to_engine":
                if line.startswith("setoption name "):
                    match = re.fullmatch(r"setoption name (.+?) value (.*)", line)
                    if match:
                        current["options"][match[1]] = match[2]
                elif line == "ucinewgame":
                    current["newgame"] = True
                elif line.startswith("position "):
                    current["position"] = line[9:]
                elif line.startswith("go "):
                    require(active is None and current["newgame"], "Overlapping search or missing new game")
                    require(index < len(contexts) or record["status"] != "complete", "Search absent from game journal")
                    expected = dict(common, **self.protocol.options(role))
                    require(all(current["options"].get(k) == v for k, v in expected.items()), "Actual UCI options differ")
                    if index < len(contexts):
                        context = contexts[index]
                        require(role == context["event"]["engine"], "Wrong searching engine")
                        board = board_from_command(current["position"])
                        require(board.root().fen() == context["board"].root().fen() and board.move_stack == context["board"].move_stack,
                                "Search position lost or changed game history")
                        tokens = line.split()
                        require(len(tokens) == 9 and set(tokens[1::2]) == {"wtime", "btime", "winc", "binc"}, "Unexpected go limit")
                        limits = {k: int(v) for k, v in zip(tokens[1::2], tokens[2::2])}
                        for color, key in (("white", "wtime"), ("black", "btime")):
                            close(limits[key]/1000, context["clocks"][color], "Transmitted clock differs", .00101)
                        require(limits["winc"] == limits["binc"] == 150, "Wrong transmitted increment")
                    active = (role, tick, index)
                    index += 1
            else:
                require(event["direction"] != "stderr", "Unexpected stderr in frozen qualification protocol")
                require(event["direction"] == "from_engine", "Unknown transcript direction")
                option = re.match(r"option name (.+?) type (?:spin|check|combo|string) default (.*)", line)
                if option:
                    current["options"][option[1]] = re.split(r" (?:min|max|var) ", option[2], maxsplit=1)[0]
                if line.startswith("bestmove "):
                    require(active is not None and role == active[0], "Unsolicited bestmove")
                    if active[2] < len(contexts):
                        move = contexts[active[2]]["event"]
                        require(line.split()[1] == move.get("move"), "Transcript bestmove differs from journal")
                        close((tick-active[1])/1e9, move["elapsed_seconds"], "Charged clock is not go to bestmove")
                    finished += 1
                    active = None
                if record["status"] == "complete":
                    require("error:" not in line.lower(), "Completed game contains protocol error")
                    require(not line.startswith("info string search-"), "Diagnostics enabled during match")
        if record["status"] == "complete":
            require(active is None and index == finished == len(contexts), "Missing/extra search evidence")

    def game(self, record, pair):
        role_color = record["candidate_color"]
        require(role_color in ("white", "black") and record["opening_key"] == pair["opening_key"]
                and record["opening_id"] == pair["opening_id"], "Game opening identity mismatch")
        board = chess.Board(pair["starting_fen"])
        for token in pair["moves"]:
            board.push_uci(token)
        require(record["opening_plies"] == len(pair["moves"]), "Opening length mismatch")
        clocks = {"white": 15., "black": 15.}
        contexts, played = [], []
        for index, event in enumerate(record["moves"]):
            color = "white" if board.turn else "black"
            role = "candidate" if color == role_color else "opponent"
            require(event["color"] == color and event["engine"] == role and event["ply"] == board.ply()+1, "Move identity mismatch")
            close(event["clock_before"], clocks[color], "Journal clock continuity mismatch")
            contexts.append({"event": event, "board": board.copy(stack=True), "clocks": dict(clocks)})
            if "played" not in event:
                require(record["status"] != "complete" and index == len(record["moves"])-1, "Incomplete move in completed game")
                continue
            elapsed = event["elapsed_seconds"]
            require(math.isfinite(elapsed) and elapsed >= 0, "Invalid charged duration")
            move = chess.Move.from_uci(event["move"])
            require(move in board.legal_moves, "Illegal journal move")
            remaining = clocks[color]-elapsed
            if event["played"]:
                require(remaining >= 0, "Late move credited as played")
                clocks[color] = remaining+.15
                board.push(move)
                played.append(move.uci())
            else:
                require(remaining < 0 and index == len(record["moves"])-1 and record["termination"] == "time_forfeit",
                        "Unplayed move is not a genuine final flagfall")
                require(record["clock_loser"] == role, "Clock loser mismatch")
                clocks[color] = remaining
            close(event["clock_after"], clocks[color], "Increment/clock accounting mismatch")
        require(record["played_plies"] == len(played) and record["final_fen"] == board.fen(), "Journal final position mismatch")
        for color in clocks:
            close(record["clocks"][color], clocks[color], "Final clock mismatch")
        pgn_path = self.match_file(record["pgn"])
        self.inputs[str(pgn_path)] = digest(pgn_path)
        with pgn_path.open() as stream:
            game = chess.pgn.read_game(stream)
            require(chess.pgn.read_game(stream) is None, "Extra PGN game")
        require(game is not None and not game.errors, "Invalid PGN")
        require(game.board().fen() == pair["starting_fen"] and
                [m.uci() for m in game.mainline_moves()] == pair["moves"]+played, "PGN differs from full journal history")
        require(game.headers["Result"] == record["result"] and game.headers["Termination"] == record["termination"], "PGN outcome differs")
        require(game.end().board().fen() == board.fen(), "PGN final board differs")
        for node, event in zip(list(game.mainline())[len(pair["moves"]):], [e for e in record["moves"] if e.get("played")]):
            close(node.clock(), event["clock_after"], "PGN clock differs", .000501)
        if record["status"] == "complete":
            if record["termination"] == "time_forfeit":
                require(record["moves"] and record["moves"][-1].get("played") is False, "Flagfall lacks late move")
                winner = not board.turn
                expected = "1/2-1/2" if board.has_insufficient_material(winner) else "1-0" if winner else "0-1"
                require(record["result"] == expected, "Flagfall result/material mismatch")
            else:
                outcome = board.outcome(claim_draw=True)
                require(outcome is not None and outcome.result() == record["result"] and
                        outcome.termination.name.lower() == record["termination"], "Incorrect terminal result or claim")
        else:
            require(record["result"] == "*" and record["candidate_score"] is None, "Incomplete game was scored")
        self.transcript(record, contexts)
        return {"game_id": record["game_id"], "status": record["status"], "termination": record["termination"],
                "result": record["result"], "legal_plies": len(pair["moves"])+len(played), "search_events": len(contexts)}


def board_from_command(command):
    tokens = command.split()
    require(tokens[0] in ("startpos", "fen"), "Invalid position command")
    board = chess.Board() if tokens[0] == "startpos" else chess.Board(" ".join(tokens[1:7]))
    if "moves" in tokens:
        for token in tokens[tokens.index("moves")+1:]:
            board.push_uci(token)
    return board


def audit(campaign, protocol):
    checker = Audit(campaign, protocol)
    protocol = checker.protocol
    report = {"schema_version": 1, "protocol_id": protocol.protocol_id, "audited_utc": datetime.now(timezone.utc).isoformat(),
              "campaign": str(checker.campaign), "audit_tool_sha256": digest(__file__),
              "audit_entrypoint_sha256": digest(ROOT / protocol.entrypoint),
              "decision": "invalid_or_incomplete", "default_change": False,
              "interpretation": "Conditional on independent opening-pair sampling assumptions; limited to this suite and configuration. No general strength claim or automatic default change."}
    records, computed = [], {}
    complete = False
    try:
        launch = checker.manifest()
        run = checker.read(checker.match_file("run.json"))
        plan = checker.plan(run)
        records = checker.read(checker.match_file("games.jsonl"), lines=True)
        require(len({g["game_id"] for g in records}) == len(records), "Duplicate game identifiers")
        expected_ids = {f"{p['pair_id']}-{leg}" for p in plan for leg in (1, 2)}
        require({g["game_id"] for g in records} <= expected_ids, "Unexpected game identifiers")
        by_pair = {p["pair_id"]: p for p in plan}
        for record in records:
            try:
                pair = by_pair[record["pair_id"]]
                leg = int(record["game_id"].rsplit("-", 1)[1])
                require(record["game_id"] == f"{pair['pair_id']}-{leg}", "Game identifier belongs to another pair")
                first = pair["first_candidate_color"]
                expected_color = first if leg == 1 else "black" if first == "white" else "white"
                require(record["candidate_color"] == expected_color, "Pair colors do not follow plan")
                checker.games.append(checker.game(record, pair))
            except (ValueError, KeyError, TypeError, OSError, IndexError) as error:
                checker.errors.append(f"{record.get('game_id')}: {error}")
        complete = (launch["status"] == run["status"] == "finished" and len(records) == 2*protocol.pairs
                    and all(g["status"] == "complete" for g in records))
        computed = statistics_for(records, plan, run["status"] == "finished", protocol.pairs)
        smoke = dict(protocol.settings)["smoke"]
        if smoke:
            computed.update(inference_eligible=False, radius=None, score_interval=None, relative_elo_interval=None)
        saved = checker.read(checker.match_file("summary.json"))
        for key in ("wdl", "pair_point_counts", "included_pairs", "excluded_pairs", "included_games", "excluded_games", "included_pair_scores"):
            require(saved[key] == computed[key], "Saved summary differs: " + key)
        require(saved["recorded_games"] == len(records) and saved["experiment_complete"] == (run["status"] == "finished")
                and saved["smoke"] is smoke, "Summary completion metadata differs")
        require(saved["inference_eligible"] == computed["inference_eligible"], "Summary inference gate differs")
        for key in ("radius", "score_interval", "relative_elo_interval"):
            compare_values(saved["uncertainty"][key], computed[key], "Saved uncertainty differs: " + key)
        require(saved["uncertainty"]["confidence"] == .95 and saved["uncertainty"]["sample_size_pairs"] == computed["included_pairs"],
                "Wrong uncertainty configuration")
        if computed["score"] is not None:
            close(saved["score"], computed["score"], "Saved score differs")
        compare_values(saved["relative_elo"], computed["relative_elo"], "Saved relative Elo differs")
        require(saved["distinct_identified_openings"] == computed["included_pairs"] and saved["supplied_pairs"] == protocol.pairs,
                "Saved opening/pair counts differ")
        included_ids = {p["pair_id"] for p in computed["included_pair_scores"]}
        require(saved["included_time_forfeit_games"] == sum(g["termination"] == "time_forfeit" and g["pair_id"] in included_ids for g in records),
                "Saved clock-forfeit count differs")
        require(saved["termination_counts"] == dict(Counter(g["termination"] for g in records)) and
                saved["game_status_counts"] == dict(Counter(g["status"] for g in records)), "Saved termination/status counts differ")
        if "match_summary" in launch:
            require(launch["match_summary"] == saved, "Launcher and runner summaries differ")
    except (ValueError, KeyError, TypeError, OSError, IndexError) as error:
        checker.errors.append(str(error))
    candidate_forfeits = sum(g.get("termination") == "time_forfeit" and g.get("clock_loser") == "candidate" for g in records)
    report.update(decision=classify(computed, complete, checker.errors, candidate_forfeits), complete=complete,
                  errors=checker.errors, statistics=computed, games=checker.games, input_sha256=checker.inputs,
                  live_source_differences=checker.live_source_differences,
                  candidate_time_forfeits=candidate_forfeits,
                  opponent_time_forfeits=sum(g.get("termination") == "time_forfeit" and g.get("clock_loser") == "opponent" for g in records))
    if dict(protocol.settings)["smoke"]:
        report["decision"] = "operational_smoke_only" if complete and not checker.errors else "invalid_or_incomplete"
        report["interpretation"] = "Development smoke evidence only; never strength evidence or part of the held-out sample."
    return report


