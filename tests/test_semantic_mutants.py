#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The Loomground Authors
"""Semantic mutants: the suite must fail an evaluator whose *verdict semantics*
is wrong, not only one whose runner contract is wrong (tests/test_stub_rejection.py).

Each mutant below monkeypatches one rule of `loomground` — a precedence step,
the join, the release rule, a delegation bound, a guard, the tie-break — and
is scored through the stricter runner. Every mutant must score below the total,
and the vectors that fail it are reported, so the suite's sensitivity to each
rule is a number and not a claim.

Usage: python3 tests/test_semantic_mutants.py [LOOMGROUND_ROOT]
"""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_ROOT, os.path.join(_ROOT, "tools")]
import loomground as L  # noqa: E402
import verify as V  # noqa: E402

ROOT = V.find_standard_root(sys.argv[1] if len(sys.argv) > 1 else None)
MANIFEST = json.load(open(os.path.join(ROOT, "conformance", "manifest.json")))
VDIR = os.path.join(ROOT, "conformance", "vectors")
TOTAL = len(MANIFEST["vectors"])


def score():
    passed, failing = 0, []
    for v in MANIFEST["vectors"]:
        d = os.path.join(VDIR, v["name"])
        try:
            r = V.RUNNERS[v["kind"]](d)
        except L.Reject as e:
            r = f"FAIL unexpected reject: {e}"
        except Exception as e:  # noqa: BLE001
            r = f"FAIL exception: {type(e).__name__}: {e}"
        if r == "pass":
            passed += 1
        else:
            failing.append(v["name"])
    return passed, failing


class _patched:
    def __init__(self, **attrs):
        self.attrs, self.saved = attrs, {}

    def __enter__(self):
        for k, v in self.attrs.items():
            self.saved[k] = getattr(L, k)
            setattr(L, k, v)

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            setattr(L, k, v)


R_own, R_eval, R_check, R_guard, R_rs, R_val = (
    L.own_verdict, L.evaluate, L.check, L._guard_holds, L._risk_set, L.validate_token)


def _floored(p, gate, token):
    return max(L.RISK[token["risk"]], L.RISK.get(p.nodes[gate].get("risk_floor"), -1))


def _matches(rules, p, gate, token):
    f = _floored(p, gate, token)
    return any(r["kind"] == token["kind"] and R_guard(r["when"], token, f) for r in rules)


def _granted(p, gate, token, actor):
    f = _floored(p, gate, token)
    name = [k for k, v in L.RISK.items() if v == f][0]
    return name in R_rs(p.grants.get(gate, {}).get(actor), token["kind"])


def _piped(p, gate):
    return any(t == gate and ty == "pipe" for _, t, ty in p.cords_typed)


# ---------------------------------------------------------------- mutants
# (name, rule broken, {attr: replacement})

def m_reserved_before_refused(p, g, t, a):          # SPEC §7.1 step order 2/3
    v = R_own(p, g, t, a)
    return "reserved" if v == "refused" and _matches(p.reservations, p, g, t) else v


def m_refused_before_prohibited(p, g, t, a):        # SPEC §7.1 step order 1/2
    v = R_own(p, g, t, a)
    return "refused" if v == "prohibited" and not _granted(p, g, t, a) else v


def m_grade_clears_reservation(p, g, t, a):         # reservation reads the actor
    v = R_own(p, g, t, a)
    return "auto" if v == "reserved" and p.nodes.get(a, {}).get("grade") is not None else v


def m_ungraded_is_auto(p, g, t, a):                 # fail-open for an ungraded actor
    v = R_own(p, g, t, a)
    return "auto" if v == "human" and p.nodes.get(a, {}).get("grade") is None else v


def m_no_authority_downstream(p, g, t, a):          # authority not re-checked at a piped gate
    if not _piped(p, g):
        return R_own(p, g, t, a)
    gr = p.grants.setdefault(g, {})
    had, saved = a in gr, gr.get(a)
    gr[a] = {"kinds": None, "risks": None}
    try:
        return R_own(p, g, t, a)
    finally:
        if had:
            gr[a] = saved
        else:
            del gr[a]


def m_floor_ignored(p, g, t, a):                    # a gate's risk floor does not raise risk
    n = p.nodes[g]
    fl = n.pop("risk_floor", None)
    try:
        return R_own(p, g, t, a)
    finally:
        if fl is not None:
            n["risk_floor"] = fl


def m_guard_ge_as_eq(g, token, floored):            # `risk >= x` read as `risk = x`
    if g and g["field"] == "risk" and g["op"] == ">=":
        return floored == L.RISK[g["val"]]
    return R_guard(g, token, floored)


def m_grant_risk_unnarrowed(spec, kind):            # a grant's risk narrowing ignored
    s = R_rs(spec, kind)
    return L.FULL_RISK if s else s


def m_release_on_human(p, acts):                    # master releases `human`
    res, log = R_eval(p, acts)
    for e in res.values():
        if "master" in e and e["verdict"] == "human":
            e["master"] = "act"
    return res, log


