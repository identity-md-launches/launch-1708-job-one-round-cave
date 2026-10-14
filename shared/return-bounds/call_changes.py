#!/usr/bin/env python3
"""Compare or recheck the same Ethereum call. Read-only; Python standard library."""
import argparse
import json
from pathlib import Path
import re
import sys

import rehearse_core as core

SCHEMA = 'call-changes-v1'
HERE = Path(__file__).resolve().parent
OBSERVATION_KEYS = {'schema', 'source', 'chain_id', 'block', 'call', 'returns',
                    'code_present', 'outcome'}
SUCCESS = {'returned', 'returned_true', 'returned_false'}
LIMITS = (
    'Comparison of provider-reported historical eth_call results, not receipts or state diffs. '
    'Equal return bytes do not prove equal side effects, code, balances, gas use or safety. '
    'No transaction was signed or sent. Files do not authenticate RPC or prove canonicality. '
    'No guarantee of execution at a future block; omitted gas/fee fields use provider defaults.'
)


def validate(observation):
    """Accept only the bounded, explicit ancestor schema; never trust saved interpretations."""
    core.require(isinstance(observation, dict) and set(observation) == OBSERVATION_KEYS,
                 'observation must have exactly the call-rehearsal-v1 fields')
    block = observation['block']
    core.require(isinstance(block, dict) and set(block) == {'number', 'hash', 'timestamp'},
                 'invalid saved block fields')
    outcome = observation['outcome']
    if isinstance(outcome, dict) and 'error' in outcome:
        error = core.RPCError(outcome['error']).error
        core.require(set(error) <= {'code', 'message', 'data'}, 'unknown RPC error fields')
    core.require(len(json.dumps(observation, allow_nan=False).encode()) <= core.LIMIT,
                 'observation exceeds byte limit')
    return core.report(observation)


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        core.require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('non-finite JSON number: ' + value)


def load_observation(path):
    with core.workspace_path(path).open('rb') as handle:
        raw = handle.read(core.LIMIT + 1)
    core.require(len(raw) <= core.LIMIT, 'observation exceeds byte limit')
    result = json.loads(raw, object_pairs_hook=no_duplicates, parse_constant=reject_constant)
    validate(result)
    return result


def save_observation(path, observation):
    validate(observation)
    encoded = json.dumps(observation, indent=2, allow_nan=False).encode() + b'\n'
    core.require(len(encoded) <= core.LIMIT, 'observation exceeds byte limit')
    with core.workspace_path(path).open('xb') as handle:
        handle.write(encoded)


def execution_evidence(observation, result):
    """Separate execution evidence from transport messages and incomplete ABI data."""
    status = result['status']
    if status in SUCCESS:
        return ('returned', result['raw'])
    if status == 'reverted':
        raw = observation['outcome']['error'].get('data')
        if isinstance(raw, str) and re.fullmatch(r'0x(?:[0-9a-fA-F]{2})*', raw):
            return ('reverted', core.data(raw))
        return ('reverted', None)
    return None


def compare(before, after):
    left, right = validate(before), validate(after)
    core.require(left['call'] == right['call'],
                 'cannot compare different target, sender, calldata or value')
    core.require(before['returns'] == after['returns'],
                 'cannot compare different return interpretations')
    a, b = core.header(before['block']), core.header(after['block'])
    number_a, number_b = core.quantity(a['number']), core.quantity(b['number'])
    core.require(number_b >= number_a, 'after block must not precede before block')
    if number_a == number_b:
        core.require(a == b, 'same block number has conflicting hash or timestamp')
    else:
        core.require(a['hash'] != b['hash'], 'different block numbers have the same hash')
        core.require(core.quantity(b['timestamp']) > core.quantity(a['timestamp']),
                     'later block must have a later timestamp')
    report = {
        'schema': SCHEMA, 'chain_id': 1, 'call': left['call'], 'returns': before['returns'],
        'before': {'source': before['source'], 'block': a, 'result': left['result']},
        'after': {'source': after['source'], 'block': b, 'result': right['result']},
        'blocks_apart': number_b - number_a,
        'seconds_apart': core.quantity(b['timestamp']) - core.quantity(a['timestamp']),
        'same_block': number_a == number_b,
        'same_provider': before['source'] == after['source'],
        'limits': LIMITS,
    }
    x = execution_evidence(before, left['result'])
    y = execution_evidence(after, right['result'])
    if x is None or y is None:
        verdict, reason = 'inconclusive', 'RPC failure or return bytes outside the selected ABI type'
    elif x[0] != y[0]:
        verdict, reason = 'changed', 'execution changed between return and revert'
    elif x[0] == 'reverted' and (x[1] is None or y[1] is None):
        verdict, reason = 'inconclusive', 'both calls reverted but at least one lacks revert bytes'
    elif x == y:
        verdict, reason = 'unchanged', 'same execution category and exact return or revert bytes'
    else:
        verdict, reason = 'changed', 'return or revert bytes differ'
    if report['same_block'] and verdict == 'changed':
        verdict, reason = 'inconsistent_observations', 'same call and block produced conflicting evidence'
    report.update(verdict=verdict, reason=reason)
    if before['returns'] == 'uint256' and x and y and x[0] == y[0] == 'returned':
        report['uint256_delta'] = str(int(right['result']['uint256']) - int(left['result']['uint256']))
    return report


