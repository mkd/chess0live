#!/usr/bin/env python3
"""Finite continuation-history development screen; no speed or strength claim.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Run through tools/run.py. Reuse the existing exposed corpus, independent legal
referee and bounded process/resource harness without modifying frozen tools.
One process/worker at a time; all 180 searches and complete transcripts survive.
"""
import argparse
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bench import digest
from profile_cache import board_for, publish
from profile_search_package import BASE_OPTIONS, CORPUS, NETWORK, Monitor, load_positions, send
from profile_tt_move_hints import finish_session, receive, run_order, validate_result
from uci_client import Engine

PREFIX = "info string continuation-history v1 "


def check_output(lines, board, role):
    """The existing validator independently replays every PV with python-chess."""
    records = [line for line in lines if line.startswith(PREFIX)]
    continuation = None
    if role == "on":
        assert len(records) == 1, records
        tokens = records[0][len(PREFIX):].split()
        assert len(tokens) == 12, tokens
        fields = dict(zip(tokens[::2], tokens[1::2]))
        assert set(fields) == {"enabled", "entries", "allocated_bytes", "lookups", "nonzero", "updates"}, fields
        assert fields.pop("enabled") == "true", fields
        assert all(v.isascii() and v.isdecimal() for v in fields.values()), fields
        continuation = {key: int(value) for key, value in fields.items()}
        assert continuation["entries"] == 589824, continuation
        assert continuation["allocated_bytes"] >= 1179648, continuation
        assert continuation["nonzero"] <= continuation["lookups"], continuation
    else:
        assert not records, records
    # The old validator's 'off' role requires every existing default-policy
    # diagnostic, full completed depth 6, exact accounting and no tablebase use.
    result = validate_result([line for line in lines if not line.startswith(PREFIX)], board, "off")
    result["continuation"] = continuation
    return result


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    corpus, positions = load_positions()
    paths = dict(parent=args.parent.resolve(), candidate=args.candidate.resolve(),
                 network=args.network.resolve(), corpus=CORPUS, script=Path(__file__),
                 protocol=ROOT / "docs/experiments/phase4f8.md")
    for name, module in tuple(sys.modules.items()):
        source = getattr(module, "__file__", None)
        if source:
            path = Path(source).resolve()
            if path.is_relative_to(ROOT) and path.suffix == ".py":
                paths["dependency:" + str(path.relative_to(ROOT))] = path
    identities = {key: dict(path=str(path), sha256=digest(path)) for key, path in paths.items()}
    expected = dict(parent="6dd685119d80145e2c6956c8d27c20a2d67e006bdf6556ceef5b779585baff9f",
                    network="1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2",
                    corpus="afd19399b8dfd284ea274a850988989f4127097eefb9266905faef7b3e6a300f")
    for name, checksum in expected.items():
        if identities[name]["sha256"] != checksum:
            raise ValueError("Prepared input identity mismatch: " + name)
    report = dict(status="running", identities=identities, corpus=corpus, sessions=[],
                  samples=[], resource_events=[], limitations="Exposed development roots; no speed or strength inference.")
    monitor = Monitor(paths["network"], report["resource_events"])
    monitor.threads = 1
    try:
        for repetition in range(2):
            for index, item in enumerate(positions):
                board = board_for(item["position"])
                for role in run_order(index, repetition):
                    name = f"r{repetition}-p{index:02d}-{role}"
                    session = dict(id=name, role=role, repetition=repetition, position_index=index,
                                   raw_log=name + ".jsonl", commands=[], identity=[], setup=[])
                    report["sessions"].append(session)
                    monitor.check(force=True)
                    binary = paths["parent" if role == "parent" else "candidate"]
                    raw_path = args.output / session["raw_log"]
                    try:
                        with raw_path.open("x") as raw:
                            engine = None
                            try:
                                engine = Engine(binary, cwd=ROOT)
                                session["pid"] = engine.process.pid
                                send(engine, "uci", raw, session)
                                receive(engine, "uciok", 10, monitor, raw, session["identity"])
                                advertised = "option name Continuation History type check default false"
                                assert (advertised in session["identity"]) == (role != "parent")
                                options = dict(BASE_OPTIONS, EvalFile=str(paths["network"]), **{"TT Move Hints": "false"})
                                if role != "parent": options["Continuation History"] = str(role == "on").lower()
                                session["options"] = options
                                for name, value in options.items():
                                    assert any(line.startswith(f"option name {name} type ") for line in session["identity"]), name
                                    send(engine, f"setoption name {name} value {value}", raw, session)
                                send(engine, "isready", raw, session)
                                receive(engine, "readyok", 10, monitor, raw, session["setup"])
                                assert session["setup"] == ["info string Syzygy largest 0 pieces; table files are external", "readyok"]
                                for temperature in ("cold", "warm"):
                                    sample = dict(session_id=session["id"], role=role, repetition=repetition,
                                                  position_index=index, temperature=temperature, output=[])
                                    report["samples"].append(sample)
                                    if temperature == "cold": send(engine, "ucinewgame", raw, session)
                                    send(engine, "position " + item["position"], raw, session)
                                    send(engine, "isready", raw, session)
                                    prep = receive(engine, "readyok", 10, monitor, raw, [])
                                    assert prep == ["readyok"], prep
                                    send(engine, "go depth 6", raw, session)
                                    receive(engine, "bestmove ", 10, monitor, raw, sample["output"])
                                    sample["result"] = check_output(sample["output"], board, role)
                                    send(engine, "isready", raw, session)
                                    post = receive(engine, "readyok", 10, monitor, raw, [])
                                    assert post == ["readyok"], post
                            finally:
                                original = sys.exc_info()[1]
                                if original is not None:
                                    session["error"] = f"{type(original).__name__}: {original}"
                                if engine is not None:
                                    try:
                                        finish_session(engine, session, raw)
                                    except Exception as cleanup:
                                        session["cleanup_error"] = f"{type(cleanup).__name__}: {cleanup}"
                                        if original is None: raise
                    finally:
                        if raw_path.exists(): session["raw_sha256"] = digest(raw_path)
                publish(args.output / "report.json", report)
        indexed = {(s["role"], s["position_index"], s["repetition"], s["temperature"]): s["result"] for s in report["samples"]}
        ratios, move_changes, score_changes = [], [], []
        for index in range(15):
            for repetition in range(2):
                for temperature in ("cold", "warm"):
                    results = {role: indexed[role, index, repetition, temperature] for role in ("parent", "off", "on")}
                    assert results["parent"]["signature"] == results["off"]["signature"], (index, repetition, temperature)
                    for role in results:
                        assert results[role]["signature"] == indexed[role, index, 0, temperature]["signature"], (role, index, temperature)
                        assert results[role]["continuation"] == indexed[role, index, 0, temperature]["continuation"], (role, index, temperature)
                    off, on = results["off"], results["on"]
                    ratios.append(on["reported_nodes"] / off["reported_nodes"])
                    if off["bestmove"] != on["bestmove"]: move_changes.append([index, repetition, temperature])
                    if off["iterations"][-1]["score"] != on["iterations"][-1]["score"]: score_changes.append([index, repetition, temperature])
        active = [s["result"]["continuation"] for s in report["samples"] if s["role"] == "on"]
        assert sum(v["nonzero"] for v in active) > 0 and sum(v["updates"] for v in active) > 0
        assert identities == {key: dict(path=str(path), sha256=digest(path)) for key, path in paths.items()}
        report.update(status="passed", summary=dict(searches=len(report["samples"]), clean_sessions=len(report["sessions"]),
                      disabled_parity_pairs=60, enabled_node_ratio_median=statistics.median(ratios),
                      enabled_node_ratio_range=[min(ratios), max(ratios)], changed_bestmoves=move_changes,
                      changed_final_scores=score_changes))
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        publish(args.output / "report.json", report)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--network", type=Path, default=NETWORK)
    parser.add_argument("--output", required=True, type=Path)
    run(parser.parse_args())
