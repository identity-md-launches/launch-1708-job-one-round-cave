#!/usr/bin/env python3
"""Recheck a minimum-input claim against evidence and a receiver's own policy."""
import argparse
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'zto-target'))
import zto_target as target
review = target.review
KEYS = {'schema', 'snapshot_sha256', 'block_number', 'block_hash',
        'reference_block', 'max_age_blocks', 'input_token', 'target_output',
        'ceiling_input', 'slippage_bps'}


def verify(observation, claim, policy):
    require = target.path.z.require
    require(type(policy) is dict and set(policy) == KEYS, 'policy fields mismatch')
    require(policy['schema'] == 'zto-target-check-policy-v1', 'wrong policy schema')
    for key, pattern in (('snapshot_sha256', '[0-9a-f]{64}'),
                         ('block_hash', '0x[0-9a-f]{64}')):
        require(type(policy[key]) is str and re.fullmatch(pattern, policy[key]) is not None,
                'invalid ' + key)
    for key in ('block_number', 'reference_block', 'max_age_blocks'):
        require(type(policy[key]) is int and 0 <= policy[key] < 1 << 64,
                key + ' must be uint64')
    # Always validate both evidence and numeric choices, even if the anchor fails.
    expected = target.find_target(observation, policy['input_token'],
                                  policy['target_output'], policy['ceiling_input'],
                                  policy['slippage_bps'])
    number = int(expected['block']['number'], 16)
    age = policy['reference_block'] - number
    reasons = []
    if expected['snapshot_sha256'] != policy['snapshot_sha256']:
        reasons.append('snapshot_digest_mismatch')
    if number != policy['block_number'] or expected['block']['hash'] != policy['block_hash']:
        reasons.append('block_anchor_mismatch')
    if age < 0:
        reasons.append('snapshot_after_reference')
    elif age > policy['max_age_blocks']:
        reasons.append('snapshot_too_old_for_policy')
    differences = review.differences(claim, expected)
    if differences:
        reasons.append('claim_recomputation_mismatch')
    if expected['status'] != 'target_reached':
        reasons.append('target_not_reached')
    result = {'schema': 'zto-target-check-result-v1',
              'status': 'withheld' if reasons else 'accepted',
              'snapshot_sha256': review.digest(observation),
              'claim_sha256': review.digest(claim), 'policy_sha256': review.digest(policy),
              'age_blocks': age, 'reasons': reasons, 'differences': differences,
              'verified_bound': None,
              'limitations': [
                  'Receiver policy and reference block are supplied trust inputs.',
                  'Digests bind supplied historical RPC evidence, not consensus authenticity or current state.',
                  'Reuses Target/Capacity/Path arithmetic, not an independent numerical implementation.',
                  'No transaction, settlement, transfer, gas or MEV guarantee.']}
    if not reasons:
        result['verified_bound'] = {key: expected[key] for key in (
            'chain_id', 'pool_id', 'block', 'input_token', 'output_token',
            'target_output_raw', 'minimum_input_raw', 'estimated_output_raw',
            'planning_minimum_output_raw', 'previous_input_raw',
            'previous_minimum_output_raw', 'slippage_bps')}
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--snapshot')
    parser.add_argument('--claim')
    parser.add_argument('--policy')
    args = parser.parse_args(argv)
    try:
        if args.demo:
            if args.snapshot or args.claim or args.policy:
                raise ValueError('--demo refuses custom files')
            snapshot, claim, policy = target.DEFAULT_SNAPSHOT, HERE / 'demo-claim.json', HERE / 'demo-policy.json'
        else:
            if not all((args.snapshot, args.claim, args.policy)):
                raise ValueError('provide --snapshot, --claim and receiver --policy, or --demo')
            snapshot, claim, policy = args.snapshot, args.claim, args.policy
        result = verify(review.read_json(snapshot), review.read_json(claim), review.read_json(policy))
        result['mode'] = 'historical_demo' if args.demo else 'receiver_policy'
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result['status'] == 'accepted' else 2
    except (ValueError, KeyError, TypeError, AttributeError, OSError, OverflowError, RecursionError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
