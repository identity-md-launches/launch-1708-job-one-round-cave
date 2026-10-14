# Shared Return Bounds

This shared copy extends the existing `shared/release-gate` with Line 4's
numeric return guard. It releases the selected unsigned call only when the
complete, fresh rehearsal set matches and every returned integer meets the
reviewer's inclusive bounds. ABI types and raw integer limits remain explicit
reviewer inputs.

From the repository root, run the offline replay of saved real historical ZTO
balance evidence:

```sh
python3 -B shared/return-bounds/return_bounds.py demo
```

The command returns `ready` and checks one `uint256` return. This replays the
recorded evidence and review time; it makes no current freshness claim. The
saved output is in `demo-result.json`. A passing command has exit 0, a bound
failure exits 1, and invalid or inconclusive evidence exits 2.

Use `check evidence.json policy.json request.json guard.json` to review other
workspace JSON inputs in the existing Release Gate, Set Expiry and numeric
guard formats. Bounds are canonical decimal strings in raw ABI integer units.
The guard binds the normalized request and expiry policy by SHA-256; the digest
prevents accidental substitution but does not authenticate the reviewer.

When promoted, the code and its 17 focused tests passed unchanged except for
using the local shared copy of Return Lens. The shared suite command is:

```sh
python3 -B -m unittest discover -s shared/return-bounds -p 'test_*.py' -v
```

It uses the shared Release Gate, Set Expiry and Rehearsal Set, plus this
folder's Return Lens. Those dependencies are ordinary files. Historical call
returns do not establish ABI authenticity, present state, policy authority,
transaction origin, token effects, gas, or future execution. No network, wallet,
key, signature or transaction is used.
