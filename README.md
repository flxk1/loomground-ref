<!-- SPDX-License-Identifier: Apache-2.0 -->
# loomground-ref

Stdlib-only reference implementation of the Loomground language; spec 0.10.0, 65/65 conformance vectors against standard 0.11.0.

## Problem
A specification with one implementation is that implementation's behaviour. A second, independent, stdlib-only implementation passing all vectors.

## Read

- `loomground.py` — parse, apply-stage check, projection, token validator, evaluator.
- `tools/verify.py` — runs every vector listed in the standard's `conformance/manifest.json`.
- The standard: https://github.com/flxk1/loomground-governance, directory `standard/`.

## Usage

```
git clone --depth 1 https://github.com/flxk1/loomground-governance /tmp/loomground-governance
export LOOMGROUND_ROOT=/tmp/loomground-governance/standard
python3 tools/verify.py                    # 65/65 vectors pass
python3 tests/test_machine_readable.py     # 49/49 checks pass; needs jsonschema
```

## Example
```
in : LOOMGROUND_ROOT=<loomground-governance>/standard python3 tools/verify.py
out:   [PASS] draft-decide
       [PASS] draft-decide-run
       [PASS] multi-hop-pipeline
       …
     65/65 vectors pass
```

## Contracts

| | |
|---|---|
| input | the standard root: argument, `$LOOMGROUND_ROOT`, or a sibling checkout named `loomground` |
| vector kinds | `patch`: `input.lg` + `expected.json` · `token`: `tokens.json` · `negative`: `input.lg` + `reject.json` with stage `parse` or `apply` |
| API | `parse(text)` → `Patch` · `check(patch)` → patch or `Reject(stage)` · `project(patch)` → observation dict · `evaluate(patch, activations)` · `validate_token(token)` |
| output | one PASS/FAIL line per vector; exit status 1 on any failure |

## Family

Independent reference implementation. Consumes: loomground-governance `standard/` (spec, grammar, schema, vocabulary, conformance vectors) · consumed by: the standard's conformance clause (two independent implementations; RVND is the other) · pipeline position: outside the reasoning pipeline. Implemented from the specification text, independently of RVND. Provenance: `docs/provenance.md`.

## Status

Package 0.1.0 · implements spec 0.10.0 (`loomground.py`) · verified 2026-09-09 against loomground-governance 0.11.0: 65/65 conformance vectors (32 patch · 31 negative · 2 token), 49/49 machine-readable checks · Python >=3.10 · 0 runtime dependencies.

## License

Apache-2.0 · `LICENSES/Apache-2.0.txt` · `NOTICE`
