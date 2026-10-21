"""When a control or operation is valid: the whole condition language (from S3 proofs/gui-mock/controls.json).

    {"is": [name, value]}   the field `name` of the target equals value
    {"not": c}  {"all": [c, ...]}  {"any": [c, ...]}
    {"fact": name}          a fact the document kind reports about the item (e.g. a clip has audio)
    None                    always valid
"""
from __future__ import annotations


def holds(cond, values: dict, facts: dict | None = None) -> bool:
    if cond is None:
        return True
    facts = facts or {}
    if "is" in cond:
        name, want = cond["is"]
        return values.get(name) == want
    if "not" in cond:
        return not holds(cond["not"], values, facts)
    if "all" in cond:
        return all(holds(c, values, facts) for c in cond["all"])
    if "any" in cond:
        return any(holds(c, values, facts) for c in cond["any"])
    if "fact" in cond:
        return bool(facts.get(cond["fact"], False))
    raise ValueError(f"unknown condition {cond!r}")


def refs(cond) -> list[tuple[str, str]]:
    """[("param", name) | ("fact", name)]: what a condition reads, for checking registrations."""
    if not cond:
        return []
    if "is" in cond:
        return [("param", cond["is"][0])]
    if "not" in cond:
        return refs(cond["not"])
    if "fact" in cond:
        return [("fact", cond["fact"])]
    if "all" in cond or "any" in cond:
        return [r for c in cond.get("all", cond.get("any")) for r in refs(c)]
    raise ValueError(f"unknown condition {cond!r}")


def check_refs(cond, names) -> list[str]:
    """Problems with a condition: unknown keys or fields it names that don't exist."""
    try:
        return [f"valid_when names unknown field {n!r}" for k, n in refs(cond) if k == "param" and n not in names]
    except ValueError as e:
        return [str(e)]


def describe(cond) -> str:
    """Plain words for an error: 'dof is True', 'type is Spot and ...'."""
    if cond is None:
        return "always"
    if "is" in cond:
        return f"{cond['is'][0]} is {cond['is'][1]!r}"
    if "not" in cond:
        return f"not ({describe(cond['not'])})"
    if "fact" in cond:
        return f"the item {cond['fact']}"
    joiner = " and " if "all" in cond else " or "
    return joiner.join(describe(c) for c in cond.get("all", cond.get("any", [])))
