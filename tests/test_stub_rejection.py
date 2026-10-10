#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The Loomground Authors
"""The stricter runner (tools/verify.py) must not score a stub evaluator as
conformant. Each stub below monkeypatches `loomground` to simulate a specific
way a lenient runner can be fooled (conformance/README.md, the vector-format
contract) and asserts the *stricter* runner's score drops below 75/75 — in
particular that it does not pass every negative vector, which a
stage-only-no-reason runner would.

Usage: python3 tests/test_stub_rejection.py [LOOMGROUND_ROOT]
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


def score():
    """Run every vector under the current (possibly monkeypatched) `loomground`
    module via the stricter runner's RUNNERS; returns (passed, total, fails_by_kind)."""
    passed, fails_by_kind = 0, {}
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
            fails_by_kind[v["name"]] = r
    return passed, len(MANIFEST["vectors"]), fails_by_kind


fails = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"\n      {detail}"))
    if not cond:
        fails.append(name)


# -------------------------------------------------------------- baseline (before)
before, total, _ = score()
print(f"baseline (real implementation): {before}/{total}")
check("baseline passes every vector (no stub applied yet)", before == total, f"{before}/{total}")


class _patched:
    """Context manager: replace attributes on the `loomground` module, restore on exit."""

    def __init__(self, **attrs):
        self.attrs = attrs
        self.saved = {}

    def __enter__(self):
        for k, v in self.attrs.items():
            self.saved[k] = getattr(L, k)
            setattr(L, k, v)
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            setattr(L, k, v)


# --------------------------------------------------- stub 1: raise-always
def _raise_always_check(patch):
    raise L.Reject("apply", "UNDECLARED_NODE", "stub: rejects everything at apply")


with _patched(check=_raise_always_check):
    after, _, fails_by_kind = score()
    print(f"stub raise-always (reject-at-apply on every input): {after}/{total}")
    check("raise-always stub fails the stricter runner (scores below total)",
          after < total, f"{after}/{total}")
    # every patch and determinism vector must now fail — the stub accepts nothing
    patch_det_names = {v["name"] for v in MANIFEST["vectors"] if v["kind"] in ("patch", "determinism")}
    still_passing = patch_det_names - set(fails_by_kind)
    check("raise-always stub fails every patch/determinism vector",
          not still_passing, f"unexpectedly still passing: {sorted(still_passing)}")


# --------------------------------------------------- stub 2: reject-at-apply (parse OK, same reason)
def _parse_ok_reject_apply(text):
    return L.Patch()  # always "parses" to an empty, vacuously well-formed patch


def _reject_apply_check(patch):
    raise L.Reject("apply", "UNDECLARED_NODE", "stub: rejects every patch at apply")


with _patched(parse=_parse_ok_reject_apply, check=_reject_apply_check):
    after, _, fails_by_kind = score()
    print(f"stub reject-at-apply (parses everything, rejects every check()): {after}/{total}")
    check("reject-at-apply stub fails the stricter runner (scores below total)",
          after < total, f"{after}/{total}")
    patch_names = {v["name"] for v in MANIFEST["vectors"] if v["kind"] == "patch"}
    still_passing = patch_names - set(fails_by_kind)
    check("reject-at-apply stub fails every patch vector",
          not still_passing, f"unexpectedly still passing: {sorted(still_passing)}")
    # rule 2: this stub also fails apply-stage NEGATIVE vectors whose real cause
    # is a parse-stage defect (reject.json declares stage parse) — it "rejects"
    # but at the wrong stage, which the stricter runner must catch
    parse_stage_negatives = {v["name"] for v in MANIFEST["vectors"]
                              if v["kind"] == "negative" and v.get("stage") == "parse"}
    still_passing = parse_stage_negatives - set(fails_by_kind)
    check("reject-at-apply stub fails parse-stage negative vectors (wrong stage)",
          not still_passing, f"unexpectedly still passing: {sorted(still_passing)}")


# --------------------------------------------------- stub 3: wrong-reason
_real_check = L.check


def _wrong_reason_check(patch):
    try:
        return _real_check(patch)
    except L.Reject as e:
        # correct stage, deliberately wrong reason — the lenient (stage-only) check
        # would still pass this; the stricter runner must not
        raise L.Reject(e.stage, "PARSE_ERROR" if e.stage == "apply" else "UNDECLARED_NODE", str(e))


