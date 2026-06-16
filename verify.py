#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The Loomground Authors
"""Run the Loomground conformance vectors against the reference implementation.

Usage:  python3 verify.py [--generate] [VECTORS_DIR]
  (default VECTORS_DIR = ../loomground/conformance/vectors)
  --generate rewrites each expected.json/transport.json from the implementation.
"""
import json
import os
import sys
import loomground as L

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.normpath(os.path.join(HERE, "..", "loomground", "conformance", "vectors"))


def load(d, f):
    p = os.path.join(d, f)
    return json.load(open(p)) if os.path.exists(p) else None


def infer_actor(patch, src):
    gr = patch.grants.get(src, {})
    return next(iter(gr)) if len(gr) == 1 else None


def run_one(d, name, generate=False):
    inp = os.path.join(d, "input.loom")
    reject = load(d, "reject.json")
    tokens = load(d, "tokens.json")
    if tokens is not None:                       # token vector
        for case in tokens:
            got = L.validate_token(case["token"])
            if got != case["valid"]:
                return f"FAIL token {case['token']!r}: got valid={got}, want {case['valid']}"
        return "pass"
    if reject is not None:                        # negative vector
        try:
            L.check(L.parse(open(inp).read()))
        except L.Reject as e:
            return "pass" if e.stage == reject["stage"] else f"FAIL stage {e.stage} != {reject['stage']}"
        return f"FAIL expected reject({reject['stage']}) but accepted"
    # patch vector
    patch = L.check(L.parse(open(inp).read()))
    proj = L.project(patch)
    if generate:
        json.dump(proj, open(os.path.join(d, "expected.json"), "w"), indent=2)
        open(os.path.join(d, "expected.json"), "a").write("\n")
    else:
        exp = load(d, "expected.json")
        if exp is not None and proj != exp:
            return f"FAIL projection mismatch\n  got : {json.dumps(proj)}\n  want: {json.dumps(exp)}"
    tr = load(d, "transport.json")
    if tr is not None:
        acts = []
        for a in tr["activations"]:
            actor = a.get("actor") or infer_actor(patch, a["source"])
            acts.append({"actor": actor, "source": a["source"], "token": a["token"]})
        res = L.evaluate(patch, acts)
        want = tr.get("expected", {})
        for g, w in want.items():
            got = res.get(g, {})
            for k, v in w.items():
                if got.get(k) != v:
                    return f"FAIL run {g}.{k}: got {got.get(k)!r}, want {v!r}"
    return "pass"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    generate = "--generate" in sys.argv
    vdir = args[0] if args else DEFAULT
    names = sorted(n for n in os.listdir(vdir) if os.path.isdir(os.path.join(vdir, n)))
    fails = 0
    for n in names:
        r = run_one(os.path.join(vdir, n), n, generate)
        ok = r == "pass"
        print(f"  [{'PASS' if ok else 'FAIL'}] {n}" + ("" if ok else f"\n    {r}"))
        fails += 0 if ok else 1
    print(f"\n{len(names) - fails}/{len(names)} vectors pass" + (" — GENERATED" if generate else ""))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
