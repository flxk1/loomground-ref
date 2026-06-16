#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The Loomground Authors
"""A reference implementation of the Loomground language, v0.5.

Stdlib-only. A *host* that realises the abstract semantics of the specification
so the conformance vectors can be machine-verified. It is not part of the
standard; the standard is the spec + grammar + vectors it conforms to.
"""
from __future__ import annotations
import re

RISK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
# restrictiveness chain: auto ⊑ human ⊑ refused ⊑ reserved ⊑ prohibited
VERDICT = {"auto": 0, "human": 1, "refused": 2, "reserved": 3, "prohibited": 4}


class Reject(Exception):
    def __init__(self, stage, msg):
        super().__init__(f"{stage}: {msg}")
        self.stage = stage


# ---------------------------------------------------------------- rack pre-pass
def expand_racks(lines):
    racks, out, i = {}, [], 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"\s*rack\s+(\w[\w-]*)\s*\(([^)]*)\)\s*:\s*$", ln)
        if m:
            name, params = m.group(1), [p.strip() for p in m.group(2).split(",") if p.strip()]
            body, i = [], i + 1
            while i < len(lines) and lines[i].strip() != "end":
                body.append(lines[i]); i += 1
            if i >= len(lines):
                raise Reject("parse", f"rack {name} missing end")
            racks[name] = (params, body); i += 1; continue
        out.append(ln); i += 1
    prog, inst = [], {}
    for ln in out:
        m = re.match(r"\s*rack-use\s+(\w[\w-]*)\s*\(([^)]*)\)\s*$", ln)
        if not m:
            prog.append(ln); continue
        name = m.group(1)
        if name not in racks:
            raise Reject("parse", f"unknown rack {name}")
        params, body = racks[name]
        binds = {}
        for b in m.group(2).split(","):
            if "=" not in b:
                raise Reject("parse", f"bad binding {b!r}")
            k, v = b.split("=", 1); binds[k.strip()] = v.strip()
        if set(binds) != set(params):
            raise Reject("parse", f"rack {name} args {set(binds)} != params {set(params)}")
        n = inst.get(name, 0); inst[name] = n + 1
        for bl in body:
            s = bl
            for k, v in binds.items():
                s = re.sub(r"\$" + re.escape(k) + r"\b", v, s)
            s = s.replace("$0", str(n))
            if "$" in s:
                raise Reject("parse", f"undefined substitution in {bl!r}")
            prog.append(s)
    return prog


# --------------------------------------------------------------------- parsing
class Patch:
    def __init__(self):
        self.nodes = {}          # id -> {"class":..., extras}
        self.order = []          # declaration order of declared nodes
        self.grants = {}         # gate -> {actor: {"kinds":set|None,"risks":set|None}}
        self.cords = []          # (frm, to, type)
        self.reservations = []   # {"kind","by","when"}
        self.prohibitions = []   # {"kind","when"}
        self.obligations = []    # {"obligation","gate"}
        self.delegations = {}    # delegate -> delegator


def _guard(tokens, i):
    # guard = kind = X | risk relop L | party = id
    field = tokens[i]
    if field == "kind" and tokens[i + 1] == "=":
        return {"field": "kind", "op": "=", "val": tokens[i + 2]}, i + 3
    if field == "risk" and tokens[i + 1] in (">=", "="):
        return {"field": "risk", "op": tokens[i + 1], "val": tokens[i + 2]}, i + 3
    if field == "party" and tokens[i + 1] == "=":
        return {"field": "party", "op": "=", "val": tokens[i + 2]}, i + 3
    raise Reject("parse", f"bad guard at {tokens[i:]}")


def _grant(tok):
    m = re.match(r"^([\w-]+)(?:\[([^\]]*)\])?$", tok)
    if not m:
        raise Reject("parse", f"bad grant {tok!r}")
    actor, inner = m.group(1), m.group(2)
    kinds = risks = None
    if inner is not None:
        if ":" in inner:
            kpart, rpart = inner.split(":", 1)
            kinds = {kpart.strip()}; risks = {r.strip() for r in rpart.split(",")}
        else:
            kinds = {k.strip() for k in inner.split(",")}
    return actor, {"kinds": kinds, "risks": risks}


