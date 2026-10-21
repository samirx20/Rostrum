"""Check controls.json and print what each demo moment must show (the reference both mockups are compared to).

    python -I check_controls.py              # checks the data, prints visible controls per moment
    python -I check_controls.py --json out   # also writes {moment: {item, shown: [...], more: [...]}} to out

Exits 1 on any problem in the data (fail loudly: a mockup built on bad data proves nothing).
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def valid(cond, values, facts):
    """The whole condition language: is, not, all, any, fact. No condition = always valid."""
    if cond is None:
        return True
    if "is" in cond:
        name, want = cond["is"]
        return values[name] == want
    if "not" in cond:
        return not valid(cond["not"], values, facts)
    if "all" in cond:
        return all(valid(c, values, facts) for c in cond["all"])
    if "any" in cond:
        return any(valid(c, values, facts) for c in cond["any"])
    if "fact" in cond:
        return bool(facts.get(cond["fact"], False))
    raise ValueError(f"unknown condition {cond}")


def shown(kind, item):
    """(shown, more): valid controls, deep ones behind 'More'. Order: groups as they first appear in the data,
    inside a group primary before secondary, then data order."""
    groups = list(dict.fromkeys(p["group"] for p in kind["params"]))
    rank = {"primary": 0, "secondary": 1, "deep": 2}
    ok = [p for p in kind["params"] if valid(p.get("validWhen"), item["values"], item["facts"])]
    ok.sort(key=lambda p: (groups.index(p["group"]), rank[p["importance"]]))  # stable: data order breaks ties
    return ([p["id"] for p in ok if p["importance"] != "deep"], [p["id"] for p in ok if p["importance"] == "deep"])


def refs(cond):
    if not cond:
        return []
    if "is" in cond:
        return [("param", cond["is"][0])]
    if "not" in cond:
        return refs(cond["not"])
    if "fact" in cond:
        return [("fact", cond["fact"])]
    return [r for c in cond.get("all", cond.get("any", [])) for r in refs(c)]


def check(data):
    problems = []
    for kid, kind in data["kinds"].items():
        ids = {p["id"] for p in kind["params"]}
        for p in kind["params"]:
            if p["importance"] not in data["importance"]:
                problems.append(f"{kid}.{p['id']}: importance {p['importance']!r}")
            for what, name in refs(p.get("validWhen")):
                if what == "param" and name not in ids:
                    problems.append(f"{kid}.{p['id']}: validWhen names unknown control {name!r}")
    for it in data["items"]:
        kind = data["kinds"].get(it["kind"])
        if not kind:
            problems.append(f"{it['id']}: unknown kind {it['kind']!r}")
            continue
        for p in kind["params"]:
            v = it["values"].get(p["id"], None)
            if p["id"] not in it["values"]:
                problems.append(f"{it['id']}: no value for {p['id']}")
            elif p["type"] == "choice" and v not in p["options"]:
                problems.append(f"{it['id']}.{p['id']}: {v!r} not one of {p['options']}")
            elif p["type"] == "toggle" and not isinstance(v, bool):
                problems.append(f"{it['id']}.{p['id']}: toggle needs true/false")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the expected visible controls per moment here")
    args = ap.parse_args()
    data = json.loads((HERE / "controls.json").read_text(encoding="utf-8"))
    demo = json.loads((HERE / "demo.json").read_text(encoding="utf-8"))
    problems = check(data)
    if problems:
        print("controls.json has problems:\n  " + "\n  ".join(problems))
        sys.exit(1)
    items = {it["id"]: json.loads(json.dumps(it)) for it in data["items"]}
    out = {}
    for name, steps in demo["moments"].items():
        state = {k: json.loads(json.dumps(v)) for k, v in items.items()}
        sel = None
        for s in steps:
            if s["op"] == "select":
                sel = s["item"]
            elif s["op"] == "set":
                state[s["item"]]["values"][s["param"]] = s["value"]
        it = state[sel]
        main_ids, more = shown(data["kinds"][it["kind"]], it)
        out[name] = {"item": sel, "shown": main_ids, "more": more}
        print(f"{name:18} {sel:8} shown: {', '.join(main_ids)}   more: {', '.join(more) or '-'}")
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("controls.json OK")


if __name__ == "__main__":
    main()
