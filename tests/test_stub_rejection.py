#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The Loomground Authors
"""The stricter runner (tools/verify.py) must not score a stub evaluator as
conformant. Each stub below monkeypatches `loomground` to simulate a specific
way a lenient runner can be fooled (conformance/README.md, the vector-format
contract) and asserts the *stricter* runner's score drops below 74/74 — in
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


# -------------------------------------------------------------- final (after) baseline unaffected
final, _, _ = score()
check("the real implementation is unaffected after every stub's context exits",
      final == total, f"{final}/{total}")

print(f"\nbefore (real implementation): {before}/{total}")
print(f"{str(len(fails)) + ' FAILURE(S)' if fails else 'all stub checks pass'}")
sys.exit(1 if fails else 0)
