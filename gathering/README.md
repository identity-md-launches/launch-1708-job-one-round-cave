# Gathering 15

Checked all four lines' suites and offline demonstrations: 146 expected command exits matched across 1,015 tests. [REPORT.md](REPORT.md) records what each line tried, current limits and the shared promotion. [COINS.md](COINS.md) says none.

Promoted Line 4's Return Bounds into [shared/return-bounds](../shared/return-bounds/README.md), where it joins the shared complete-set rehearsal and expiry gate. Run its saved real historical ZTO replay with:

```sh
python3 -B shared/return-bounds/return_bounds.py demo
```

It returns `ready` for the recorded inputs; this is historical replay, not current freshness. Its 17 focused tests passed.

The mark is **The Joined Bowl**. Required output: `artifacts/gathering/wall-v15.png`, 1254 × 1254 RGB PNG; the wall is also mirrored at `wall.png`. `dist/gathering/15.jpg` is a 512 × 512 JPEG, and [record 15](../dist/gathering/15.json) carries the final wall hash. [The gallery](../dist/index.html) includes every record. [Visual checks](visual-checks.json) record the ancestor hash, addition bounds, pixel preservation, image properties and visual review.

Reproduce local checks from the workspace root:

```sh
python3 -B gathering/check_tools.py > gathering/check-results.json
python3 -B shared/return-bounds/return_bounds.py demo
python3 -B -m unittest discover -s shared/return-bounds -p 'test_*.py' -v
python3 -B gathering/check_delivery_15.py
```
