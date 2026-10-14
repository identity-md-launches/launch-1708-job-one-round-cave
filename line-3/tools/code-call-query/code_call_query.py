#!/usr/bin/env python3
"""Query exact proof-backed call offsets, including calls beyond the preview cap."""
import argparse
import json
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / 'code-call-routes'))
import code_call_routes as joined

calls, routes = joined.calls, joined.routes


def query(code, pcs):
    """Pure byte analysis; this helper alone does not verify any proof."""
    pcs = list(pcs)
    calls.lens.require(pcs, 'at least one query PC is required')
    scanned = calls.scan(code, pcs)
    structural = routes.scan(code, pcs)
    decoded = {pc: op for pc, op, _, _ in routes.surface.instructions(code)}
    results = []
    for pc, hit, route in zip(pcs, scanned['queried_calls'], structural['queried_pcs']):
        kind = ('call-instruction' if hit is not None else
                'outside-runtime' if pc >= len(code) else
                'push-operand-byte' if pc not in decoded else 'non-call-instruction')
        results.append({'pc': pc, 'kind': kind, 'route_status': route['route_status'],
                        'in_recognized_metadata': route['in_recognized_metadata'],
                        'opcode_byte': '0x%02x' % decoded[pc] if pc in decoded else None,
                        'call': hit})
    return {'call_instruction_count': scanned['call_instruction_count'],
            'preview_limit': calls.PREVIEW,
            'calls_omitted_from_default_preview': scanned['omitted_call_count'],
            'query_count': len(results), 'queries': results}


def inspect(bundle, runtime_address, pcs, anchor_hash=None):
    # Reject every invalid account, runtime or header before releasing any finding.
    checked = calls.proof.verify(bundle, anchor_hash)
    address = calls.lens.address(runtime_address)
    code = None
    for node in bundle['observation']['nodes']:
        for item in (node, node.get('beacon')):
            if item is not None and calls.lens.address(item['address']) == address:
                candidate = calls.lens.code_bytes(item['code'])
                calls.lens.require(code is None or candidate == code, 'conflicting runtime')
                code = candidate
    calls.lens.require(code is not None, 'requested runtime is not present in verified bundle')
    return {'schema': 'code-call-query-result-v1', 'chain_id': 1,
            'target': checked['target'], 'runtime_address': address,
            'runtime_code_hash': calls.lens.digest(code), 'runtime_bytes': len(code),
            'code_block': calls.ancestry.block_identity(bundle['observation']['block']),
            'proof': checked, **query(code, pcs),
            'route_model': 'legacy-evm-adjacent-push-v1',
            'reachability_verified': False, 'external_target_code_verified': False,
            'anchor_authenticity_verified': False, 'semantic_safety_verified': False,
            'scope': 'Selected offsets in full proven historical runtime only. Queries bypass '
                     'the 64-call preview without rebasing PC or CODESIZE. Non-call and PUSH '
                     'data offsets have null call details. Constants depend on successful '
                     'linear segment execution; structural paths may be infeasible and '
                     'dynamic jumps admit all JUMPDESTs. Metadata remains included. '
                     'No execution, dependency completeness, external target identity, '
                     'source/ABI meaning, current state, consensus, finality, anchor '
                     'authenticity, safety or authority to transact is verified.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--runtime', required=True, help='address present in the raw proof bundle')
    parser.add_argument('--pc', required=True, action='append', type=lambda s: int(s, 0),
                        help='decimal or 0x offset; repeat up to 32 distinct offsets')
    parser.add_argument('--anchor-hash')
    args = parser.parse_args()
    try:
        result = inspect(calls.ancestry.read_json(args.bundle), args.runtime, args.pc, args.anchor_hash)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError, OverflowError, AttributeError,
            IndexError, RecursionError) as error:
        print('Code Call Query: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
