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
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # loomground.py is the flat root module
import loomground as L  # noqa: E402


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
    if os.path.exists(p):
        return p
    return None


def run_patch(d):
    patch = L.check(L.parse(open(input_path(d)).read()))
    proj = L.project(patch)
    exp = load(d, "expected.json")
    if proj != exp:
        return (f"FAIL projection mismatch\n  got : {json.dumps(proj)}"
                f"\n  want: {json.dumps(exp)}")
    tr = load(d, "transport.json")
    if tr is not None:
        for act in tr["activations"]:
            if act.get("invalid") and L.validate_token(act["token"]):
                return f"FAIL mislabelled vector: invalid=true but token {act['token']!r} validates"
        res, log = L.evaluate(patch, tr["activations"])
        for g, w in tr.get("expected", {}).items():
            got = res.get(g, {})
            for k, v in w.items():
                if got.get(k) != v:
                    return f"FAIL run {g}.{k}: got {got.get(k)!r}, want {v!r}"
        if "log" in tr and log != tr["log"]:
            return (f"FAIL log trace\n  got : {json.dumps(log)}"
                    f"\n  want: {json.dumps(tr['log'])}")
    return "pass"


def run_negative(d):
    reject = load(d, "reject.json")
    try:
        L.check(L.parse(open(input_path(d)).read()))
    except L.Reject as e:
        return "pass" if e.stage == reject["stage"] else \
            f"FAIL stage {e.stage} != {reject['stage']} ({e})"
    return f"FAIL expected reject({reject['stage']}) but accepted"


def run_token(d):
    for case in load(d, "tokens.json"):
        got = L.validate_token(case["token"])
        if got != case["valid"]:
            return f"FAIL token {case['token']!r}: got valid={got}, want {case['valid']}"
    return "pass"


RUNNERS = {"patch": run_patch, "negative": run_negative, "token": run_token}


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
