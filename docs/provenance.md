# loomground-ref — provenance and prior status

Moved verbatim from README.md (2026-09-09, README canon). Reference material; the README carries the contract.
"Independent" below describes this file alone: written from the specification text, not ported
from another evaluator. It is not a claim of §9 two-implementation independence — that criterion is
open (README.md, Status).

Stdlib-only reference implementation of the Loomground language
(spec v0.11.2). A host that realises the standard's semantics so its conformance
vectors are machine-verifiable. Not part of the standard
(github.com/flxk1/loomground).

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
- 75/75 conformance vectors (manifest v0.11.2), under the stricter runner in `tools/verify.py`.
- The §9 two-implementation independence criterion is open, not met (see README.md, Status): this
  implementation and the standard's other existing one were both authored within the same
  AI-assisted project; conformance here is checked against the published vectors, which is not
  the same claim as independence.

## Provenance
The code and documentation are written with Loomground agents. The maintainer reads and corrects all of it.
No AI authorship or co-authorship: `commit-discipline` rejects AI co-author
trailers.
