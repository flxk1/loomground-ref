<!-- SPDX-License-Identifier: Apache-2.0 -->
# loomground-ref

An independent, stdlib-only **reference implementation** of the Loomground
language, specification v0.5. It is a *host*: it realises the abstract semantics
of the standard so the standard's conformance vectors can be machine-verified. It
is **not** part of the standard — the standard is the spec, grammar, and vectors
it conforms to (github.com/flxk1/loomground).

## What it does
- `loomground.py` — parser (incl. rack expansion), well-formedness check, the
  token validator, and the evaluator (verdict assignment, strictest-wins
  propagation, the master deciding each egress path).
- `verify.py` — runs every conformance vector through the implementation.

## Run
```bash
python3 verify.py                 # verify against ../loomground/conformance/vectors
python3 verify.py PATH/TO/vectors # or a given vector set
python3 verify.py --generate      # rewrite expected.json from the implementation
```
Zero dependencies; Python 3.10+.

## Status
Passes all 13 v0.5 conformance vectors. Being an *independent* second
implementation that passes the suite is the interoperability bar the
specification's Conformance section describes.

## Provenance
This implementation was written with AI assistance (Claude, Anthropic) under
human direction. The human author makes the decisions and is responsible for the
content; the AI was used as a drafting and review tool. The commit history records
this per change via `Co-Authored-By` trailers.
