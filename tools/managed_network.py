#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Register, select and launch locally qualified networks without changing defaults.

The catalog belongs to external tooling. The engine receives an explicit file
argument and never reads this catalog. A registered payload is a separate copy;
qualification and declared provenance stay with it. Local receipts detect drift,
but are not authenticated attestations or evidence of playing strength.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import uuid

import network
from fetch_network import fingerprint
from network import NetworkToolError, unique_object
from network_receipt import validate_qualification
from tooling import ToolingError, setup_lock

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = ROOT / '.local/networks/managed'
STATE_KEYS = {'schema_version', 'entries', 'active', 'previous', 'has_previous'}


def safe_path(value):
    """Paths travel as literal argv values and UCI strings, never shell code."""
    path = Path(value).expanduser().resolve()
    if any(ord(c) < 32 or ord(c) == 127 for c in str(path)):
        raise NetworkToolError('Paths must not contain control characters')
    return path


def check_name(name, *, default=False):
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', name):
        raise NetworkToolError('Use a name of 1–64 lowercase letters, digits, underscores or hyphens')
    if name == 'default' and not default:
        raise NetworkToolError('The name default is reserved for the pinned network')
    return name


def read_json(path):
    maximum = 4 * 1024 * 1024
    if not path.is_file() or path.stat().st_size > maximum:
        raise NetworkToolError('Missing or oversized record: ' + str(path))
    with path.open('rb') as stream:
        payload = stream.read(maximum + 1)
    if len(payload) > maximum:
        raise NetworkToolError('Record grew beyond its size limit: ' + str(path))
    return json.loads(payload, object_pairs_hook=unique_object)


def empty_state():
    return dict(schema_version=1, entries={}, active=None, previous=None, has_previous=False)


def read_state(store):
    """Read-only queries do not create a catalog or download the default file."""
    path = safe_path(store) / 'catalog.json'
    if path.is_symlink():
        raise NetworkToolError('Managed catalog must not be a symlink')
    if not path.exists():
        if path.parent.exists() and any(p.name != '.lock' for p in path.parent.iterdir()):
            raise NetworkToolError('Catalog is missing from a nonempty store; refusing a default fallback')
        return empty_state()
    state = read_json(path)
    if (not isinstance(state, dict) or set(state) != STATE_KEYS
            or type(state['schema_version']) is not int or state['schema_version'] != 1
            or not isinstance(state['entries'], dict) or type(state['has_previous']) is not bool):
        raise NetworkToolError('Invalid managed network catalog')
    for name, entry in state['entries'].items():
        check_name(name)
        if (not isinstance(entry, dict) or set(entry) != {'directory', 'receipt_sha256'}
                or not isinstance(entry['directory'], str)
                or not re.fullmatch(r'[a-f0-9]{32}', entry['directory'])
                or not isinstance(entry['receipt_sha256'], str)
                or not re.fullmatch(r'[a-f0-9]{64}', entry['receipt_sha256'])):
            raise NetworkToolError('Invalid catalog entry: ' + name)
    for key in ('active', 'previous'):
        if state[key] is not None and (not isinstance(state[key], str) or state[key] not in state['entries']):
            raise NetworkToolError('Catalog selection is missing: ' + key)
    if not state['has_previous'] and state['previous'] is not None:
        raise NetworkToolError('Invalid previous selection')
    return state


@contextmanager
def catalog_lock(store):
    """Serialize writers across processes; failed writes preserve the old state."""
    store = safe_path(store)
    store.mkdir(parents=True, exist_ok=True)
    with setup_lock(store / '.lock'):
        if not (store / 'catalog.json').exists():
            foreign = [p for p in store.iterdir() if p.name != '.lock']
            if foreign:
                raise NetworkToolError('Refusing to initialize a nonempty foreign catalog directory')
            save_state(store, empty_state())
        yield store


