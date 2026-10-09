<!-- SPDX-License-Identifier: Apache-2.0 -->
# loomground-ref

Stdlib-only reference implementation of the Loomground language; spec 0.10.0, 74/74 conformance vectors against the standard's manifest v0.11.2, under the stricter runner (reason-checked negatives, whole-observation equality, determinism vectors executed; see `tools/verify.py`).

## Problem
A specification with one implementation is that implementation's behaviour. A second, stdlib-only implementation passing all vectors is a conformance check; see Status, below, on what it is not yet.

## Read

- `loomground.py` — parse, apply-stage check, projection, token validator, evaluator.
- `tools/verify.py` — runs every vector listed in the standard's `conformance/manifest.json`.
- The standard: https://github.com/flxk1/loomground, at the repo root (renamed from loomground-governance; no longer under `standard/`).

## Usage

```
git clone --depth 1 https://github.com/flxk1/loomground /tmp/loomground
export LOOMGROUND_ROOT=/tmp/loomground
python3 tools/verify.py                    # 74/74 vectors pass
python3 tests/test_machine_readable.py     # needs jsonschema
```

## Example
```
in : LOOMGROUND_ROOT=<loomground> python3 tools/verify.py
out:   [PASS] draft-decide
       [PASS] draft-decide-run
       [PASS] multi-hop-pipeline
       …
     74/74 vectors pass
```

## Contracts

| | |
|---|---|
| input | the standard root: argument, `$LOOMGROUND_ROOT`, or a sibling checkout named `loomground` |
| vector kinds | `patch`: `input.lg` + `expected.json` [+ `transport.json`] · `token`: `tokens.json` · `negative`: `input.lg` + `reject.json` with `stage` (`parse`\|`apply`) and `reason` · `determinism`: `input.lg` + `transport.json` with `repeat`/`permutations` |
| API | `parse(text)` → `Patch` · `check(patch)` → patch, or raises `Reject(stage, reason, msg)` · `project(patch)` → observation dict · `evaluate(patch, activations)` → `(results, log)` · `validate_token(token)` |
| output | one PASS/FAIL line per vector; exit status 1 on any failure |

## Family

A reference implementation. Consumes: loomground's `conformance/` (spec, grammar, schema, vocabulary, conformance vectors) · pipeline position: outside the reasoning pipeline. Implemented from the specification text without importing another evaluator. Provenance: `docs/provenance.md`.

## Status

Package 0.1.0 · implements spec 0.10.0 (`loomground.py`) · verified against loomground conformance manifest v0.11.2: 74/74 conformance vectors (40 patch · 31 negative · 2 token · 1 determinism) under the stricter runner (`tools/verify.py`) · Python >=3.10 · 0 runtime dependencies.

The standard's own `conformance/README.md` states the §9 two-implementation
independence criterion is **open**, not met: this repository and the
standard's other existing reference implementation were both authored within
the same AI-assisted project, with no controlled isolation between them, so
their agreement is differential verification (useful for catching
divergence), not an independence proof. This repository makes no claim of
independence from that other implementation; neither implementation does,
until one is produced without access to this project's implementations.

## How this is made

The code and documentation are written with Loomground agents. The maintainer reads and corrects all of it.

## License

Apache-2.0 · `LICENSES/Apache-2.0.txt` · `NOTICE`
