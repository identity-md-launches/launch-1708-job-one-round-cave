# Permission Policy Transition

Compare two raw ERC-20 permission inventories against **one unchanged explicit allowance policy**. This gives an unfamiliar worker a review queue for ceiling crossings, persistent violations, and permissions that returned within the ceiling. A decreasing allowance can still violate policy; an empty balance does not remove that violation.

From the repository root, run this offline demonstration:

```sh
python3 -B line-2/tools/policy-transition/policy_transition.py
```

Python 3.10+ and its standard library suffice. The included sibling Permission Gate, Allowance Changes and Allowance Lens sources are required and shipped as ordinary files. There is no network access or installation. The tool only reads workspace JSON and prints a report; it prepares no transactions.

When tried, the demo revalidated **real historical ZTO evidence** at Ethereum blocks **26,183,751** and **26,184,324**. All **19** previous pairs were rechecked: **three still violate** the illustrative deny-all policy and **sixteen remained within** its zero ceiling. The result is `deny_measured_pairs`; the explicitly labelled demonstration exits 0. No new on-chain observation or current-state claim is made. Saved output is `example-report.json`. Eighteen focused tests passed, including ceiling equality, increases on empty balances, reductions still above the limit, lost and newly measured pairs, empty inventories, chronology, corrupt calldata, wrong token, input immutability, strict loading and CLI exits.

For an actual historical policy evaluation, provide all three inputs:

```sh
python3 -B line-2/tools/policy-transition/policy_transition.py --before line-2/tools/allowance-lens/observation.json --after line-2/tools/allowance-changes/recheck.json --policy line-2/tools/policy-transition/demo-policy.json
```

This command exits **3** because the measured permissions violate that policy. Supply your own raw inventories and explicit policy for your review. Policy fields follow [Permission Gate](../permission-gate/README.md): Ethereum chain 1, real ZTO first or IMD, inclusive block interval, and at most 64 explicit owner/spender pairs with canonical uint256 ceilings in token base units. Unlisted measured pairs have a zero ceiling. Every policy pair must be measured in both inputs. Both blocks must fall in the policy interval, and every previously measured pair must be rechecked for the overall decision to pass. Inputs are workspace files, each at most 96 KiB; duplicate JSON keys are rejected. Derived reports are not evidence.

| Exit | Meaning |
| --- | --- |
| 0 | Measured pairs pass, or the labelled default demo completed |
| 1 | Invalid input or file failure |
| 2 | Argument syntax error |
| 3 | Later measured permissions violate policy |
| 4 | Either inventory is insufficient, outside the interval, or loses prior coverage |

`crossed_above_limit` and `returned_within_limit` require measurements in both inputs. A newly measured pair is labelled `newly_measured_violation` or `newly_measured_within_limit`, never newly approved or newly cleared. Missing pairs retain null amounts and `not_rechecked` or `missing_both`. Diagnostic transitions are still shown if a block is outside the interval, but the overall decision is `insufficient_evidence`. Canonical JSON SHA-256 fingerprints bind the supplied evidence and policy semantically; these are not raw-file hashes or authentication.

These are trusted historical RPC measurements under standard ERC-20 assumptions. Policy authority, present canonicality, wall-clock freshness, future execution, spender trust, complete-wallet safety, unknown spenders, Permit2, unused signatures and custom authorization are outside coverage. A returned-within-limit result does not establish whether spending, revocation or another cause reduced the allowance. A block interval is reviewer-selected and does not make historical evidence current. Even a pass can coexist with a newly measured zero-allowance pair; its transition remains explicit.

Run the focused checks from the repository root:

```sh
python3 -B -m unittest discover -s line-2/tools/policy-transition -p 'test_*.py' -v
```

Test mutations are synthetic, stay in memory or `test/scratch/`, and are never delivered as chain evidence.
