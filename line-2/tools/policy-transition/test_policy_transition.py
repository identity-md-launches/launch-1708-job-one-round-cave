"""Synthetic test-only mutations of real ZTO evidence; never saved as chain data."""
import copy
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import policy_transition as tool

BEFORE = tool.gate.load(HERE.parent / 'allowance-lens/observation.json')
AFTER = tool.gate.load(HERE.parent / 'allowance-changes/recheck.json')
POLICY = tool.gate.load(HERE / 'demo-policy.json')


def samples(a=9, b=11, balance=0):
    # Select an actual owner/spender, retaining actual historical block headers.
    actual = next(o for o in AFTER['observations'] if any(
        tool.gate.lens.word(r['result']) > 0 for r in o['raw']['allowances']))
    base = copy.deepcopy(actual)
    entry = next(r for r in base['raw']['allowances'] if tool.gate.lens.word(r['result']) > 0)
    base['query']['spenders'] = [entry['spender']]
    base['raw']['allowances'] = [entry]
    base['raw']['balances'][0]['result'] = '0x' + f'{balance:064x}'
    old, new = copy.deepcopy(base), copy.deepcopy(base)
    old['block'] = copy.deepcopy(BEFORE['block'])
    old['query']['from_block'] = old['query']['to_block'] = int(old['block']['number'], 16)
    old['raw']['allowances'][0]['result'] = '0x' + f'{a:064x}'
    new['raw']['allowances'][0]['result'] = '0x' + f'{b:064x}'
    policy = copy.deepcopy(POLICY)
    policy['pairs'] = [{'owner': entry['owner'], 'spender': entry['spender'],
                        'maximum_allowance_raw': '10'}]
    return old, new, policy


def empty(value):
    value = copy.deepcopy(value)
    value['query'].update(mode='approval_window', spenders=[])
    value['raw']['allowances'] = []
    value['raw']['balances'] = []
    return value


class PolicyTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (Path.cwd() / 'test/scratch').mkdir(parents=True, exist_ok=True)

    def test_real_replay(self):
        result = tool.assess(BEFORE, AFTER, POLICY)
        self.assertEqual(result['decision'], 'deny_measured_pairs')
        self.assertEqual(result['transition_counts'], {'remained_within_limit': 16, 'still_violates': 3})
        self.assertEqual(result['coverage']['compared_pairs'], 19)

    def test_crossing_even_on_empty_balance(self):
        result = tool.assess(*samples(10, 11))
        self.assertEqual(result['pairs'][0]['transition'], 'crossed_above_limit')
        self.assertEqual(result['decision'], 'deny_measured_pairs')

    def test_reduction_still_violates(self):
        result = tool.assess(*samples(20, 11))
        self.assertEqual(result['pairs'][0]['transition'], 'still_violates')
        self.assertEqual(result['pairs'][0]['allowance_change'], 'decreased')

    def test_exact_ceiling_returns_within(self):
        result = tool.assess(*samples(11, 10))
        self.assertEqual(result['pairs'][0]['transition'], 'returned_within_limit')
        self.assertEqual(result['decision'], 'pass_measured_pairs')

    def test_unlisted_has_zero_ceiling(self):
        a, b, p = samples(0, 1)
        p['pairs'] = []
        row = tool.assess(a, b, p)['pairs'][0]
        self.assertEqual(row['after_status'], 'unlisted_active_permission')
        self.assertEqual(row['transition'], 'crossed_above_limit')

    def test_missing_after_is_unknown(self):
        a, b, p = samples(11, 0)
        result = tool.assess(a, empty(b), p)
        self.assertEqual(result['decision'], 'insufficient_evidence')
        self.assertEqual(result['pairs'][0]['transition'], 'not_rechecked')
        self.assertIsNone(result['pairs'][0]['after_allowance_raw'])

    def test_new_measurement_not_crossing(self):
        a, b, p = samples(0, 11)
        result = tool.assess(empty(a), b, p)
        self.assertEqual(result['pairs'][0]['transition'], 'newly_measured_violation')
        self.assertEqual(result['decision'], 'insufficient_evidence')
        b['raw']['allowances'][0]['result'] = '0x' + '0' * 64
        self.assertEqual(tool.assess(empty(a), b, p)['pairs'][0]['transition'],
                         'newly_measured_within_limit')

    def test_missing_both_required(self):
        a, b, p = samples()
        result = tool.assess(empty(a), empty(b), p)
        self.assertEqual(result['pairs'][0]['transition'], 'missing_both')
        self.assertEqual(result['decision'], 'insufficient_evidence')

    def test_empty_policy_and_scan_do_not_pass(self):
        a, b, p = samples()
        p['pairs'] = []
        self.assertEqual(tool.assess(empty(a), empty(b), p)['decision'], 'insufficient_evidence')

    def test_lost_unlisted_pair_blocks_pass(self):
        a, b, p = samples(0, 0)
        p['pairs'] = []
        self.assertEqual(tool.assess(a, empty(b), p)['decision'], 'insufficient_evidence')

    def test_block_interval_controls_both_inputs(self):
        a, b, p = samples(11, 0)
        p['minimum_block'] = int(b['block']['number'], 16)
        result = tool.assess(a, b, p)
        self.assertEqual(result['pairs'][0]['transition'], 'returned_within_limit')
        self.assertEqual(result['decision'], 'insufficient_evidence')

    def test_reverse_chronology_refused(self):
        a, b, p = samples()
        with self.assertRaises(ValueError):
            tool.assess(b, a, p)

    def test_same_block_conflict_refused(self):
        a, b, p = samples()
        a['block'] = copy.deepcopy(b['block'])
        a['query'] = copy.deepcopy(b['query'])
        with self.assertRaises(ValueError):
            tool.assess(a, b, p)

    def test_bad_raw_calldata_refused(self):
        a, b, p = samples()
        b['raw']['allowances'][0]['data'] = '0x'
        with self.assertRaises(ValueError):
            tool.assess(a, b, p)

    def test_wrong_policy_token_refused(self):
        a, b, p = samples()
        p['token_address'] = tool.gate.lens.TOKENS['IMD']
        with self.assertRaises(ValueError):
            tool.assess(a, b, p)

    def test_immutable_and_bound_inputs(self):
        inputs = samples()
        original = copy.deepcopy(inputs)
        first = tool.assess(*inputs)
        self.assertEqual(inputs, original)
        inputs[2]['pairs'][0]['maximum_allowance_raw'] = '11'
        second = tool.assess(*inputs)
        self.assertNotEqual(first['input_sha256']['policy'], second['input_sha256']['policy'])
        self.assertEqual(first['input_sha256']['before'], second['input_sha256']['before'])

    def test_cli_exits(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(tool.main([]), 0)
            self.assertEqual(tool.main(['--before', str(HERE / 'demo-policy.json')]), 1)
            self.assertEqual(tool.main(['--before', str(HERE.parent / 'allowance-lens/observation.json'),
                '--after', str(HERE.parent / 'allowance-changes/recheck.json'),
                '--policy', str(HERE / 'demo-policy.json')]), 3)
        with tempfile.TemporaryDirectory(dir=Path.cwd() / 'test/scratch') as folder:
            paths = [Path(folder) / f'{name}.json' for name in ('before', 'after', 'policy')]
            inputs = samples(11, 10)
            for path, value in zip(paths, inputs):
                path.write_text(json.dumps(value))
            args = [part for name, path in zip(('before', 'after', 'policy'), paths)
                    for part in ('--' + name, str(path))]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main(args), 0)
                inputs[2]['minimum_block'] = int(inputs[1]['block']['number'], 16)
                paths[2].write_text(json.dumps(inputs[2]))
                self.assertEqual(tool.main(args), 4)

    def test_strict_loader(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / 'test/scratch') as folder:
            path = Path(folder) / 'duplicate.json'
            path.write_text('{"schema": 1, "schema": 2}')
            with self.assertRaises(ValueError):
                tool.gate.load(path)
        with self.assertRaises(ValueError):
            tool.gate.load(Path.cwd().parent / 'outside.json')


if __name__ == '__main__':
    unittest.main()