def parse(text):
    raw = [l.split("#", 1)[0].rstrip() for l in text.splitlines()]
    raw = expand_racks(raw)
    p = Patch()
    for line in raw:
        if not line.strip():
            continue
        t = line.split()
        kw = t[0]
        if kw == "actor":
            p.nodes[t[1]] = {"class": "actor"}; p.order.append(t[1]); i = 2
            while i < len(t):
                if t[i] == "party": p.nodes[t[1]]["party"] = t[i + 1]; i += 2
                elif t[i] == "on-behalf-of": p.delegations[t[1]] = t[i + 1]; i += 2
                elif t[i] == "name": break
                else: raise Reject("parse", f"bad actor clause {t[i]!r}")
        elif kw == "human":
            p.nodes[t[1]] = {"class": "human"}; p.order.append(t[1]); i = 2
            while i < len(t):
                if t[i] == "role": p.nodes[t[1]]["role"] = t[i + 1]; i += 2
                elif t[i] == "name": break
                else: raise Reject("parse", f"bad human clause {t[i]!r}")
        elif kw == "gate":
            gid = t[1]; p.nodes[gid] = {"class": "gate"}; p.order.append(gid)
            p.grants.setdefault(gid, {}); i = 2
            while i < len(t):
                if t[i] == "risk": p.nodes[gid]["risk_floor"] = t[i + 1]; i += 2
                elif t[i] == "party": p.nodes[gid]["party"] = t[i + 1]; i += 2
                elif t[i] == "name": p.nodes[gid]["name"] = t[i + 1]; i += 2
                elif t[i] == "grant":
                    for gt in t[i + 1:]:
                        a, spec = _grant(gt); p.grants[gid][a] = spec
                    break
                else: raise Reject("parse", f"bad gate clause {t[i]!r}")
        elif kw == "cord":
            if "->" not in t:
                raise Reject("parse", "cord without ->")
            j = t.index("->")
            p.cords.append((t[1], t[j + 1], None))
        elif kw == "reserve":
            kind = t[1]
            if t[2] != "by":
                raise Reject("parse", "reserve without by")
            # target spec is consumed but not needed for these semantics
            when = None; i = 3
            while i < len(t):
                if t[i] == "when":
                    when, i = _guard(t, i + 1)
                elif t[i] == "duration":
                    i += 2
                else:
                    i += 1
            p.reservations.append({"kind": kind, "by": t[3], "when": when})
        elif kw == "prohibit":
            when = None
            if len(t) > 2 and t[2] == "when":
                when, _ = _guard(t, 3)
            p.prohibitions.append({"kind": t[1], "when": when})
        elif kw == "obligation":
            if t[2] != "on":
                raise Reject("parse", "obligation without on")
            p.obligations.append({"obligation": t[1], "gate": t[3]})
        elif kw == "contest-notice":
            if t[1] != "on":
                raise Reject("parse", "contest-notice without on")
            p.obligations.append({"obligation": "contest-notice", "gate": t[2]})
        else:
            raise Reject("parse", f"unknown keyword {kw!r}")
    return p


# ------------------------------------------------------------- well-formedness
def cord_type(p, frm, to):
    if to == "master":
        if p.nodes.get(frm, {}).get("class") != "gate":
            raise Reject("apply", f"only a gate may egress to master ({frm})")
        return "egress"
    cf = p.nodes.get(frm, {}).get("class")
    ct = p.nodes.get(to, {}).get("class")
    if cf is None or ct is None:
        raise Reject("apply", f"cord into undeclared node {frm}->{to}")
    if cf == "actor" and ct == "gate":
        return "authority"
    if cf == "gate" and ct == "gate":
        return "pipe"
    raise Reject("apply", f"illegal cord {cf}->{ct}")


def check(p):
    # risk floors in domain
    for nid, n in p.nodes.items():
        if "risk_floor" in n and n["risk_floor"] not in RISK:
            raise Reject("apply", f"unknown risk {n['risk_floor']}")
    # type every cord
    typed = []
    for frm, to, _ in p.cords:
        if p.nodes.get(frm, {}).get("class") == "human" or p.nodes.get(to, {}).get("class") == "human":
            raise Reject("apply", "a human may not be a cord endpoint")
        typed.append((frm, to, cord_type(p, frm, to)))
    p.cords = typed
    pipes = [(f, t) for f, t, ty in typed if ty == "pipe"]
    # acyclic pipe
    succ = {}
    for f, t in pipes:
        succ.setdefault(f, []).append(t)
    WHITE, GREY, BLACK = 0, 1, 2
    col = {}

    def dfs(u):
        col[u] = GREY
        for v in succ.get(u, []):
            if col.get(v, WHITE) == GREY:
                raise Reject("apply", "pipe cycle")
            if col.get(v, WHITE) == WHITE:
                dfs(v)
        col[u] = BLACK
    for g in [n for n, d in p.nodes.items() if d["class"] == "gate"]:
        if col.get(g, WHITE) == WHITE:
            dfs(g)
    # reachability: every gate on a pipe∪egress path to master
    reaches = set()
    egress = {f for f, t, ty in typed if ty == "egress"}
    changed = True
    reaches |= egress
    while changed:
        changed = False
        for f, t in pipes:
            if t in reaches and f not in reaches:
                reaches.add(f); changed = True
    for g, d in p.nodes.items():
        if d["class"] == "gate" and g not in reaches:
            raise Reject("apply", f"gate {g} on no path to master")
    # no-amplification for delegations
    for delegate, delegator in p.delegations.items():
        for gate, gr in p.grants.items():
            if delegate in gr:
                dk = gr[delegate]["kinds"]
                if delegator not in gr:
                    raise Reject("apply", f"delegation {delegate}<-{delegator}: delegator lacks grant at {gate}")
                # risk subset check (None = all)
                drisk = gr[delegate]["risks"]; lrisk = gr[delegator]["risks"]
                if drisk is not None and lrisk is not None and not drisk <= lrisk:
                    raise Reject("apply", f"delegation amplifies risk at {gate}")
    return p


