# Code Call Query

Inspect up to 32 selected byte offsets in one proof-backed Ethereum runtime, including call instructions omitted by the existing first-64 preview. A reviewer can ask about a specific late call without mistaking PUSH data for instructions or changing the meaning of `PC` and `CODESIZE` by slicing the code.

From the repository root, run this offline demonstration with Python 3.9+ and only its standard library:

```sh
python3 -B line-3/tools/code-call-query/demo.py
```

When tried, `demonstration_passed` was `true`. It reverified the committed real ZTO proof first and IMD proof second at block **26,188,209**. ZTO has no decoded calls; its queried offset 0 is a non-call instruction. IMD has twelve calls. At offset **12,834**, the STATICCALL's locally constant target is **0x1a44076050125825900e736c501f859c50fe728c** and its route is `dynamic-target-candidate`. This is an observed historical operand, not verified external target code or a recommendation to call it. `demo-result.json` records the result. No new chain capture is claimed.

For another raw proof bundle already in the workspace:

```sh
python3 -B line-3/tools/code-call-query/code_call_query.py --bundle line-3/tools/code-routes/imd-proof.json --runtime 0xd34a99bc0f67ae1bbd63c660e6d0b0dd03e263b7 --pc 12834
```

Repeat `--pc` for up to 32 distinct decimal or `0x` byte offsets in 0..24575. `--runtime` must identify a runtime present in the verified bundle, including a candidate-path or beacon runtime. All raw proofs are checked before query findings are released. `--anchor-hash` may compare a separately obtained execution block hash; authenticating that anchor is the caller's job. The default saved header is unanchored.

Each result classifies the requested offset as `call-instruction`, `non-call-instruction`, `push-operand-byte`, or `outside-runtime`. Only decoded calls have non-null `call` details. An unresolved operand stays null. Queries keep input order and include conservative route and metadata annotations. The output explicitly reports the total call count and the number omitted by the ordinary preview; it never claims a query list covers all dependencies. Invalid proofs, anchors, runtimes or queries exit 1 with empty stdout; argument syntax errors exit 2. Successful inspection exits 0, including non-call or unresolved findings. The CLI prints JSON and writes nothing.

Tests:

```sh
python3 -B -m unittest discover -s line-3/tools/code-call-query -p 'test_*.py' -v
```

Twelve tests passed: real evidence with networking disabled, a 101st call beyond the preview, original PC/CODESIZE semantics, PUSH-data and outside offsets, unresolved/excluded calls, strict query bounds, input immutability, metadata, randomized equivalence, proof corruption before analysis, anchor/runtime binding, and CLI refusal without partial output. All inherited Line 3 suites were also rerun; see `line-3/check-results-35.json`.

Dependencies are ordinary committed sibling Python files: `code-call-routes`, `code-calls`, `code-routes`, `code-surface`, `code-opcodes`, `code-ancestry`, `code-proof`, and `code-lens`. The demo uses the sibling `code-routes` proof bundles. The only change to Code Calls adds optional selected offsets to its full-runtime scanner. Existing calls without that option keep identical output and the 64-call cap.

Limits: this is a legacy EVM structural model, not execution. Constants are conditional on successful linear-segment execution. Direct model paths may be infeasible; dynamic jumps conservatively admit every decoded JUMPDEST. Exclusion is not a safety finding. Metadata bytes stay included and annotated. `0xef`-prefixed code is refused. No stack/gas feasibility, external code identity, complete dependency graph, ABI/source equivalence, current state, consensus/finality, anchor authenticity, semantic safety or authority to transact is established. No environment variables, wallets, keys or secrets are read; nothing is signed, sent, paid, posted or deployed.

Mark: **Pepe picks one stone from the long trail to inspect.**
