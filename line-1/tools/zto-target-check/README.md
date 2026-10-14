# ZTO Target Check

Verify a transferred ZTO/IMD minimum-input claim against its liquidity snapshot and a receiver's separately supplied policy. Python 3.10+, standard library only. Keep the ordinary committed sibling Target, Capacity, Review, Sizes, Path and Band folders. No install or network is needed.

One command from the repository root:

```sh
python3 -B line-1/tools/zto-target-check/zto_target_check.py --demo
```

The demo recomputes the bundled claim using real historical Ethereum pool evidence at block **26,184,260**. It returns `accepted`, minimum input **6.605354095186351266 ZTO**, rounded planning minimum **0.0001 IMD**, and a direct predecessor minimum of **0.000099999999999999 IMD**. The demo policy explicitly permits a ten-block historical age and 100-bps tolerance; these are demonstration choices, not recommendations or a current freshness claim. `demo-result.json` records this run. Nine focused tests passed, including altered amounts, tolerance, direction, target, ceiling, anchor, expiry, added transaction data, unreachable targets and input immutability.

For your own evidence and receiver policy:

```sh
python3 -B line-1/tools/zto-target-check/zto_target_check.py --snapshot line-1/tools/zto-path/observation.json --claim line-1/tools/zto-target-check/demo-claim.json --policy line-1/tools/zto-target-check/demo-policy.json
```

Replace the three paths with your own workspace files. The receiver must choose the policy independently rather than accepting one supplied by the claim's sender. Policy fields are exactly those in `demo-policy.json`: schema, canonical snapshot SHA-256, anchored block number/hash, reference block, inclusive maximum age in blocks, input token, output target, input ceiling and tolerance. Decimal amounts are strings in token units; block/age/tolerance values are integers. The schema is `zto-target-check-policy-v1`.

The checker validates the supplied pool evidence and numeric controls, runs the existing target search under the receiver's choices, and compares every report field with type-sensitive equality. Digests, raw amounts, unit displays, coverage and predecessor results must match; additional fields are refused. An exact complete `target_reached` claim within the receiver's anchor/age policy releases a compact `verified_bound`. Any mismatch or non-reached target yields `withheld`, null bound, and exit 2; malformed input yields exit 1. No claim values are copied into the released bound. Files use the ancestor's bounded workspace-only strict JSON reader, including duplicate-key and floating-number refusal.

This binds supplied historical RPC evidence, not consensus authenticity, provider independence, present liquidity or future inclusion. Age depends on the receiver's explicit reference block. Arithmetic reuses Target/Capacity/Path, so this is evidence recomputation rather than an independent implementation. Minimum output is a planning amount, not an enforced receipt; settlement, transfer behavior, gas and MEV remain outside scope. No recipient, router, calldata, signature or transaction is produced.

Tests:

```sh
python3 -B -m unittest discover -s line-1/tools/zto-target-check -p 'test_*.py' -v
```