# --------------------------------------------------------------- projection
def project(p):
    nodes = []
    for nid in p.order:
        d = p.nodes[nid]
        e = {"id": nid, "class": d["class"]}
        if "role" in d: e["role"] = d["role"]
        if "risk_floor" in d: e["risk_floor"] = d["risk_floor"]
        nodes.append(e)
    nodes.append({"id": "master", "class": "master"})
    cords = [{"from": f, "to": t, "type": ty} for f, t, ty in p.cords]
    res = []
    for r in p.reservations:
        e = {"kind": r["kind"], "by": r["by"]}
        if r["when"]:
            g = r["when"]
            e["when"] = f'{g["field"]} {g["op"]} {g["val"]}'
        res.append(e)
    out = {"nodes": nodes, "cords": cords, "reservations": res}
    return out


# --------------------------------------------------------------- evaluation
def _guard_holds(g, token, floor):
    if g is None:
        return True
    if g["field"] == "kind":
        return token["kind"] == g["val"]
    if g["field"] == "party":
        return token.get("party") == g["val"]
    if g["field"] == "risk":
        tr = max(RISK[token["risk"]], RISK.get(floor, -1))
        return tr >= RISK[g["val"]] if g["op"] == ">=" else tr == RISK[g["val"]]
    return False


def own_verdict(p, gate, token, actor):
    floor = p.nodes[gate].get("risk_floor")
    for pr in p.prohibitions:
        if pr["kind"] == token["kind"] and _guard_holds(pr["when"], token, floor):
            return "prohibited"
    gr = p.grants.get(gate, {})
    granted = actor in gr and (gr[actor]["kinds"] is None or token["kind"] in gr[actor]["kinds"])
    if not granted:
        return "refused"
    for r in p.reservations:
        if r["kind"] == token["kind"] and _guard_holds(r["when"], token, floor):
            return "reserved"
    return "auto"   # step (4): policy default is `auto` in these vectors


def evaluate(p, activations):
    pipes = [(f, t) for f, t, ty in p.cords if ty == "pipe"]
    preds = {}
    for f, t in pipes:
        preds.setdefault(t, []).append(f)
    egress = {f for f, t, ty in p.cords if ty == "egress"}
    results = {}
    for act in activations:
        actor, src, token = act["actor"], act["source"], act["token"]
        # gates reachable from src over pipes (incl. src)
        reach, stack = set(), [src]
        succ = {}
        for f, t in pipes:
            succ.setdefault(f, []).append(t)
        while stack:
            u = stack.pop()
            if u in reach:
                continue
            reach.add(u)
            stack += succ.get(u, [])
        eff = {}

        def effective(g):
            if g in eff:
                return eff[g]
            own = own_verdict(p, g, token, actor)
            v = own
            for h in preds.get(g, []):
                if h in reach:
                    hv = effective(h)
                    if VERDICT[hv] > VERDICT[v]:
                        v = hv
            eff[g] = v
            return v
        for g in reach:
            verdict = effective(g)
            entry = results.setdefault(g, {"verdict": verdict})
            entry["verdict"] = verdict
            if g in egress:
                entry["master"] = "act" if verdict == "auto" else "withhold"
    return results


# --------------------------------------------------------------- token check
def validate_token(tok):
    if not isinstance(tok, dict):
        return False
    for f in ("id", "kind", "risk", "party", "provenance"):
        if f not in tok:
            return False
    if tok["risk"] not in RISK:
        return False
    if not isinstance(tok["provenance"], list):
        return False
    return True
