"""Offline ZTO-first, IMD-second replay using real historical raw proofs."""
import json
from pathlib import Path
import code_call_query as tool


def main():
    results = []
    for token, address, pcs in (('zto', tool.calls.lens.ZTO, [0]),
                                 ('imd', tool.calls.lens.IMD, [12834])):
        bundle = tool.calls.ancestry.read_json(
            Path(__file__).resolve().parents[1] / 'code-routes' / (token + '-proof.json'))
        results.append({'token': token.upper(), 'result': tool.inspect(bundle, address, pcs)})
    zto, imd = [item['result'] for item in results]
    hit = imd['queries'][0]
    passed = (zto['call_instruction_count'] == 0 and zto['queries'][0]['call'] is None
              and imd['call_instruction_count'] == 12
              and hit['call']['opcode'] == 'STATICCALL'
              and hit['call']['target_address'] == '0x1a44076050125825900e736c501f859c50fe728c'
              and hit['route_status'] == 'dynamic-target-candidate'
              and all(item['result']['proof']['state_inclusion_verified'] for item in results))
    return {'demonstration_passed': passed, 'results': results,
            'note': 'Historical proof replay; the measured call target is not a verified dependency.'}


if __name__ == '__main__':
    result = main()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['demonstration_passed'] else 1)