def block_selector(value):
    if value == 'finalized':
        return value
    return hex(core.quantity(value))


def capture(rpc, tx, returns, block='finalized'):
    """Rehearse at a requested finalized height, with all state reads hash-pinned."""
    tx = core.transaction(tx)
    core.require(returns in ('raw', 'bool', 'uint256'), 'unsupported return interpretation')
    block = block_selector(block)
    core.require(rpc.call('eth_chainId', []) == '0x1', 'expected Ethereum mainnet')
    finalized = core.header(rpc.call('eth_getBlockByNumber', ['finalized', False]))
    chosen = finalized
    if block != 'finalized':
        core.require(core.quantity(block) <= core.quantity(finalized['number']),
                     'requested block is newer than the finalized head')
        chosen = core.header(rpc.call('eth_getBlockByNumber', [block, False]))
        core.require(chosen['number'] == block, 'provider returned the wrong requested block')
        if block == finalized['number']:
            core.require(chosen == finalized, 'finalized header changed during selection')
        else:
            core.require(chosen['hash'] != finalized['hash'] and
                         core.quantity(chosen['timestamp']) < core.quantity(finalized['timestamp']),
                         'historical header conflicts with the finalized head')
    pin = {'blockHash': chosen['hash'], 'requireCanonical': True}
    code = core.data(rpc.call('eth_getCode', [tx['to'], pin]))
    core.require(code != '0x', 'target has no code; empty EOA call is not a rehearsal')
    try:
        outcome = {'result': core.data(rpc.call('eth_call', [tx, pin]))}
    except core.RPCError as exc:
        outcome = {'error': exc.error}
    after = core.header(rpc.call('eth_getBlockByNumber', [chosen['number'], False]))
    core.require(chosen == after, 'block changed during rehearsal; discard and retry')
    observation = {'schema': core.SCHEMA, 'source': rpc.endpoint, 'chain_id': 1,
                   'block': chosen, 'call': tx, 'returns': returns,
                   'code_present': True, 'outcome': outcome}
    validate(observation)
    return observation


def exit_code(report):
    return {'unchanged': 0, 'changed': 1, 'inconclusive': 2,
            'inconsistent_observations': 2}[report['verdict']]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='mode', required=True)
    commands.add_parser('demo', help='offline comparison of the two supplied real ZTO observations')
    cmd = commands.add_parser('compare', help='compare two saved Call Rehearsal observations offline')
    cmd.add_argument('before')
    cmd.add_argument('after')
    cmd = commands.add_parser('recheck', help='repeat exactly the saved call against public Ethereum')
    cmd.add_argument('before')
    cmd.add_argument('--rpc', choices=core.ENDPOINTS, default=core.ENDPOINTS[0])
    cmd.add_argument('--block', default='finalized', help='finalized or canonical hexadecimal block number')
    cmd.add_argument('--save', help='new workspace path for the raw after observation; never overwritten')
    args = parser.parse_args(argv)
    try:
        if args.mode == 'demo':
            before = load_observation(HERE / 'zto-before.json')
            after = load_observation(HERE / 'zto-after.json')
        else:
            before = load_observation(args.before)
            if args.mode == 'compare':
                after = load_observation(args.after)
            else:
                block = block_selector(args.block)
                if block != 'finalized':
                    core.require(core.quantity(block) >= core.quantity(before['block']['number']),
                                 'after block must not precede before block')
                destination = core.workspace_path(args.save) if args.save else None
                if destination:
                    core.require(not destination.exists(), 'save destination already exists')
                    core.require(destination.parent.is_dir(), 'save parent directory does not exist')
                after = capture(core.RPC(args.rpc), before['call'], before['returns'], block)
        result = compare(before, after)
        if args.mode == 'recheck' and args.save:
            save_observation(args.save, after)
        print(json.dumps(result, indent=2, allow_nan=False))
        return exit_code(result)
    except (ValueError, KeyError, TypeError, OSError, RecursionError, core.RPCError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