def m_log_by_name(p, acts):                         # tie-break by gate name, not declaration
    res, log = R_eval(p, acts)
    return res, sorted(log, key=lambda e: e["gate"])


def _swallow(reason):
    def check(p):
        try:
            return R_check(p)
        except L.Reject as e:
            if e.reason == reason:
                return p
            raise
    return check


MUTANTS = [
    ("reserved-before-refused", "priority step 2 before 3", {"own_verdict": m_reserved_before_refused}),
    ("refused-before-prohibited", "priority step 1 before 2", {"own_verdict": m_refused_before_prohibited}),
    ("grade-clears-reservation", "reservation independent of the actor", {"own_verdict": m_grade_clears_reservation}),
    ("ungraded-actor-auto", "ungraded actor fails closed", {"own_verdict": m_ungraded_is_auto}),
    ("no-authority-downstream", "authority checked at every gate", {"own_verdict": m_no_authority_downstream}),
    ("risk-floor-ignored", "gate floor raises the effective risk", {"own_verdict": m_floor_ignored}),
    ("guard-ge-as-eq", "`>=` guard on an ordered property", {"_guard_holds": m_guard_ge_as_eq}),
    ("grant-risk-unnarrowed", "grant narrowed to risk levels", {"_risk_set": m_grant_risk_unnarrowed}),
    ("join-least-restrictive", "join is the maximum on the chain", {"VERDICT": {k: -v for k, v in L.VERDICT.items()}}),
    ("release-on-human", "only `auto` releases", {"evaluate": m_release_on_human}),
    ("log-by-name", "tie-break by declaration order", {"evaluate": m_log_by_name}),
    ("invalid-token-evaluated", "invalid token denotes ⊥", {"validate_token": lambda tok: True}),
    ("grade-amplification-allowed", "no-amplification over grade", {"check": _swallow("GRADE_AMPLIFICATION")}),
    ("risk-amplification-allowed", "no-amplification over granted risk", {"check": _swallow("RISK_AMPLIFICATION")}),
    ("mandate-widening-allowed", "mandate attenuation along delegation", {"check": _swallow("MANDATE_WIDENING")}),
    ("obo-cycle-allowed", "acyclic on-behalf-of", {"check": _swallow("OBO_CYCLE")}),
]

# A mutant the suite does not catch is a gap in the suite, recorded here with
# the vector that closes it. The record holds exactly while that vector is
# absent from the standard under test: a listed survivor that becomes caught,
# or an unlisted one that survives, fails this test, so the list cannot go stale.
_GAPS = {
    "guard-ge-as-eq": ("guard-risk-above-threshold",
                       "no vector runs a token above a `risk >=` guard's threshold "
                       "(every run that hits one does so at the threshold value), so "
                       "`>=` and `=` are not told apart at evaluation"),
}
_present = {v["name"] for v in MANIFEST["vectors"]}
KNOWN_SURVIVORS = {m: f"{why}; closed by `{vec}`, absent at manifest {MANIFEST.get('version')}"
                   for m, (vec, why) in _GAPS.items() if vec not in _present}

fails = []
before, _ = score()
print(f"baseline: {before}/{TOTAL}")
if before != TOTAL:
    fails.append("baseline")

rows = []
for name, rule, attrs in MUTANTS:
    with _patched(**attrs):
        passed, failing = score()
    detected = passed < TOTAL
    rows.append((name, rule, passed, failing))
    if detected and name in KNOWN_SURVIVORS:
        status, note = "FAIL", "listed as a survivor but now caught: remove it from KNOWN_SURVIVORS"
    elif detected:
        status, note = "PASS", ""
    elif name in KNOWN_SURVIVORS:
        status, note = "GAP ", KNOWN_SURVIVORS[name]
    else:
        status, note = "FAIL", "survives and is not a listed gap"
    print(f"  [{status}] {name:30s} {passed:2d}/{TOTAL}  "
          f"caught by {len(failing)}: {', '.join(failing[:4])}{', …' if len(failing) > 4 else ''}"
          + (f"\n        {note}" if note else ""))
    if status == "FAIL":
        fails.append(name)

after, _ = score()
print(f"restored: {after}/{TOTAL}")
if after != TOTAL:
    fails.append("restored")

if "--json" in sys.argv:
    out = [{"mutant": n, "rule": r, "score": s, "total": TOTAL, "caught_by": f,
            "gap": KNOWN_SURVIVORS.get(n)} for n, r, s, f in rows]
    json.dump(out, open(os.path.join(_ROOT, "tests", "semantic-mutants.json"), "w"), indent=1)

caught = sum(1 for _, _, s, _ in rows if s < TOTAL)
print(f"\n{len(MUTANTS)} mutants, {caught} caught, {len(MUTANTS) - caught} known gap(s); "
      f"{str(len(fails)) + ' FAILURE(S)' if fails else 'no unexpected result'}")
sys.exit(1 if fails else 0)