with _patched(check=_wrong_reason_check):
    after, _, fails_by_kind = score()
    print(f"stub wrong-reason (correct stage, scrambled reason): {after}/{total}")
    check("wrong-reason stub fails the stricter runner (scores below total)",
          after < total, f"{after}/{total}")
    apply_negatives_with_reason = {v["name"] for v in MANIFEST["vectors"]
                                    if v["kind"] == "negative" and v.get("stage") == "apply"
                                    and v.get("reason") not in (None, "PARSE_ERROR")}
    still_passing = apply_negatives_with_reason - set(fails_by_kind)
    check("wrong-reason stub fails apply-stage negative vectors on reason alone",
          not still_passing, f"unexpectedly still passing: {sorted(still_passing)}")


# --------------------------------------------------- stub 4: extra observation key
_real_project = L.project


def _extra_key_project(patch):
    out = _real_project(patch)
    out["debug"] = True  # a key no expected.json declares
    return out


with _patched(project=_extra_key_project):
    after, _, fails_by_kind = score()
    print(f"stub extra-observation-key (adds an undeclared 'debug' key): {after}/{total}")
    check("extra-observation-key stub fails the stricter runner (scores below total)",
          after < total, f"{after}/{total}")
    patch_names = {v["name"] for v in MANIFEST["vectors"] if v["kind"] == "patch"}
    still_passing = patch_names - set(fails_by_kind)
    check("extra-observation-key stub fails every patch vector (whole-observation rule)",
          not still_passing, f"unexpectedly still passing: {sorted(still_passing)}")


# --------------------------------------------------- stub 5: missing observation key
def _missing_key_project(patch):
    out = _real_project(patch)
    out.pop("reservations", None)  # drop a required member
    return out


with _patched(project=_missing_key_project):
    after, _, fails_by_kind = score()
    print(f"stub missing-observation-key (drops 'reservations'): {after}/{total}")
    check("missing-observation-key stub fails the stricter runner (scores below total)",
          after < total, f"{after}/{total}")


# --------------------------------------------------- stub 6: nondeterministic evaluate
_real_evaluate = L.evaluate
_flip = {"n": 0}


def _nondeterministic_evaluate(patch, activations):
    results, log = _real_evaluate(patch, activations)
    _flip["n"] += 1
    if _flip["n"] % 2 == 0 and log:
        # every other call reverses the log trace — same per-gate verdicts and
        # master decisions, but a different order, which a determinism vector
        # (repeat + permutations) MUST catch
        log = list(reversed(log))
    return results, log


determinism_names = {v["name"] for v in MANIFEST["vectors"] if v["kind"] == "determinism"}
if determinism_names:
    with _patched(evaluate=_nondeterministic_evaluate):
        after, _, fails_by_kind = score()
        print(f"stub nondeterministic-evaluate (flips log order every other call): {after}/{total}")
        check("nondeterministic-evaluate stub fails the stricter runner (scores below total)",
              after < total, f"{after}/{total}")
        still_passing = determinism_names - set(fails_by_kind)
        check("nondeterministic-evaluate stub fails every determinism vector",
              not still_passing, f"unexpectedly still passing: {sorted(still_passing)}")
else:
    check("determinism vectors present to exercise the nondeterminism stub", False,
          "manifest declares no determinism-kind vector")


# --------------------------------------------------- stub 7: parse-runs-check-reraise (rule 2)
# A parse() that internally runs check() and, on failure, re-raises the
# resulting Reject as if it came from parse() itself (still reporting
# stage="apply", the true stage of the underlying cause). Rule 2 requires the
# stricter runner to fail an apply-stage vector on ANY exception raised inside
# the parse() call, whatever stage that exception reports — because an
# apply-stage vector's input is required to survive parse() on its own, with
# the rejection coming from a separate check() call. A lenient runner that
# only inspects `L.check(L.parse(text))` as one combined call cannot tell this
# apart from a correctly separated parse()-then-check() and would pass these
# apply-stage negative vectors by accident.
_real_parse_for_stub7 = L.parse
_real_check_for_stub7 = L.check


def _parse_runs_check_reraise(text):
    p = _real_parse_for_stub7(text)
    try:
        _real_check_for_stub7(p)
    except L.Reject as e:
        # the exception is raised from inside parse(), not from a later,
        # separate check() call — even though it reports the true stage
        raise L.Reject(e.stage, e.reason, f"stub: parse() ran check internally: {e}")
    return p


with _patched(parse=_parse_runs_check_reraise):
    after, _, fails_by_kind = score()
    print(f"stub parse-runs-check-reraise (parse() internally runs check and re-raises): {after}/{total}")
    check("parse-runs-check-reraise stub fails the stricter runner (scores below total)",
          after < total, f"{after}/{total}")
    apply_stage_negatives = {v["name"] for v in MANIFEST["vectors"]
                              if v["kind"] == "negative" and v.get("stage") == "apply"}
    still_passing = apply_stage_negatives - set(fails_by_kind)
    check("parse-runs-check-reraise stub fails every apply-stage negative vector "
          "(exception inside parse(), rule 2)",
          not still_passing, f"unexpectedly still passing: {sorted(still_passing)}")


