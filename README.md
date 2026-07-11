<!-- SPDX-License-Identifier: Apache-2.0 -->
# loomground-ref

An independent, stdlib-only **reference implementation** of the Loomground
language, specification v0.7. It is a *host*: it realises the abstract semantics
of the standard so the standard's conformance vectors can be machine-verified. It
is **not** part of the standard — the standard is the spec, grammar, and vectors
it conforms to (github.com/flxk1/loomground).

## What it does
- `loomground.py` — parser (incl. rack expansion), apply-stage well-formedness
  (typed cords, pipe/on-behalf-of acyclicity, reachability, guard domain, grade
  ladder, the delegation no-amplification invariant), the observation projection
  (canonical form incl. principal-chain party resolution), the token validator,
  and the evaluator (verdict assignment incl. the §7.1 grade comparison,
  strictest-wins propagation, the ordered log trace, the master deciding each
  egress path).
- `verify.py` — runs every conformance vector, enumerated from the standard's
  `conformance/manifest.json` (patch, negative, and token vectors; the netlist
  extension is `input.lg` — the standard closed the `.loom` alias at v0.7).
- `test_machine_readable.py` — cross-validates the standard's machine-readable
  layer (schemas, vocabulary, language card, manifest, grammar, llms.txt)
  against this implementation and the vector data (needs `jsonschema`).

## Run
```bash
python3 verify.py         # locate the standard next to this checkout, run all vectors
python3 verify.py PATH    # or point at the standard's root (or set $LOOMGROUND_ROOT)
```
Zero dependencies; Python 3.10+.

## Status
Passes all 47 conformance vectors (v0.8-draft suite, including the group-A
negatives that pin rack-failure and obligation-gate rejection stages, one of
which caught and fixed a real gap here) — including the autonomy grades, the
delegation/on-behalf-of principal chain with its no-amplification invariant
(and its pinned empty-set corner), party inheritance along the chain, quorum
and temporal reservations, redress, tag guards, and the ordered log trace.
This fulfils the second half of the standard's §9 two-implementation
interoperability criterion: two implementations, neither derived from the
other, each reproduce every vector — RVND (a production host, tracked
separately) is the other.

## Provenance
This implementation was written with AI assistance under
human direction. The human author makes the decisions and is responsible for the
content; AI was used as a drafting and review tool. An assisted commit ends
with a plain line naming the tool used — "Assisted by <tool> (<vendor>); not an
author or copyright holder." — never an authorship or co-authorship trailer
(enforced by the `commit-discipline` CI job). The commit history records which
tool assisted each change; this document names none. Commits made before this
convention carried a `Co-Authored-By` trailer from tooling defaults; that
trailer recorded no authorship claim and is superseded by this convention.
