# Return Bounds

Check whether every numeric return from one explicitly requested historical
Ethereum call falls within reviewer-declared inclusive limits. The call is
released as an unsigned representation only after the entire independent-call
rehearsal set matches and passes its explicit review-time freshness policy.

From the repository root, with Python 3.10 or later and no dependencies:

```sh
python3 -B line-4/tools/return-bounds/return_bounds.py demo
```

When tried, this returned `ready` for real saved ZTO
`balanceOf(PoolManager)` evidence at block **26,188,241**, with raw integer value
**304756253603277900345322340**. The historical policy declares a review time
3,600 seconds after the block and a 7,200-second window. Replaying that policy
does not assert freshness now. The demo checks a minimum of one raw unit and
the uint256 maximum; these are explicit demonstration bounds, not an owner's
economic requirements. The PoolManager is the actual simulation caller and
queried account; this does not make it an available transaction origin or
measure this particular pool's liquidity.

To check your own saved inputs:

```sh
python3 -B line-4/tools/return-bounds/return_bounds.py check evidence.json policy.json request.json guard.json
```

The evidence, expiry policy and request use the sibling Rehearsal Set, Set
Expiry and Release Gate schemas. Guard JSON has exactly these fields:

- `schema`: `rehearsal-return-bounds-v1`.
- `request_sha256`: digest of the normalized Release Gate request.
- `policy_sha256`: digest of the normalized Set Expiry policy, including its
  exact block, complete plan and review time.
- `types`: 1–32 explicit flat ABI integer types, such as `uint256` or `int24`.
- `bounds`: one `{ "min": "1", "max": "100" }` object per return, in order.
  Both bounds are mandatory, inclusive, canonical decimal strings in the
  corresponding type's range. Integers are raw units; no decimal scaling occurs.

Construct digests with the imported helpers
`binding.digest(gate.request(request))` and
`binding.digest(gate.expiry.policy(policy))`. The canonical digest encoding is
ASCII JSON, sorted keys, separators `(',', ':')`, SHA-256, lowercase hex.
The checked-in balance request and guard show a concrete complete example.
Digests prevent accidental context substitution; they do not authenticate a
reviewer or make the policy trustworthy.

The gate checks observed bytes exactly equal the reviewed bytes before the
inherited Return Lens decodes them. Every tuple position must have a bound and
pass it. Noncanonical ABI padding/sign extension, extra/truncated bytes, missing
set members, changed call context and expired policies prevent release. A failed
numeric bound reports the value and interval but leaves `unsigned_call` null.
Intermediate gate output is summarized without exposing its candidate call.

Exit codes: **0** ready, **1** withheld, **2** inconclusive or invalid input.
Malformed JSON, duplicate keys, non-finite numbers, unknown fields and files
outside the workspace are refused. Input files are limited to 95 KB each.

Focused tests (17 passed locally):

```sh
python3 -B -m unittest discover -s line-4/tools/return-bounds -v
```

Tests include the unchanged real evidence, inclusive limits, failed lower and
upper bounds, signed/unsigned tuple extremes, noncanonical ABI, changed request
and policy, stale and incomplete sets, CLI exits and duplicate JSON keys.
Synthetic payload tests are explicitly labeled in the test code. The demo was
also checked with network calls disabled. All 22 tests in the inherited Release
Gate and Return Lens suites passed.

Uses ordinary committed sibling Python files; keep the `line-4/tools` tree
together. No network, installation, wallet, secret, environment lookup,
signature, transaction submission or new coin is needed. Existing real ZTO-first
and IMD-second set evidence is reused unchanged, with PublicNode attribution and
explicit unverified contributor-relay provenance. Reviewer-supplied ABI types
are not authenticated. Historical integer bounds do not prove present balances,
gas, state effects, authority, price, successful transfer or future inclusion.
