#!/usr/bin/env python3
"""Release a rehearsed call only when every numeric return meets explicit bounds."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent


def sibling(name, path):
    spec = importlib.util.spec_from_file_location(name, HERE.parent / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = sibling('bounds_release_gate', 'release-gate/release_gate.py')
lens = sibling('bounds_return_lens', 'return-bounds/return_lens.py')
binding = gate.expiry.sets.binding
core = gate.expiry.core
SCHEMA = 'rehearsal-return-bounds-v1'
EXIT = {'ready': 0, 'withheld': 1, 'inconclusive': 2}
LIMITS = (
    'Bounds check historical return bytes under reviewer-supplied integer ABI types, '
    'not authenticated ABI or economic meaning. Values and limits are raw integers; '
    'no decimals, token price or unit inference. Every set member must bind and the '
    'explicit review-time policy must pass before decoding. Digests bind content, '
    'not reviewer identity. No current state, authority, gas, effects, liquidity, '
    'future execution or transaction origin is established. Calls are independent. '
    'Nothing is signed or sent.'
)


def decimal(value):
    core.require(isinstance(value, str) and len(value) <= 79 and
                 re.fullmatch(r'0|-?[1-9][0-9]*', value),
                 'bounds require canonical decimal strings (no -0, float or exponent)')
    return int(value)


def guard(value):
    gate.expiry.sets.bounded(value)
    core.require(isinstance(value, dict) and set(value) ==
                 {'schema', 'request_sha256', 'policy_sha256', 'types', 'bounds'},
                 'guard requires exactly schema, request_sha256, policy_sha256, types, bounds')
    core.require(value['schema'] == SCHEMA, 'unsupported return bounds schema')
    for key in ('request_sha256', 'policy_sha256'):
        core.require(isinstance(value[key], str) and
                     re.fullmatch(r'[0-9a-f]{64}', value[key]), 'invalid ' + key)
    types = lens.layout(value['types'])
    core.require(isinstance(value['bounds'], list) and len(value['bounds']) == len(types),
                 'provide one bound for every return value')
    bounds = []
    for kind, bound in zip(types, value['bounds']):
        match = re.fullmatch(r'(uint|int)([0-9]+)', kind)
        core.require(match is not None, 'only explicit uintN and intN types are supported')
        core.require(isinstance(bound, dict) and set(bound) == {'min', 'max'},
                     'each bound requires exactly min and max')
        lower, upper = decimal(bound['min']), decimal(bound['max'])
        width = int(match[2])
        low, high = ((0, 2**width - 1) if match[1] == 'uint' else
                     (-2**(width-1), 2**(width-1) - 1))
        core.require(low <= lower <= upper <= high,
                     'bounds must be ordered and fit the declared integer type')
        bounds.append({'min': str(lower), 'max': str(upper)})
    return {**value, 'types': types, 'bounds': bounds}


def evaluate(evidence, policy, request, selected_guard):
    chosen = guard(selected_guard)
    wanted = gate.request(request)
    policy = gate.expiry.policy(policy)
    report = {'schema': SCHEMA, 'verdict': 'inconclusive', 'reason': '',
              'unsigned_call': None, 'checks': [], 'member_id': wanted['member_id'],
              'guard_sha256': binding.digest(chosen),
              'request_sha256': binding.digest(wanted),
              'policy_sha256': binding.digest(policy), 'limits': LIMITS}
    if any(chosen[key] != report[key] for key in ('request_sha256', 'policy_sha256')):
        report.update(verdict='withheld', reason='guard is bound to a different request or expiry policy')
        return report
    checked = gate.evaluate(evidence, policy, wanted)
    # Do not embed the gate's intermediate unsigned_call in a refused result.
    report['release_gate'] = {'verdict': checked['verdict'], 'reason': checked['reason']}
    if checked['verdict'] != 'ready':
        report.update(verdict=('inconclusive' if checked['verdict'] == 'inconclusive' else 'withheld'),
                      reason='historical release gate is ' + checked['verdict'])
        return report
    report['block'] = checked['reviewed_block']
    try:
        # The gate already checked actual raw bytes equal these exact expected bytes.
        values = lens.decode(checked['expected_return'], chosen['types'])
    except ValueError as exc:
        report['reason'] = 'return layout rejected: ' + str(exc)
        return report
    for index, (decoded, bound) in enumerate(zip(values, chosen['bounds'])):
        passed = int(bound['min']) <= int(decoded['value']) <= int(bound['max'])
        report['checks'].append({'index': index, **decoded, **bound, 'passed': passed})
    if not all(item['passed'] for item in report['checks']):
        report.update(verdict='withheld', reason='at least one numeric return is outside its inclusive bounds')
        return report
    report.update(verdict='ready', reason='complete fresh rehearsal and every declared numeric bound match',
                  unsigned_call=checked['unsigned_call'])
    return report


def demo_inputs():
    return (binding.read_json(HERE.parent / 'rehearsal-set/zto-set-evidence.json'),
            binding.read_json(HERE.parent / 'set-expiry/zto-set-expiry-policy.json'),
            binding.read_json(HERE / 'zto-balance-request.json'),
            binding.read_json(HERE / 'zto-balance-guard.json'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('demo', help='check real historical ZTO balance evidence offline')
    check = commands.add_parser('check', help='check explicit evidence, expiry policy, request and guard JSON')
    for name in ('evidence', 'policy', 'request', 'guard'):
        check.add_argument(name)
    args = parser.parse_args(argv)
    try:
        inputs = demo_inputs() if args.command == 'demo' else tuple(
            binding.read_json(getattr(args, key)) for key in ('evidence', 'policy', 'request', 'guard'))
        result = evaluate(*inputs)
        print(json.dumps(result, indent=2, allow_nan=False))
        return EXIT[result['verdict']]
    except (ValueError, KeyError, TypeError, OSError, RecursionError, core.RPCError) as exc:
        print(json.dumps({'schema': SCHEMA, 'verdict': 'inconclusive',
                          'unsigned_call': None, 'error': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
