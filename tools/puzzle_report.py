#!/usr/bin/env python3
"""Export an audited Phase 4F.7 puzzle comparison as Markdown and CSV.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Usage: python3 tools/puzzle_report.py REPORT.json --output NEW_DIRECTORY
The independent auditor replays existing evidence; no engine or benchmark is
started. Dependencies prepare automatically. The output parent must exist.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

if __name__ == "__main__":
    from tooling import direct_entry
    direct_entry(__file__)

import audit_phase4f7_puzzles as auditor

ROLES = ("hints-off", "hints-on")
OUTPUT_FILES = ("comparison.md", "positions.csv", "audit.json")
CSV_FIELDS = (
    "mode", "position_number", "position_id", "spreadsheet_row", "fen",
    "supplied_mate", "role", "score_type", "score_value", "score_pawns",
    "reported_mate", "depth", "seldepth", "bestmove", "ponder", "nodes",
    "receipt_seconds", "engine_time_ms", "reported_positive_mate",
    "reported_mate_matches_supplied", "final_pv_ends_in_checkmate",
)


def format_score(score):
    """Preserve the UCI distinction between centipawns and signed mate reports."""
    if score is None:
        return "No score"
    if score["type"] == "cp":
        return f"{score['value'] / 100:+.2f}"
    if score["type"] == "mate":
        value = score["value"]
        return f"{'-' if value < 0 else ''}M{abs(value)}"
    raise ValueError("Unsupported score type")


def code(value):
    """Render arbitrary recorded text without Markdown, HTML or table injection."""
    text = "".join(f"\\u{ord(char):04x}" if ord(char) < 32 or ord(char) == 127 else char
                   for char in str(value))
    return "<code>" + html.escape(text).replace("|", "&#124;") + "</code>"


def spreadsheet_text(value):
    """Keep text cells from becoming spreadsheet formulas; numbers stay numeric."""
    text = str(value)
    if text[:1] in ("\t", "\r", "\n") or text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def ordered_samples(report):
    """Display original corpus order and fixed role order, not execution order."""
    if report["mode"] == "check":
        return []
    samples = {(item["position_id"], item["role"]): item for item in report["samples"]}
    return [(number, position, samples[position["id"], role])
            for number, position in enumerate(report["positions"], 1) for role in ROLES]


def csv_rows(report):
    """Produce one row per actual search; absent cp/mate/ponder values stay blank."""
    rows = []
    for number, position, sample in ordered_samples(report):
        result, role = sample["result"], sample["role"]
        score = result["score"]
        rows.append(dict(
            mode=spreadsheet_text(report["mode"]), position_number=number,
            position_id=spreadsheet_text(position["id"]), spreadsheet_row=position["spreadsheet_row"],
            fen=spreadsheet_text(position["fen"]), supplied_mate=position["supplied_mate"],
            role=spreadsheet_text(role), score_type=score["type"], score_value=score["value"],
            score_pawns=f"{score['value'] / 100:.2f}" if score["type"] == "cp" else "",
            reported_mate=score["value"] if score["type"] == "mate" else "",
            depth=result["completed_depth"], seldepth=result["iterations"][-1]["seldepth"],
            bestmove=spreadsheet_text(result["bestmove"]),
            ponder=spreadsheet_text(result["ponder"]) if result["ponder"] is not None else "",
            nodes=result["reported_nodes"], receipt_seconds=sample["elapsed_seconds"],
            engine_time_ms=result["reported_time_ms"],
            reported_positive_mate=result["reported_positive_mate"],
            reported_mate_matches_supplied=result["reported_mate_matches_supplied"],
            final_pv_ends_in_checkmate=result["final_pv_ends_in_checkmate"],
        ))
    return rows


def differences(off, on):
    """Describe observations without ranking strength or inventing mate proofs."""
    notes = []
    if off["bestmove"] != on["bestmove"]:
        notes.append("Different best moves")
    if off["score"] != on["score"]:
        notes.append("Different scores")
    if off["completed_depth"] != on["completed_depth"]:
        notes.append("Different depths")
    if off["reported_positive_mate"] != on["reported_positive_mate"]:
        notes.append("Positive mate reported only with hints " + ("on" if on["reported_positive_mate"] else "off"))
    elif (off["reported_mate"] is not None and on["reported_mate"] is not None
          and off["reported_mate"] != on["reported_mate"]):
        notes.append("Different reported mate distances")
    return "; ".join(notes) if notes else "Same displayed result"


def render_markdown(report, certificate):
    """Render all positions from a freshly audited report, including adverse cases."""
    mode = report["mode"]
    label = {"check": "readiness check", "smoke": "one-second smoke", "full": "60-second comparison"}[mode]
    options = report["options"]["hints-off"]
    lines = [f"# chess0live puzzle report — {label}", "",
             f"Independent raw audit: **passed**. {certificate['raw_sessions']} sessions, "
             f"{certificate['searches']} searches, {certificate['zero_exits']} clean exits.", "",
             f"Run: {code(report['started_utc'])} to {code(report['finished_utc'])}.", "",
             f"Requested settings: **{options['Threads']} threads**, **{options['Hash']} MiB Hash**, "
             f"**{report['settings']['movetime_ms']} ms per search**. One fresh engine per role/position; "
             "only TT Move Hints differs. Threads and memory reservations are not measured OS utilization.", "",
             "Quiet-host operator attestation: **" + ("yes" if report["quiet_host"] else "no") + "**. "
             "This is not continuous thermal, power or competing-workload telemetry.", ""]
    if mode == "check":
        lines += ["**Readiness only:** both configurations were initialized and shut down; no position was searched. "
                  "The CSV contains its column headings only.", ""]
    elif mode == "smoke":
        lines += ["**Operational smoke only:** one second per search checks the workflow and legal output. "
                  "It does not replace the full 60-second comparison or establish playing strength.", ""]
    else:
        lines += ["**Tactical observations only:** this exposed puzzle set is separate from held-out match testing. "
                  "Completing it does not establish playing strength or qualify a default change.", ""]
    lines += ["Scores are from the side to move. Ordinary scores are in pawns; M7 means the engine reports "
              "mate in seven moves, and -M7 reports being mated. Supplied mate annotations are separate claims. "
              "Neither a mate report nor a legal mating PV proves forced mate against every defense. "
              "Centipawns are not distance to mate, and deeper search is not a strength score. "
              "Parallel search can vary between runs.", ""]
    if mode != "check":
        lines += ["## Summary", "",
                  f"Same final best move: **{certificate['same_bestmove']}/{len(report['positions'])}** positions. "
                  f"The audit replayed {certificate['iterations']} completed iterations and "
                  f"{certificate['legal_pv_plies']} legal PV plies.", "",
                  "| Observation | Hints off | Hints on |", "| --- | ---: | ---: |"]
        labels = (("reported_positive_mate", "Positive mate reports"),
                  ("reported_mate_matches_supplied", "Reported distance matches supplied annotation"),
                  ("final_pv_ends_in_checkmate", "Legal final PV ends in checkmate"))
        for field, title in labels:
            lines.append(f"| {title} | {certificate['roles']['hints-off'][field]} | {certificate['roles']['hints-on'][field]} |")
        lines += ["", "## Every position", "",
                  "Each score is followed by the last completed nominal depth. No position is omitted or ranked.", "",
                  "| # | Supplied mate | Hints off: score / depth | Hints on: score / depth | Best moves: off / on | Observed differences |",
                  "| ---: | --- | --- | --- | --- | --- |"]
        lookup = {(s["position_id"], s["role"]): s["result"] for s in report["samples"]}
        for number, position in enumerate(report["positions"], 1):
            off, on = (lookup[position["id"], role] for role in ROLES)
            moves = code(off["bestmove"]) if off["bestmove"] == on["bestmove"] else code(off["bestmove"]) + " / " + code(on["bestmove"])
            lines.append(f"| {number} | M{position['supplied_mate']} | "
                         f"{format_score(off['score'])} / {off['completed_depth']} | "
                         f"{format_score(on['score'])} / {on['completed_depth']} | {moves} | {differences(off, on)} |")
        lines += ["", "A single best move in the table means both roles chose it. The CSV retains each role separately, "
                  "with the exact FEN, source spreadsheet row, signed UCI score, nodes and timing.", ""]
    lines += ["## Evidence identities", "",
              f"- Source revision: {code(report['engine_source_revision'])}",
              f"- Audited report SHA-256: {code(certificate['report_sha256'])}",
              f"- Executable SHA-256: {code(report['assets']['engine']['sha256'])}",
              f"- Network: {code(Path(report['assets']['network']['path']).name)}",
              f"- Network SHA-256: {code(report['assets']['network']['sha256'])}",
              f"- Preparation pins SHA-256: {code(report['assets']['pins']['sha256'])}", "",
              "The included audit.json contains the fresh independent audit result. This export reads saved "
              "evidence only; it starts no engine, reruns no search and changes no playing option.", ""]
    return "\n".join(lines)


def evidence_hashes(report_path, report, report_sha256):
    """Collect the identities already validated by the independent auditor."""
    expected = {Path(report_path).resolve(): report_sha256}
    entries = [(Path(item["path"]), item["sha256"]) for item in report["assets"].values()]
    entries += [(Path(report_path).parent / sample["raw_log"], sample["raw_sha256"])
                for sample in report["samples"]]
    # Build provenance also pins third-party source files outside the asset map.
    if "engine_manifest" in report["assets"]:
        manifest = json.loads(Path(report["assets"]["engine_manifest"]["path"]).read_bytes(),
                              object_pairs_hook=auditor.unique_object)
        entries += [(auditor.ROOT / name, identity)
                    for name, identity in manifest["source_sha256"].items()]
    for path, identity in entries:
        path = path.resolve()
        if path in expected and expected[path] != identity:
            raise ValueError("Conflicting evidence identities")
        expected[path] = identity
    return expected


def verify_evidence(expected):
    """Refuse publication if input bytes drift after their fresh raw audit."""
    for path, identity in expected.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != identity:
            raise ValueError("Evidence changed during export: " + str(path))


def _write_staged(stage, markdown, rows, certificate):
    """Prepare complete files before reserving the visible export directory."""
    (stage / "comparison.md").write_text(markdown, encoding="utf-8")
    with (stage / "positions.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (stage / "audit.json").write_text(json.dumps(certificate, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _same_file(path, identity):
    try:
        current = path.lstat()
    except FileNotFoundError:
        return False
    return (current.st_dev, current.st_ino) == identity


def _publish(stage, output):
    """Create exclusively; failed writes remove only this attempt's own files.

    A plain POSIX directory rename can replace an empty destination introduced
    by another process. Exclusive mkdir and file creation preserve every existing
    path instead. All content is staged first; handled write failures clean up.
    """
    output.mkdir()  # Refuse existing directories, files and symlinks atomically.
    stat = output.lstat()
    directory_identity = (stat.st_dev, stat.st_ino)
    created = []
    try:
        for name in OUTPUT_FILES:
            target = output / name
            with target.open("xb") as destination:
                stat = os.fstat(destination.fileno())
                created.append((target, (stat.st_dev, stat.st_ino)))
                with (stage / name).open("rb") as source:
                    shutil.copyfileobj(source, destination)
    except BaseException:
        if _same_file(output, directory_identity):
            for target, identity in reversed(created):
                if _same_file(target, identity):
                    target.unlink()
            try:
                output.rmdir()  # Leave any foreign file added by another process.
            except OSError:
                pass
        raise


def export_report(report_path, output):
    """Freshly audit saved evidence and publish a new human-readable export."""
    report_path = Path(report_path).expanduser().resolve()
    requested_output = Path(output).expanduser()
    if requested_output.is_symlink() or requested_output.exists():
        raise ValueError("Output already exists; choose a new directory")
    output = requested_output.resolve()
    if not output.parent.is_dir():
        raise ValueError("Output parent does not exist: " + str(output.parent))
    before = report_path.read_bytes()
    certificate = auditor.audit(report_path)
    identity = hashlib.sha256(before).hexdigest()
    if (certificate.get("status") != "passed" or certificate.get("report_sha256") != identity
            or report_path.read_bytes() != before):
        raise ValueError("Report changed during its independent audit")
    report = json.loads(before, object_pairs_hook=auditor.unique_object)
    if (report.get("schema_version") != 1 or report.get("status") != "complete"
            or report.get("protocol") != "phase4f7-tt-hints-puzzles-v1"
            or report.get("mode") not in ("check", "smoke", "full")):
        raise ValueError("Only complete current Phase 4F.7 puzzle reports are supported")
    expected = evidence_hashes(report_path, report, identity)
    markdown, rows = render_markdown(report, certificate), csv_rows(report)
    with tempfile.TemporaryDirectory(prefix=".puzzle-report-", dir=output.parent) as temporary:
        stage = Path(temporary)
        _write_staged(stage, markdown, rows, certificate)
        verify_evidence(expected)
        _publish(stage, output)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Complete saved Phase 4F.7 report.json")
    parser.add_argument("--output", type=Path, required=True,
                        help="New export directory; its parent must already exist")
    args = parser.parse_args(argv)
    output = export_report(args.report, args.output)
    print("Saved audited puzzle report: " + str(output / "comparison.md"))
    print("Saved per-search spreadsheet data: " + str(output / "positions.csv"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        sys.exit("Puzzle report export failed: " + str(error))
    except KeyboardInterrupt:
        sys.exit("Puzzle report export stopped; no existing output was replaced.")