def save_state(store, state):
    """One atomic replacement publishes entries and selection together."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=store,
                                         prefix='.catalog-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream, indent=2, ensure_ascii=True, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, store / 'catalog.json')
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def entry_paths(store, entry):
    directory = safe_path(store) / 'entries' / entry['directory']
    if (directory.parent.is_symlink() or directory.is_symlink()
            or directory.resolve().parent != safe_path(store) / 'entries'):
        raise NetworkToolError('Managed entry escaped its catalog')
    return directory, directory / 'network.nnue', directory / 'receipt.json'


def validate_entry(store, name, entry, *, require_current=True):
    """Check stored bytes and retained evidence before selecting or launching."""
    directory, payload, receipt_path = entry_paths(store, entry)
    receipt = read_json(receipt_path)
    if fingerprint(receipt_path)[1] != entry['receipt_sha256']:
        raise NetworkToolError('Managed receipt changed: ' + name)
    if (not isinstance(receipt, dict) or receipt.get('schema_version') != 1
            or receipt.get('name') != name or type(receipt.get('has_metadata')) is not bool):
        raise NetworkToolError('Invalid managed receipt: ' + name)
    metadata = directory / 'metadata.json' if receipt['has_metadata'] else None
    info = network.inspect_network(payload, metadata)
    read_json(directory / 'qualification/report.json')
    if (info['artifact'] != receipt.get('artifact') or info['provenance'] != receipt.get('provenance')
            or fingerprint(directory / 'qualification/report.json')[1] != receipt.get('qualification_report_sha256')):
        raise NetworkToolError('Managed network, provenance or qualification changed: ' + name)
    verification = validate_qualification(directory / 'qualification', payload, metadata,
                                          require_current=require_current)
    return dict(name=name, status='ready' if verification['current_sources'] else 'stale',
                artifact=info['artifact'], provenance=info['provenance'], verification=verification,
                playing_strength='not_measured')


def default_status():
    info = network.inspect_network(network.default_network())
    if info['verification']['file_identity'] != 'manifest_pinned':
        raise NetworkToolError('Default network does not match networks/manifest.json; run make net')
    return dict(name='default', status='ready', artifact=info['artifact'], provenance=info['provenance'],
                verification=dict(scope='Manifest-pinned project default; not a new oracle run',
                                  current_sources=None), playing_strength='not_measured')


def resolve_selection(store, state, name, *, require_current=True):
    if name is None:
        return default_status()
    if name not in state['entries']:
        raise NetworkToolError('Unknown network: ' + name)
    return validate_entry(store, name, state['entries'][name], require_current=require_current)


def add_network(store, name, path, *, metadata=None, compiler=None,
                reference_dir=ROOT / '.local/networks/sf19-reference', offline=False, jobs=1):
    """Qualify a copied payload; publish an alias only after the complete check."""
    check_name(name)
    path = safe_path(path)
    metadata = safe_path(metadata) if metadata is not None else None
    before = network.inspect_network(path, metadata)
    if before['architecture']['status'] != 'recognized_header':
        raise NetworkToolError(before['architecture']['reason'])
    with catalog_lock(store) as store:
        state = read_state(store)
        if name in state['entries']:
            raise NetworkToolError('Name already registered; choose a new name: ' + name)
        if (store / 'entries').is_symlink():
            raise NetworkToolError('Managed entries directory must not be a symlink')
        directory = store / 'entries' / uuid.uuid4().hex
        directory.mkdir(parents=True)
        payload = directory / 'network.nnue'
        # No deletion on failure: retain diagnostics, never publish partial work.
        shutil.copyfile(path, payload)
        copied_metadata = directory / 'metadata.json' if metadata else None
        if metadata:
            shutil.copyfile(metadata, copied_metadata)
        copied = network.inspect_network(payload, copied_metadata)
        if ((copied['artifact']['size_bytes'], copied['artifact']['sha256'])
                != (before['artifact']['size_bytes'], before['artifact']['sha256'])
                or copied['provenance'] != before['provenance']):
            raise NetworkToolError('Network or metadata changed while copying')
        args = argparse.Namespace(network=payload, metadata=copied_metadata, output=directory / 'qualification',
                                  compiler=compiler, reference_dir=safe_path(reference_dir), offline=offline, jobs=jobs)
        if network.qualify(args) != 0:
            raise NetworkToolError('Registration failed; diagnostics retained in ' + str(directory))
        verification = validate_qualification(args.output, payload, copied_metadata)
        receipt = dict(schema_version=1, name=name, created_at=network.utc_now(),
                       artifact=copied['artifact'], provenance=copied['provenance'],
                       has_metadata=metadata is not None,
                       qualification_report_sha256=fingerprint(args.output / 'report.json')[1],
                       verification=verification)
        network.write_json(directory / 'receipt.json', receipt)
        entry = dict(directory=directory.name, receipt_sha256=fingerprint(directory / 'receipt.json')[1])
        result = validate_entry(store, name, entry)
        state['entries'][name] = entry
        save_state(store, state)
        return result


def select_network(store, name):
    check_name(name, default=True)
    selected = None if name == 'default' else name
    with catalog_lock(store) as store:
        state = read_state(store)
        result = resolve_selection(store, state, selected)
        if selected != state['active']:
            state.update(previous=state['active'], active=selected, has_previous=True)
            save_state(store, state)
        return result


def revert_network(store):
    with catalog_lock(store) as store:
        state = read_state(store)
        if not state['has_previous']:
            raise NetworkToolError('No previous selection to restore')
        result = resolve_selection(store, state, state['previous'])
        state['active'], state['previous'] = state['previous'], state['active']
        save_state(store, state)
        return result


def status(store):
    state = read_state(store)
    try:
        result = resolve_selection(store, state, state['active'], require_current=False)
    except (NetworkToolError, OSError, ValueError) as error:
        result = dict(name=state['active'] or 'default', status='unavailable', error=str(error))
    result.update(previous=(state['previous'] or 'default') if state['has_previous'] else None,
                  catalog=str(safe_path(store) / 'catalog.json'))
    return result


def list_networks(store):
    state = read_state(store)
    result = []
    for name in [None, *sorted(state['entries'])]:
        try:
            item = resolve_selection(store, state, name, require_current=False)
        except (NetworkToolError, OSError, ValueError) as error:
            item = dict(name=name or 'default', status='unavailable', error=str(error))
        item['selected'] = name == state['active']
        result.append(item)
    return result


def launch_config(store, engine):
    """Return literal launch arguments; never execute content read from reports."""
    engine = safe_path(engine)
    if not engine.is_file() or not stat.S_ISREG(engine.stat().st_mode) or not os.access(engine, os.X_OK):
        raise NetworkToolError('Choose a built chess0live executable with --engine PATH')
    state = read_state(store)
    selected = resolve_selection(store, state, state['active'])
    path = safe_path(selected['artifact']['path'])
    size, sha = fingerprint(engine)
    return dict(engine=dict(path=str(engine), size_bytes=size, sha256=sha), network=selected,
                argv=[str(engine), '--eval-file', str(path)],
                uci_option='setoption name EvalFile value ' + str(path),
                gui_note='A saved GUI EvalFile explicitly overrides this launch selection; set it to the same path.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, default=DEFAULT_STORE, help='local catalog directory')
    commands = parser.add_subparsers(dest='command', required=True)
    add = commands.add_parser('add', help='copy and freshly qualify a network under a new name')
    add.add_argument('name'); add.add_argument('network', type=Path)
    add.add_argument('--metadata', type=Path)
    add.add_argument('--compiler'); add.add_argument('--jobs', type=int, choices=(1, 2), default=1)
    add.add_argument('--reference-dir', type=Path, default=ROOT / '.local/networks/sf19-reference')
    add.add_argument('--offline', action='store_true')
    commands.add_parser('select', help='select a registered name or default').add_argument('name')
    for name in ('revert', 'status', 'list'):
        commands.add_parser(name)
    for name in ('config', 'run'):
        commands.add_parser(name).add_argument('--engine', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'add':
            result = add_network(args.store, args.name, args.network, metadata=args.metadata, compiler=args.compiler,
                                 reference_dir=args.reference_dir, offline=args.offline, jobs=args.jobs)
        elif args.command == 'select':
            result = select_network(args.store, args.name)
        elif args.command == 'revert':
            result = revert_network(args.store)
        elif args.command == 'status':
            result = status(args.store)
        elif args.command == 'list':
            result = list_networks(args.store)
        else:
            result = launch_config(args.store, args.engine)
            if args.command == 'run':
                # Inherit console/GUI pipes directly; no UCI proxy or shell parsing.
                os.execv(result['argv'][0], result['argv'])
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0
    except (NetworkToolError, ToolingError, OSError, ValueError, KeyError, TypeError, KeyboardInterrupt) as error:
        print('Error: ' + json.dumps(str(error) or 'Interrupted', ensure_ascii=True), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
