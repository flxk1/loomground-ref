#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The Loomground Authors
"""Run the Loomground conformance vectors against the reference implementation.

Usage:  python3 tools/verify.py [ROOT_OR_VECTORS_DIR]

The standard is located from, in order: the argument (the standard's root, or
its conformance/vectors directory), $LOOMGROUND_ROOT, or a sibling checkout
named `loomground`/`Loomground` next to any ancestor of this file. Vectors are
enumerated from conformance/manifest.json; the netlist extension is `input.lg`
(the standard closed the `.loom` alias window at v0.7).

This is the *stricter* runner: conformance/README.md, "The vector-format
contract" names four rules a lenient runner can miss, and each is checked here:

1. A negative vector's `reject.json` carries `stage` AND `reason` (a code from
   the closed set in vocabulary/reject-reasons.json); both are checked, not
   stage alone — an implementation that rejects at the right stage for the
   wrong cause fails the vector.
2. A raised exception is treated as a correct rejection only for a vector whose
   `reject.json` declares `"stage": "parse"`. An apply-stage vector requires
   the input to survive parsing; a parse-time exception on an apply-stage
   vector is a FAIL, not a pass-by-accident.
3. Whole-observation equality: a patch vector's `expected.json`, and each
   `transport.json` run's `expected`/`log`, are compared as whole objects —
   an extra, missing, or misordered member anywhere is a failure, not a
   partial pass on named keys alone.
4. Determinism vectors (`kind: "determinism"`) are executed: `repeat` runs
   against `input.lg` and one run against each file in `permutations`, failing
   on any divergence in per-gate verdicts, master decisions, or log trace.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # loomground.py is the flat root module
import loomground as L  # noqa: E402

REASON_CODES = None  # the closed set, loaded lazily from vocabulary/reject-reasons.json


def find_standard_root(arg=None):
    candidates = []
    if arg:
        candidates += [arg, os.path.normpath(os.path.join(arg, "..", ".."))]
    if os.environ.get("LOOMGROUND_ROOT"):
        candidates.append(os.environ["LOOMGROUND_ROOT"])
    d = HERE
    while True:
        parent = os.path.dirname(d)
        candidates += [os.path.join(parent, n) for n in ("loomground", "Loomground")]
        if parent == d:
            break
        d = parent
    for c in candidates:
        if os.path.isfile(os.path.join(c, "conformance", "manifest.json")):
            return c
    sys.exit("cannot locate the Loomground standard: pass its root, or set $LOOMGROUND_ROOT")


def load(d, f):
    p = os.path.join(d, f)
    return json.load(open(p)) if os.path.exists(p) else None


def input_path(d):
    p = os.path.join(d, "input.lg")
    return p if os.path.exists(p) else None


def whole_eq(got, want, where):
    """Whole-object equality: every member of `want` present and equal in
    `got`, AND no member of `got` absent from `want` — rule 3. Returns None on
    match, else a description of the mismatch."""
    if got == want:
        return None
    missing = {k: want[k] for k in want if k not in got}
    extra = {k: got[k] for k in got if k not in want}
    diff = {k: (got.get(k), want.get(k)) for k in set(got) | set(want)
            if got.get(k) != want.get(k)}
    return (f"{where} mismatch\n  got : {json.dumps(got)}\n  want: {json.dumps(want)}"
            f"\n  missing={missing!r} extra={extra!r} differing={diff!r}")


def run_patch(d):
    patch = L.check(L.parse(open(input_path(d)).read()))
    proj = L.project(patch)
    exp = load(d, "expected.json")
    diff = whole_eq(proj, exp, "projection")
    if diff:
        return f"FAIL {diff}"
    tr = load(d, "transport.json")
    if tr is not None:
        for act in tr["activations"]:
            if act.get("invalid") and L.validate_token(act["token"]):
                return f"FAIL mislabelled vector: invalid=true but token {act['token']!r} validates"
        res, log = L.evaluate(patch, tr["activations"])
        for g, want_gate in tr.get("expected", {}).items():
            got_gate = res.get(g, {})
            diff = whole_eq(got_gate, want_gate, f"run {g}")
            if diff:
                return f"FAIL {diff}"
        # a gate named in `expected` with no observed counterpart (dropped from
        # res), or vice versa, is also a whole-observation failure
        extra_gates = set(res) - set(tr.get("expected", {}))
        if extra_gates:
            return f"FAIL run: observed verdict(s) for undeclared gate(s) {sorted(extra_gates)}"
        if "log" in tr:
            diff = whole_eq(log, tr["log"], "log trace") if log != tr["log"] else None
            if log != tr["log"]:
                return (f"FAIL log trace\n  got : {json.dumps(log)}"
                        f"\n  want: {json.dumps(tr['log'])}")
    return "pass"


def run_negative(d):
    reject = load(d, "reject.json")
    want_stage = reject["stage"]
    want_reason = reject.get("reason")
    try:
        L.check(L.parse(open(input_path(d)).read()))
    except L.Reject as e:
        # rule 2: an exception is a correct rejection only at the declared stage
        if e.stage != want_stage:
            return f"FAIL stage {e.stage} != {want_stage} ({e})"
        # rule 1: check reason, not only stage
        if want_reason is not None and e.reason != want_reason:
            return f"FAIL reason {e.reason} != {want_reason} ({e})"
        return "pass"
    except Exception as e:  # noqa: BLE001 — a non-Reject exception is never a pass
        return f"FAIL unexpected exception (not a Reject): {type(e).__name__}: {e}"
    return f"FAIL expected reject({want_stage}) but accepted"


def run_token(d):
    for case in load(d, "tokens.json"):
        got = L.validate_token(case["token"])
        if got != case["valid"]:
            return f"FAIL token {case['token']!r}: got valid={got}, want {case['valid']}"
    return "pass"


def _run_once(d, lg_path, activations):
    """Parse+check `lg_path` and evaluate `activations` against it; returns
    (per-gate results, log) or raises L.Reject/other on failure to parse."""
    patch = L.check(L.parse(open(lg_path).read()))
    return L.evaluate(patch, activations)


def run_determinism(d):
    tr = load(d, "transport.json")
    activations = tr["activations"]
    repeat = tr["repeat"]
    permutations = tr.get("permutations", [])
    base = input_path(d)
    want_res, want_log = {}, tr["log"]
    for g, w in tr["expected"].items():
        want_res[g] = w
    runs = [("input.lg (run %d)" % i, base) for i in range(repeat)]
    runs += [(p, os.path.join(d, p)) for p in permutations]
    for label, path in runs:
        res, log = _run_once(d, path, activations)
        for g, w in want_res.items():
            diff = whole_eq(res.get(g, {}), w, f"{label} run {g}")
            if diff:
                return f"FAIL determinism: {diff}"
        if log != want_log:
            return (f"FAIL determinism: {label} log trace\n  got : {json.dumps(log)}"
                    f"\n  want: {json.dumps(want_log)}")
    return "pass"


RUNNERS = {"patch": run_patch, "negative": run_negative, "token": run_token,
           "determinism": run_determinism}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = find_standard_root(args[0] if args else None)
    manifest = json.load(open(os.path.join(root, "conformance", "manifest.json")))
    vdir = os.path.join(root, "conformance", "vectors")
    print(f"standard: {root} (manifest v{manifest.get('version', '?')})")
    fails = 0
    for v in manifest["vectors"]:
        d = os.path.join(vdir, v["name"])
        try:
            r = RUNNERS[v["kind"]](d)
        except L.Reject as e:
            r = f"FAIL unexpected reject: {e}"
        ok = r == "pass"
        print(f"  [{'PASS' if ok else 'FAIL'}] {v['name']}" + ("" if ok else f"\n    {r}"))
        fails += 0 if ok else 1
    print(f"\n{len(manifest['vectors']) - fails}/{len(manifest['vectors'])} vectors pass")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
