"""Boundary, provenance and full-runtime query checks; synthetic bytes are tests only."""
import copy
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch
import code_call_query as tool

FOLDER = Path(__file__).resolve().parent


def evidence(token='imd'):
    return tool.calls.ancestry.read_json(FOLDER.parent / 'code-routes' / (token + '-proof.json'))


class QueryTests(unittest.TestCase):
    def test_real_proof_demo_offline(self):
        import demo
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            self.assertTrue(demo.main()['demonstration_passed'])

    def test_beyond_preview_and_original_codesize(self):
        # Last call uses CODESIZE as its target. Slicing a suffix would be wrong.
        code = bytes.fromhex('60015afa50') * 100 + bytes.fromhex('385afa')
        pc = len(code) - 1
        old = tool.calls.scan(code)
        self.assertEqual(len(old['call_preview']), 64)
        hit = tool.query(code, [pc])['queries'][0]
        self.assertEqual(hit['kind'], 'call-instruction')
        self.assertEqual(int(hit['call']['target_word'], 16), len(code))
        self.assertEqual(hit['call']['pc'], pc)
        self.assertEqual(tool.query(code, [pc])['calls_omitted_from_default_preview'], 37)

    def test_original_pc_not_rebased(self):
        code = b'\x5b' * 200 + bytes.fromhex('585afa')
        hit = tool.query(code, [202])['queries'][0]['call']
        self.assertEqual(int(hit['target_word'], 16), 200)

    def test_classifies_non_calls_data_and_outside(self):
        code = bytes.fromhex('63f1f2f4fa00')
        result = tool.query(code, [0, 1, 5, 6])['queries']
        self.assertEqual([r['kind'] for r in result],
                         ['non-call-instruction', 'push-operand-byte',
                          'non-call-instruction', 'outside-runtime'])
        self.assertTrue(all(r['call'] is None for r in result))
        self.assertIsNone(result[1]['opcode_byte'])

    def test_unresolved_and_excluded_are_retained(self):
        result = tool.query(bytes.fromhex('005afa'), [2])['queries'][0]
        self.assertEqual(result['route_status'], 'excluded-by-model')
        self.assertEqual(result['call']['target_status'], 'unresolved')
        self.assertIsNone(result['call']['target_address'])

    def test_validation_and_order(self):
        for pcs in ([], [1, 1], [True], [-1], [24576], list(range(33)), ['2']):
            with self.assertRaises(ValueError):
                tool.query(bytes.fromhex('5afa'), pcs)
        self.assertEqual([r['pc'] for r in tool.query(b'\x5b' * 32, [31, 0])['queries']], [31, 0])
        self.assertEqual(len(tool.query(b'\x5b' * 32, range(32))['queries']), 32)
        with self.assertRaises(ValueError):
            tool.query(b'\xef\x01\x00', [0])

    def test_invalid_proof_precedes_query(self):
        for mutation in ('header', 'proof', 'runtime'):
            bundle = evidence()
            if mutation == 'header':
                bundle['header_rlp'] = bundle['header_rlp'][:-2] + 'ff'
            elif mutation == 'proof':
                bundle['proofs'][0]['accountProof'].pop()
            else:
                bundle['observation']['nodes'][0]['code'] = '0x00'
            with patch.object(tool, 'query', side_effect=AssertionError('query ran before verification')):
                with self.assertRaises(ValueError):
                    tool.inspect(bundle, tool.calls.lens.IMD, [12834])

    def test_anchor_and_runtime_binding(self):
        bundle = evidence()
        with self.assertRaises(ValueError):
            tool.inspect(bundle, tool.calls.lens.ZTO, [0])
        with self.assertRaises(ValueError):
            tool.inspect(bundle, tool.calls.lens.IMD, [12834], '0x' + '11' * 32)
        result = tool.inspect(bundle, tool.calls.lens.IMD, [12834], bundle['observation']['block']['hash'])
        self.assertEqual(result['proof']['anchor'], 'caller-supplied-block-hash')
        self.assertFalse(result['anchor_authenticity_verified'])
        self.assertFalse(result['external_target_code_verified'])

    def test_input_unchanged(self):
        bundle = evidence()
        before = copy.deepcopy(bundle)
        tool.inspect(bundle, tool.calls.lens.IMD, [12834])
        self.assertEqual(bundle, before)

    def test_metadata_call_annotation(self):
        bundle = evidence()
        prior = tool.calls.inspect(bundle)['runtimes'][0]['call_preview'][-1]
        result = tool.inspect(bundle, tool.calls.lens.IMD, [prior['pc']])['queries'][0]
        self.assertTrue(result['in_recognized_metadata'])
        self.assertEqual(result['call'], prior)

    def test_queries_match_existing_preview_randomized(self):
        rng = random.Random(35)
        checked = 0
        for _ in range(100):
            code = bytes(rng.randrange(256) for _ in range(250))
            if code[0] == 0xef:
                continue
            old = tool.calls.scan(code)
            pcs = [hit['pc'] for hit in old['call_preview']][:32]
            if pcs:
                result = tool.query(code, pcs)
                self.assertEqual([r['call'] for r in result['queries']], old['call_preview'][:32])
                checked += 1
            self.assertNotIn('queried_calls', old)
        self.assertGreater(checked, 50)

    def test_cli_success_and_empty_stdout_on_refusal(self):
        command = [sys.executable, '-B', str(FOLDER / 'code_call_query.py'), '--bundle',
                   str(FOLDER.parent / 'code-routes/imd-proof.json'), '--runtime',
                   tool.calls.lens.IMD, '--pc', '12834']
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['queries'][0]['kind'], 'call-instruction')
        for tail in (['--pc', '12834'], ['--anchor-hash', 'bad']):
            result = subprocess.run(command + tail, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
