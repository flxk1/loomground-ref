# Changelog

## Unreleased

- `tools/verify.py`: rule 2 (an exception is a correct rejection only for a
  vector whose declared stage matches) is now enforced for apply-stage
  negative vectors too. Previously `run_negative` called `L.check(L.parse(text))`
  as one combined `try`, so an exception raised inside `parse()` but reporting
  `stage="apply"` could pass an apply-stage vector by accident. `parse()` is
  now called on its own first and required to succeed before `check()` runs;
  any exception from that standalone `parse()` call fails an apply-stage
  vector regardless of the stage it reports. Rule 2 is symmetric: a
  parse-stage vector's rejection MUST come from that same standalone `parse()`
  call too — if its input survives `parse()` (no exception raised at all),
  the vector fails right there, without ever calling `check()`. A lenient
  `parse()` that never rejects, paired with a `check()` that re-raises
  `Reject("parse", <the right reason>)` to paper over the gap, would
  otherwise score a pass — falling through to `check()` is exactly the hole
  that lets it. Added `tests/test_stub_rejection.py` stub 7
  (`parse-runs-check-reraise`, the apply-stage direction) and stub 9
  (`lenient-parse-check-reraises-parse-stage`, this parse-stage direction) to
  exercise both.
- `tools/verify.py`: `run_determinism` updated for the revised SPEC §7.5
  `permutations` format, where each entry is a `{"file", "log"}` pair rather
  than a bare filename — a cord reorder is checked against the same
  `expected` per-gate verdicts/master decisions, but against that permutation
  entry's own declared `log` (equal to the top-level log only when the
  activated gates still admit a single topological order, else the §7.4
  declaration-order tie-break for that file). Both the `repeat` loop and the
  `permutations` loop now also fail on an observed verdict for a gate not
  named in `expected` (mirrors `run_patch`'s `extra_gates` check); added a
  stub test (`evaluate` adding an undeclared gate's verdict) that must fail
  both determinism vectors.
- Verified against loomground conformance manifest v0.11.2: 75/75 vectors
  (was 74/74; the manifest gained a second determinism vector,
  `determinism-topo-tie`).
- Repository laid out on the package skeleton: `verify.py` → `tools/verify.py`, `test_machine_readable.py` → `tests/test_machine_readable.py` (`loomground.py` stays a flat root module); bare `LICENSE` → `LICENSES/Apache-2.0.txt` + `NOTICE` + `REUSE.toml`; `pyproject.toml` and release-please added. No semantic changes.
