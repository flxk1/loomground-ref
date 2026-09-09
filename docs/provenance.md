# loomground-ref — provenance and prior status

Moved verbatim from README.md (2026-09-09, README canon). Reference material; the README carries the contract.

Independent, stdlib-only reference implementation of the Loomground language
(spec v0.10.0). A host that realises the standard's semantics so its conformance
vectors are machine-verifiable. Not part of the standard
(github.com/flxk1/loomground-governance).

## Files
- `loomground.py` — parse, apply-stage well-formedness, observation projection,
  token validator, evaluator.
- `tools/verify.py` — run every conformance vector from `conformance/manifest.json`.
- `tests/test_machine_readable.py` — cross-check the standard's machine-readable layer
  (schemas, vocabulary, card, manifest, grammar, llms.txt). Needs `jsonschema`.

## Run
```bash
python3 tools/verify.py [PATH]   # PATH = standard root, or set $LOOMGROUND_ROOT
```
Zero dependencies; Python 3.10+.

## Status
- 62/62 conformance vectors, 49/49 machine-readable checks (governance v0.10.0).
- §9 second independent implementation; RVND is the other.

## Provenance
AI-assisted, human-directed. Attribution rides the commit line
(`Assisted by <tool> (<vendor>); not an author or copyright holder.`), enforced
by `commit-discipline`. No AI authorship or co-authorship.
