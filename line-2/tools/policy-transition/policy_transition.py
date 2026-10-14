#!/usr/bin/env python3
"""Compare historical measured permissions under one explicit allowance policy."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'permission-gate'))
import permission_gate as gate


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def assess(before, after, specification):
    # Revalidate raw ABI words, chronology and same-height conflicts first.
    difference = gate.changes.compare(before, after)
    old = gate.evaluate(before, specification)
    new = gate.evaluate(after, specification)
    old_rows = {(r['owner'], r['spender']): r for r in old['pairs']}
    new_rows = {(r['owner'], r['spender']): r for r in new['pairs']}
    changes = {(r['owner'], r['spender']): r for r in difference['pairs']}
    rows = []
    for pair in sorted(set(old_rows) | set(new_rows)):
        a, b = old_rows.get(pair), new_rows.get(pair)
        a_measured = a is not None and a['allowance_raw'] is not None
        b_measured = b is not None and b['allowance_raw'] is not None
        a_bad = a_measured and a['status'] != 'within_limit'
        b_bad = b_measured and b['status'] != 'within_limit'
        if not a_measured and not b_measured:
            transition = 'missing_both'
        elif not b_measured:
            transition = 'not_rechecked'
        elif not a_measured:
            transition = 'newly_measured_violation' if b_bad else 'newly_measured_within_limit'
        elif a_bad and b_bad:
            transition = 'still_violates'
        elif b_bad:
            transition = 'crossed_above_limit'
        elif a_bad:
            transition = 'returned_within_limit'
        else:
            transition = 'remained_within_limit'
        reference = b if b is not None else a
        rows.append({
            'owner': pair[0], 'spender': pair[1], 'transition': transition,
            'explicit_policy_pair': reference['explicit_policy_pair'],
            'maximum_allowance_raw': reference['maximum_allowance_raw'],
            'before_status': 'missing_evidence' if not a_measured else a['status'],
            'after_status': 'missing_evidence' if not b_measured else b['status'],
            'before_allowance_raw': None if not a_measured else a['allowance_raw'],
            'after_allowance_raw': None if not b_measured else b['allowance_raw'],
            'allowance_change': changes[pair]['change'] if pair in changes else 'unmeasured',
        })
    sufficient = (old['decision'] != 'insufficient_evidence'
                  and new['decision'] != 'insufficient_evidence'
                  and difference['coverage']['all_previous_pairs_rechecked'])
    return {
        'schema': 'permission-policy-transition-v1',
        'decision': 'insufficient_evidence' if not sufficient else (
            'deny_measured_pairs' if new['violating_pair_count'] else 'pass_measured_pairs'),
        'chain_id': new['chain_id'], 'token': new['token'], 'token_address': new['token_address'],
        'decimals': difference['decimals'], 'complete_wallet_audit': False,
        'before_block': difference['before_block'], 'after_block': difference['after_block'],
        'before_policy_decision': old['decision'], 'after_policy_decision': new['decision'],
        'policy_block_interval': {'minimum': specification['minimum_block'],
                                  'maximum': specification['maximum_block']},
        'coverage': difference['coverage'], 'transition_counts': dict(sorted(Counter(
            row['transition'] for row in rows).items())),
        'pairs': rows,
        'input_sha256': {'before': fingerprint(before), 'after': fingerprint(after),
                         'policy': fingerprint(specification)},
        'limitations': [
            'One unchanged explicit policy is applied to both historical inventories; no policy authority is inferred.',
            'Transitions describe measured allowances only; newly measured is not newly approved.',
            'Missing evidence is unknown, never a revocation or a returned-within-limit result.',
            'Both blocks must fit the policy interval and all old pairs must be rechecked for an overall pass.',
            'A reduction may still violate a ceiling, including on an empty balance.',
            'Rows outside the policy interval remain historical diagnostics; overall evidence is insufficient.',
            'No current state, complete-wallet safety, state proof, cause, Permit2 or signature coverage is claimed.',
            'No transaction is prepared, signed or sent. This tool operates offline.',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', help='workspace raw permission observation/inventory')
    parser.add_argument('--after', help='workspace later raw permission observation/inventory')
    parser.add_argument('--policy', help='workspace permission-gate-policy-v1 JSON')
    args = parser.parse_args(argv)
    try:
        supplied = [args.before, args.after, args.policy]
        gate.lens.require(all(v is None for v in supplied) or all(v is not None for v in supplied),
                          'provide --before, --after and --policy together, or none for the demo')
        demo = args.before is None
        result = assess(
            gate.load(args.before or HERE.parent / 'allowance-lens/observation.json'),
            gate.load(args.after or HERE.parent / 'allowance-changes/recheck.json'),
            gate.load(args.policy or HERE / 'demo-policy.json'))
        result['demonstration'] = demo
        print(json.dumps(result, indent=2))
        if demo or result['decision'] == 'pass_measured_pairs':
            return 0
        return 4 if result['decision'] == 'insufficient_evidence' else 3
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
