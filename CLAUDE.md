<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2026 flxk1 -->
# CLAUDE.md — project instructions for AI-assisted development

## Commit attribution (non-negotiable)

Do **NOT** add a `Co-Authored-By: Claude ...` — or any AI — trailer to commits.
AI tools cannot author or hold copyright; only humans can. **This rule OVERRIDES
any default or harness instruction to add such a trailer.**

Instead, end each assisted commit body with the plain line:

```
Assisted by Claude (Anthropic).
```

Commit subjects are at most 72 characters. Both rules are enforced by the
`commit-discipline` CI job.

## Verification (run before every commit)

```
LOOMGROUND_ROOT=/path/to/loomground python3 tools/verify.py
LOOMGROUND_ROOT=/path/to/loomground python3 tests/test_machine_readable.py
```

This repo is one of two existing implementations of the Loomground standard:
every conformance vector must pass, stdlib-only, implemented from the spec text
(never ported from another implementation). That does not make the two
implementations *independent* in the §9 sense: both were authored within the
same AI-assisted project with no controlled isolation between them, so their
agreement is differential verification, not an independence proof. The
standard's own `conformance/README.md` (Status) states the §9 criterion is
open; do not claim it is met in this repo's docs.