# --------------------------------------------------- stub 8: evaluate adds an undeclared gate
# `evaluate()` returning a verdict for a gate that `expected` does not name is
# a whole-observation failure (mirrors run_patch's extra_gates check), and
# must be caught in a determinism vector too — both in the `repeat` loop
# (against input.lg) and in the `permutations` loop.
_real_evaluate_for_stub8 = L.evaluate


def _evaluate_adds_undeclared_gate(patch, activations):
    results, log = _real_evaluate_for_stub8(patch, activations)
    results = dict(results)
    results["ZZZ_undeclared"] = {"verdict": "auto"}
    return results, log


determinism_names_stub8 = {v["name"] for v in MANIFEST["vectors"] if v["kind"] == "determinism"}
if determinism_names_stub8:
    with _patched(evaluate=_evaluate_adds_undeclared_gate):
        after, _, fails_by_kind = score()
        print(f"stub evaluate-adds-undeclared-gate (res gets an undeclared gate 'ZZZ_undeclared'): {after}/{total}")
        check("evaluate-adds-undeclared-gate stub fails the stricter runner (scores below total)",
              after < total, f"{after}/{total}")
        still_passing = determinism_names_stub8 - set(fails_by_kind)
        check("evaluate-adds-undeclared-gate stub fails every determinism vector",
              not still_passing, f"unexpectedly still passing: {sorted(still_passing)}")
else:
    check("determinism vectors present to exercise the undeclared-gate stub", False,
          "manifest declares no determinism-kind vector")


# --------------------------------------------------- stub 9: lenient parse + check re-raises stage=parse
# The symmetric half of rule 2: a parse() that never raises (it swallows the
# real parse()'s Reject and hands back an empty, vacuously well-formed patch
# instead) paired with a check() that re-raises the real parse()'s own
# Reject(stage="parse", reason) it captured — reporting the correct stage AND
# the correct reason. Before this fix, run_negative let a parse-stage vector
# whose input survived parse() fall through to check(); here check() raises
# with the right stage and reason, so the lenient combination scored a pass.
# The fix requires a parse-stage vector's rejection to come from the
# standalone parse() call itself — surviving parse() is a FAIL regardless of
# what any later check() does — so this stub must fail every parse-stage
# negative vector.
_real_parse_for_stub9 = L.parse
_captured_stub9 = {"reject": None}


def _lenient_parse(text):
    # overwrite (not merge) on every call, so a vector whose own parse()
    # survives never sees a stale capture left over from an earlier vector
    # whose rejection this stub swallowed instead of raising
    try:
        p = _real_parse_for_stub9(text)
        _captured_stub9["reject"] = None
        return p
    except L.Reject as e:
        _captured_stub9["reject"] = e
        return L.Patch()  # never raises — vacuously well-formed, whatever the input


def _check_reraises_captured(patch):
    e = _captured_stub9["reject"]
    if e is not None:
        raise L.Reject(e.stage, e.reason, f"stub: check() re-raises what parse() captured: {e}")
    return _real_check_for_stub7(patch)


with _patched(parse=_lenient_parse, check=_check_reraises_captured):
    after, _, fails_by_kind = score()
    print(f"stub lenient-parse-check-reraises-parse-stage "
          f"(parse() never raises; check() re-raises the real stage=parse reject): {after}/{total}")
    check("lenient-parse-check-reraises-parse-stage stub fails the stricter runner (scores below total)",
          after < total, f"{after}/{total}")
    parse_stage_negatives_stub9 = {v["name"] for v in MANIFEST["vectors"]
                                    if v["kind"] == "negative" and v.get("stage") == "parse"}
    still_passing = parse_stage_negatives_stub9 - set(fails_by_kind)
    check("lenient-parse-check-reraises-parse-stage stub fails every parse-stage negative vector "
          "(survived parse(), rule 2)",
          not still_passing, f"unexpectedly still passing: {sorted(still_passing)}")


# -------------------------------------------------------------- final (after) baseline unaffected
final, _, _ = score()
check("the real implementation is unaffected after every stub's context exits",
      final == total, f"{final}/{total}")

print(f"\nbefore (real implementation): {before}/{total}")
print(f"{str(len(fails)) + ' FAILURE(S)' if fails else 'all stub checks pass'}")
sys.exit(1 if fails else 0)
