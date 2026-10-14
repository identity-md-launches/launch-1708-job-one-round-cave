import copy
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('check', HERE / 'zto_target_check.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class CheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.obs = c.review.read_json(c.target.DEFAULT_SNAPSHOT)
        cls.claim = c.review.read_json(HERE / 'demo-claim.json')
        cls.policy = c.review.read_json(HERE / 'demo-policy.json')

    def check(self, claim=None, policy=None):
        return c.verify(self.obs, self.claim if claim is None else claim,
                        self.policy if policy is None else policy)

    def test_real_historical_minimum(self):
        r = self.check()
        self.assertEqual(r['status'], 'accepted')
        self.assertEqual(r['verified_bound']['minimum_input_raw'], '6605354095186351266')
        self.assertEqual(r['age_blocks'], 10)

    def test_claim_tampering_never_releases(self):
        for key, value in [('minimum_input_raw', '6605354095186351267'),
                           ('planning_minimum_output_raw', '100000000000001'),
                           ('previous_minimum_output_raw', '100000000000000'),
                           ('slippage_bps', True), ('scope', 'guaranteed receipt')]:
            claim = copy.deepcopy(self.claim)
            claim[key] = value
            r = self.check(claim=claim)
            self.assertEqual(r['status'], 'withheld')
            self.assertIsNone(r['verified_bound'])

    def test_added_transaction_field_refused(self):
        claim = dict(self.claim, transaction={})
        self.assertEqual(self.check(claim=claim)['status'], 'withheld')

    def test_receiver_choices_are_binding(self):
        for key, value in [('target_output', '0.0002'), ('ceiling_input', '9'),
                           ('slippage_bps', 50), ('input_token', 'IMD')]:
            policy = dict(self.policy, **{key: value})
            self.assertEqual(self.check(policy=policy)['status'], 'withheld')

    def test_anchor_and_age_refusals(self):
        for key, value, reason in [
            ('snapshot_sha256', 'a' * 64, 'snapshot_digest_mismatch'),
            ('block_hash', '0x' + 'b' * 64, 'block_anchor_mismatch'),
            ('block_number', self.policy['block_number'] + 1, 'block_anchor_mismatch'),
            ('reference_block', self.policy['block_number'] - 1, 'snapshot_after_reference'),
            ('max_age_blocks', 9, 'snapshot_too_old_for_policy')]:
            r = self.check(policy=dict(self.policy, **{key: value}))
            self.assertIn(reason, r['reasons'])
            self.assertIsNone(r['verified_bound'])

    def test_unreachable_claim_is_not_a_bound(self):
        policy = dict(self.policy, ceiling_input='1')
        claim = c.target.find_target(self.obs, 'ZTO', '0.0001', '1', 100)
        r = self.check(claim=claim, policy=policy)
        self.assertIn('target_not_reached', r['reasons'])
        self.assertEqual(r['differences'], [])
        self.assertIsNone(r['verified_bound'])

    def test_strict_policy_validation(self):
        for policy in [dict(self.policy, unexpected=1),
                       dict(self.policy, reference_block=True),
                       dict(self.policy, max_age_blocks=-1),
                       dict(self.policy, slippage_bps=True),
                       dict(self.policy, target_output='0')]:
            with self.assertRaises(ValueError):
                self.check(policy=policy)

    def test_reverse_direction(self):
        policy = dict(self.policy, input_token='IMD', target_output='1', ceiling_input='100')
        claim = c.target.find_target(self.obs, 'IMD', '1', '100', 100)
        r = self.check(claim=claim, policy=policy)
        self.assertEqual(r['status'], 'accepted')
        self.assertEqual(r['verified_bound']['output_token'], 'ZTO')

    def test_inputs_unchanged(self):
        before = copy.deepcopy((self.obs, self.claim, self.policy))
        self.check()
        self.assertEqual((self.obs, self.claim, self.policy), before)


if __name__ == '__main__':
    unittest.main()
