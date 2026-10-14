#!/usr/bin/env python3
"""Decode an explicit flat ABI layout from validated historical call evidence."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import call_changes as changes

core = changes.core
HERE = Path(__file__).resolve().parent
SCHEMA = 'return-lens-v1'
LIMITS = ('Types are supplied by the reviewer, not inferred or authenticated. Decoding '
          'does not establish the contract ABI, expected outcome, safety, state changes, '
          'gas, canonicality or future execution. Historical provider claims only. '
          'No transaction is signed or sent.')


def layout(types):
    core.require(isinstance(types, list) and 1 <= len(types) <= 32,
                 'supply between 1 and 32 flat ABI types')
    for kind in types:
        core.require(isinstance(kind, str), 'ABI type must be a string')
        if kind in ('bool', 'address', 'bytes', 'string'):
            continue
        match = re.fullmatch(r'(uint|int)([1-9][0-9]{0,2})', kind)
        if match and 8 <= int(match[2]) <= 256 and int(match[2]) % 8 == 0:
            continue
        match = re.fullmatch(r'bytes([1-9][0-9]?)', kind)
        core.require(match is not None and int(match[1]) <= 32,
                     'unsupported ABI type: ' + kind)
    return list(types)


def decode(raw, types):
    """Require minimal offsets, ordered tails, canonical padding and exact consumption."""
    types = layout(types)
    payload = bytes.fromhex(core.data(raw)[2:])
    head_size = 32 * len(types)
    core.require(len(payload) >= head_size and len(payload) % 32 == 0,
                 'ABI data is truncated or not word-aligned')
    cursor = head_size
    result = []
    for index, kind in enumerate(types):
        word = payload[index * 32:(index + 1) * 32]
        number = int.from_bytes(word, 'big')
        if kind in ('bytes', 'string'):
            core.require(number == cursor, 'dynamic offset is not the next canonical tail')
            core.require(cursor + 32 <= len(payload), 'missing dynamic length word')
            length = int.from_bytes(payload[cursor:cursor + 32], 'big')
            start = cursor + 32
            end = start + length
            padded_end = start + ((length + 31) // 32) * 32
            core.require(padded_end <= len(payload), 'dynamic length exceeds return data')
            core.require(not any(payload[end:padded_end]), 'nonzero dynamic padding')
            data = payload[start:end]
            value = data.decode('utf-8', 'strict') if kind == 'string' else '0x' + data.hex()
            cursor = padded_end
        elif kind == 'bool':
            core.require(number in (0, 1), 'noncanonical bool')
            value = bool(number)
        elif kind == 'address':
            core.require(not any(word[:12]), 'nonzero address padding')
            value = '0x' + word[12:].hex()
        elif kind.startswith('bytes'):
            width = int(kind[5:])
            core.require(not any(word[width:]), 'nonzero fixed bytes padding')
            value = '0x' + word[:width].hex()
        elif kind.startswith('uint'):
            width = int(kind[4:])
            core.require(number < 2**width, 'unsigned integer exceeds declared width')
            value = str(number)
        else:
            width = int(kind[3:])
            signed = int.from_bytes(word, 'big', signed=True)
            core.require(-(2**(width - 1)) <= signed < 2**(width - 1),
                         'signed integer has invalid sign extension or width')
            value = str(signed)
        result.append({'type': kind, 'value': value})
    core.require(cursor == len(payload), 'extra trailing ABI data')
    return result


def evaluate(observation, types):
    types = layout(types)
    validated = changes.validate(observation)
    execution = changes.execution_evidence(observation, validated['result'])
    report = {'schema': SCHEMA, 'verdict': 'inconclusive', 'types': types,
              'source': observation['source'], 'chain_id': 1,
              'block': core.header(observation['block']), 'call': validated['call'],
              'saved_interpretation': observation['returns'], 'limits': LIMITS}
    if execution is None or execution[0] != 'returned':
        report['reason'] = 'no validated successful return bytes; refusal or RPC/ABI failure'
        return report
    report['raw'] = execution[1]
    try:
        report['values'] = decode(execution[1], types)
    except (ValueError, UnicodeError) as exc:
        report['reason'] = str(exc)
        return report
    report.update(verdict='decoded', reason='canonical bytes fit the explicitly chosen layout')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('demo', help='decode saved real ZTO totalSupply() offline')
    check = commands.add_parser('check', help='decode a saved Call Rehearsal observation offline')
    check.add_argument('observation')
    check.add_argument('--types', required=True, help='comma-separated flat types, e.g. uint256,string')
    live = commands.add_parser('live', help='read-only finalized ZTO or IMD totalSupply()')
    live.add_argument('--token', choices=core.TOKENS, default='ZTO')
    live.add_argument('--rpc', choices=core.ENDPOINTS, default=core.ENDPOINTS[0])
    live.add_argument('--save', help='new workspace evidence path, never overwritten')
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            obs = changes.load_observation(HERE.parent / 'call-rehearsal' / 'zto-observation.json')
            types = ['uint256']
        elif args.command == 'check':
            types = layout(args.types.split(','))
            obs = changes.load_observation(args.observation)
        else:
            destination = core.workspace_path(args.save) if args.save else None
            if destination:
                core.require(destination.parent.is_dir() and not destination.exists(),
                             'save requires an existing parent and a new file')
            obs = changes.capture(core.RPC(args.rpc), {
                'to': core.TOKENS[args.token], 'data': '0x18160ddd', 'value': '0x0'}, 'uint256')
            if destination:
                changes.save_observation(destination, obs)
            types = ['uint256']
        report = evaluate(obs, types)
        print(json.dumps(report, indent=2, allow_nan=False))
        return 0 if report['verdict'] == 'decoded' else 2
    except (ValueError, KeyError, TypeError, OSError, RecursionError, core.RPCError) as exc:
        print(json.dumps({'schema': SCHEMA, 'verdict': 'inconclusive', 'error': str(exc)}),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
