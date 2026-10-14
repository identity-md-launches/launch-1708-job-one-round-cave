"""Offline real-evidence replay and numeric ABI refusal checks."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import return_bounds as tool


class ReturnBoundsTests(unittest.TestCase):
    def setUp(self):
        self.evidence, self.policy, self.request, self.guard = tool.demo_inputs()

    def check(self):
        return tool.evaluate(self.evidence, self.policy, self.request, self.guard)

    def rebind(self):
        self.guard['request_sha256'] = tool.binding.digest(tool.gate.request(self.request))
        self.guard['policy_sha256'] = tool.binding.digest(tool.gate.expiry.policy(self.policy))

    def observed_number(self):
        return int(self.evidence['observations'][1]['observation']['outcome']['result'], 16)

    def synthetic(self, types, values, bounds):
        # Deliberate synthetic return payload; retain real context only as scaffolding.
        raw = '0x' + ''.join((v % 2**256).to_bytes(32, 'big').hex() for v in values)
        self.evidence['observations'][1]['observation']['returns'] = 'raw'
        self.evidence['observations'][1]['observation']['outcome'] = {'result': raw}
        self.policy['plan']['calls'][1]['expected_return'] = raw
        self.guard.update(types=types, bounds=bounds)
        self.rebind()

    def test_real_zto_balance(self):
        result = self.check()
        self.assertEqual(result['verdict'], 'ready')
        self.assertEqual(result['unsigned_call'], self.request['call'])
        self.assertEqual(result['checks'][0]['value'], str(self.observed_number()))
        self.assertEqual(result['block'], self.policy['plan']['block'])

    def test_both_bounds_are_inclusive(self):
        n = str(self.observed_number())
        self.guard['bounds'] = [{'min': n, 'max': n}]
        self.assertEqual(self.check()['verdict'], 'ready')

    def test_below_minimum_and_above_maximum(self):
        n = self.observed_number()
        for lower, upper in ((n+1, n+2), (n-2, n-1)):
            self.guard['bounds'] = [{'min': str(lower), 'max': str(upper)}]
            result = self.check()
            self.assertEqual(result['verdict'], 'withheld')
            self.assertIsNone(result['unsigned_call'])
            self.assertFalse(result['checks'][0]['passed'])
            self.assertNotIn('unsigned_call', result['release_gate'])

    def test_negative_and_unsigned_tuple_extremes(self):
        self.synthetic(['int8', 'uint256'], [-128, 2**256-1],
                       [{'min': '-128', 'max': '-1'}, {'min': '1', 'max': str(2**256-1)}])
        self.assertEqual(self.check()['verdict'], 'ready')
        self.assertEqual(self.check()['checks'][0]['value'], '-128')

    def test_every_tuple_value_must_pass(self):
        self.synthetic(['uint8', 'int16'], [8, -2],
                       [{'min': '8', 'max': '8'}, {'min': '-1', 'max': '1'}])
        result = self.check()
        self.assertEqual(result['verdict'], 'withheld')
        self.assertEqual([c['passed'] for c in result['checks']], [True, False])

    def test_noncanonical_integer_width_and_sign_extension(self):
        for kind, number, bound in [('uint8', 256, {'min': '0', 'max': '255'}),
                                    ('int8', 128, {'min': '-128', 'max': '127'})]:
            self.synthetic([kind], [number], [bound])
            result = self.check()
            self.assertEqual(result['verdict'], 'inconclusive')
            self.assertIsNone(result['unsigned_call'])

    def test_layout_must_consume_all_bytes(self):
        self.synthetic(['uint256'], [1, 2], [{'min': '1', 'max': '2'}])
        self.assertEqual(self.check()['verdict'], 'inconclusive')

    def test_guard_binds_all_request_fields(self):
        for key, value in [('from', tool.core.TOKENS['IMD']), ('to', tool.core.TOKENS['IMD']),
                           ('data', '0x18160ddd'), ('value', '0x1')]:
            old = copy.deepcopy(self.request)
            self.request['call'][key] = value
            self.assertEqual(self.check()['verdict'], 'withheld')
            self.assertIsNone(self.check()['unsigned_call'])
            self.request = old

    def test_rebound_different_call_still_fails_gate(self):
        self.request['call']['to'] = tool.core.TOKENS['IMD']
        self.rebind()
        self.assertEqual(self.check()['release_gate']['verdict'], 'mismatch')

    def test_different_policy_digest_is_withheld(self):
        self.policy['max_age_seconds'] += 1
        self.assertEqual(self.check()['verdict'], 'withheld')

    def test_expired_policy_with_valid_digest_still_fails(self):
        ts = int(self.policy['plan']['block']['timestamp'], 16)
        self.policy['as_of'] = hex(ts + self.policy['max_age_seconds'] + 1)
        self.rebind()
        self.assertEqual(self.check()['release_gate']['verdict'], 'expired')
        self.assertIsNone(self.check()['unsigned_call'])

    def test_missing_or_changed_unselected_member_stops_decode(self):
        old = copy.deepcopy(self.evidence)
        self.evidence['observations'].pop()
        self.assertEqual(self.check()['verdict'], 'inconclusive')
        self.assertEqual(self.check()['checks'], [])
        self.evidence = old
        self.evidence['observations'][0]['observation']['outcome']['result'] = '0x' + '01' * 32
        self.assertEqual(self.check()['verdict'], 'withheld')
        self.assertEqual(self.check()['checks'], [])

    def test_invalid_bounds_and_types(self):
        cases = [(['bool'], [{'min': '0', 'max': '1'}]),
                 (['uint8'], [{'min': '0', 'max': '256'}]),
                 (['int8'], [{'min': '-129', 'max': '1'}]),
                 (['uint256'], []), ([], []),
                 (['uint7'], [{'min': '0', 'max': '1'}]),
                 (['uint8'], [{'min': '2', 'max': '1'}])]
        for types, bounds in cases:
            with self.subTest(types=types, bounds=bounds):
                changed = {**self.guard, 'types': types, 'bounds': bounds}
                with self.assertRaises(ValueError):
                    tool.guard(changed)
        for bad in ['-0', '01', '+1', '1.0', '1e2', 1, True, '1'*80]:
            with self.assertRaises(ValueError):
                tool.guard({**self.guard, 'bounds': [{'min': bad, 'max': '9'}]})

    def test_strict_schema_and_hashes(self):
        for changed in [{**self.guard, 'extra': 1}, {**self.guard, 'schema': 'unknown'},
                        {**self.guard, 'request_sha256': 'not-a-digest'},
                        {**self.guard, 'bounds': [{'min': '1', 'max': '9', 'unit': 'ZTO'}]}]:
            with self.assertRaises(ValueError):
                tool.guard(changed)

    def test_input_immutability(self):
        before = copy.deepcopy((self.evidence, self.policy, self.request, self.guard))
        self.check()
        self.assertEqual(before, (self.evidence, self.policy, self.request, self.guard))

    def test_demo_is_offline(self):
        with patch.object(tool.core.RPC, 'call', side_effect=AssertionError('network forbidden')):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(tool.main(['demo']), 0)
        self.assertEqual(json.loads(out.getvalue())['verdict'], 'ready')

    def test_cli_valid_refusal_and_duplicate_keys(self):
        scratch = Path('test/scratch'); scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            paths = [Path(temp)/f'{name}.json' for name in ('evidence', 'policy', 'request', 'guard')]
            for path, data in zip(paths, (self.evidence, self.policy, self.request, self.guard)):
                path.write_text(json.dumps(data))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(tool.main(['check', *map(str, paths)]), 0)
            self.guard['bounds'][0]['min'] = str(self.observed_number()+1)
            paths[-1].write_text(json.dumps(self.guard))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(tool.main(['check', *map(str, paths)]), 1)
            self.assertIsNone(json.loads(out.getvalue())['unsigned_call'])
            paths[-1].write_text('{"schema":"a","schema":"b"}')
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(tool.main(['check', *map(str, paths)]), 2)
            self.assertIsNone(json.loads(err.getvalue())['unsigned_call'])


if __name__ == '__main__':
    unittest.main()
