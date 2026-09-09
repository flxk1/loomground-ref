#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The Loomground Authors
"""Test the standard's machine-readable layer against the reference
implementation and the real vector data. Catches drift between the prose, the
data artifacts, and the semantics. Requires jsonschema."""
import glob
import json
import os
import sys
from jsonschema import Draft202012Validator as V

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_ROOT, os.path.join(_ROOT, "tools")]  # loomground.py at root, verify.py in tools/
import loomground as L  # noqa: E402
from verify import find_standard_root  # noqa: E402

STD = find_standard_root(sys.argv[1] if len(sys.argv) > 1 else None)
def p(*a): return os.path.join(STD, *a)
def jl(*a): return json.load(open(p(*a)))

fails = []
total = 0
def check(name, cond, detail=""):
    global total
    total += 1
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"\n      {detail}"))
    if not cond:
        fails.append(name)


def to_ir(patch):
    nodes = []
    for nid in patch.order:
        d = patch.nodes[nid]
        e = {"id": nid, "class": d["class"]}
        for k in ("role", "party", "risk_floor", "grade", "grade_required"):
            if k in d:
                e[k] = d[k]
        if nid in patch.delegations:
            e["on_behalf_of"] = patch.delegations[nid]
        nodes.append(e)
    nodes.append({"id": "master", "class": "master"})
    grants = []
    for g, gr in patch.grants.items():
        for a, spec in gr.items():
            it = {"gate": g, "actor": a}
            if spec["kinds"]:
                it["kinds"] = sorted(spec["kinds"])
            if spec["risks"]:
                it["risks"] = sorted(spec["risks"])
            grants.append(it)
    return {"nodes": nodes, "grants": grants,
            "cords": [{"from": f, "to": t, "type": ty} for f, t, ty in patch.cords_typed],
            "reservations": [{"kind": r["kind"], "by": r["by"]} for r in patch.reservations],
            "prohibitions": [{k: v for k, v in pr.items() if v} for pr in patch.prohibitions],
            "obligations": patch.obligations}


# 1. every schema is itself a valid JSON Schema
for f in glob.glob(p("schema", "*.json")):
    V.check_schema(json.load(open(f)))
check("schemas are valid JSON Schema (draft 2020-12)", True)

# 2. observation schema validates every expected.json
obs = V(jl("schema", "observation.schema.json"))
bad = [f for f in glob.glob(p("conformance", "vectors", "*", "expected.json")) if not obs.is_valid(json.load(open(f)))]
check("observation schema validates all expected.json", not bad, bad)

# 3. token schema agrees with the token-validation vector
tok = V(jl("schema", "token.schema.json"))
tv = jl("conformance", "vectors", "token-validation", "tokens.json")
mism = [c for c in tv if tok.is_valid(c["token"]) != c["valid"]]
check("token schema agrees with token-validation flags", not mism, mism)

# 4. patch schema validates a real patch IR (emitted from the example)
patch = L.check(L.parse(open(p("examples", "draft-decide.lg")).read()))
errs = list(V(jl("schema", "patch.schema.json")).iter_errors(to_ir(patch)))
check("patch schema validates the example patch IR", not errs, errs[:1])

# 5. vocabulary data == the reference implementation's semantics
check("verdicts.json alphabet == impl verdict chain", jl("vocabulary", "verdicts.json")["alphabet"] == list(L.VERDICT))
check("verdicts.json releases-at-master: only auto", [k for k, v in jl("vocabulary", "verdicts.json")["releases_at_master"].items() if v] == ["auto"])
check("risk.json levels == impl risk order", jl("vocabulary", "risk.json")["levels"] == list(L.RISK))
nc = {n["class"] for n in jl("vocabulary", "node-classes.json")}
check("node-classes == {actor,human,gate,master}", nc == {"actor", "human", "gate", "master"})
cords = {(c["from"], c["to"], c["type"]) for c in jl("vocabulary", "cords.json")["permitted"]}
check("cords.json == the 3 permitted pairings", cords == {("actor", "gate", "authority"), ("gate", "gate", "pipe"), ("gate", "master", "egress")})

# 6. language-card is consistent with the vocabulary + token schema
card = jl("language-card.json")
check("card.nodes == node classes", set(card["nodes"]) == nc)
check("card.verdicts == verdicts alphabet", card["verdicts"] == jl("vocabulary", "verdicts.json")["alphabet"])
check("card.declarations == declarations vocab", set(card["declarations"]) == {d["name"] for d in jl("vocabulary", "declarations.json")})
check("card.token == token schema fields", set(card["token"]) == set(jl("schema", "token.schema.json")["properties"]))

# 7. manifest matches the actual vectors. A vector dir is one that holds a
# vector input (input.lg, or tokens.json for a token vector); any other
# subdirectory is scratch, not a vector, and is not expected in the manifest.
man = jl("conformance", "manifest.json")
def _is_vector(n):
    d = p("conformance", "vectors", n)
    return os.path.isdir(d) and any(
        os.path.exists(os.path.join(d, f)) for f in ("input.lg", "tokens.json"))
actual = sorted(n for n in os.listdir(p("conformance", "vectors")) if _is_vector(n))
check("manifest lists exactly the vector dirs", sorted(v["name"] for v in man["vectors"]) == actual)
neg = {v["name"]: v.get("stage") for v in man["vectors"] if v["kind"] == "negative"}
ok = all(s == json.load(open(p("conformance", "vectors", n, "reject.json")))["stage"] for n, s in neg.items())
check("manifest negative stages match reject.json", ok)

# 8. grammar keywords cover the parser's statement keywords; all inputs parse-or-reject
ebnf = open(p("grammar", "loomground.ebnf")).read()
for kw in ["actor", "human", "gate", "cord", "reserve", "prohibit", "obligation", "redress", "transfer"]:
    check(f"grammar declares keyword '{kw}'", f'"{kw}"' in ebnf)

# 8b. the agent guide (llms.txt) stays in sync with the language. It is a
# repo-level guide: at the standard root (flat v0.7 layout) or its parent
# (governance keeps the standard bundle under standard/, llms.txt at repo root).
_llms = p("llms.txt")
if not os.path.exists(_llms):
    _llms = os.path.join(STD, "..", "llms.txt")
guide = open(_llms).read()
for n in ["actor", "human", "gate", "master"]:
    check(f"llms.txt covers node '{n}'", n in guide)
for v in ["auto", "human", "refused", "reserved", "prohibited"]:
    check(f"llms.txt covers verdict '{v}'", v in guide)
for kw in ["reserve", "quorum", "prohibit", "temporal", "obligation", "redress", "party",
           "delegation", "grade", "on-behalf-of", "mandate", "transfer", "consign",
           "reversibility", "uncertainty"]:
    check(f"llms.txt covers declaration '{kw}'", kw in guide)

parse_ok = True
inputs = glob.glob(p("conformance", "vectors", "*", "input.lg"))
for f in inputs + [p("examples", "draft-decide.lg")]:
    try:
        L.parse(open(f).read())
    except L.Reject as e:
        if e.stage == "parse" and "reject" not in f:
            parse_ok = False
check("every non-reject input parses under the grammar", parse_ok)

print(f"\n{str(total) + '/' + str(total) + ' machine-readable tests pass' if not fails else str(len(fails)) + '/' + str(total) + ' FAILURE(S)'}")
sys.exit(1 if fails else 0)
