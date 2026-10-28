"""Limbs thin next to their body: a limb() arm or leg whose width is well under what limb() would give it without widths
(limb.BODY_SHARE of the body's width). Read from the document alone (cheap): named in run_script's reply (advice.py) and
by look_review (mcp/review_limbs.py), once per character. A fact with numbers, not taste: a stick figure may be meant."""
from __future__ import annotations

from .limb import BODY_SHARE, body_width

THIN = 0.7        # a limb under this share of limb()'s own width for its body is named


def _limbs(rig: dict):
    """(kind, stem, its widest part's width, the bone it hangs from) for each limb() limb in the rig: arms have no IK,
    legs do."""
    bones, layers, stack = {b["id"]: b for b in rig.get("bones", [])}, {}, list(rig.get("layers", []))
    while stack:
        n = stack.pop()
        layers[n.get("id")] = n
        stack += n.get("layers", [])
    driven = {k.get("bone") for k in rig.get("iks", [])}
    for bid in bones:
        stem = bid[:-len("_upper")]
        if bid.endswith("_upper") and f"{stem}_lower" in bones:
            part = layers.get(stem) or layers.get(f"{stem}_upper_part")
            if part is not None and part.get("w"):
                yield ("leg" if f"{stem}_lower" in driven else "arm"), stem, float(part["w"]), bones[bid].get("parent", "")


def thin_limbs(rig: dict) -> list[dict]:
    """{kind, ids, px, body, want} per limb kind that is thin next to its body, for one rig node."""
    skip = {i for _, s, _, _ in _limbs(rig) for i in (s, f"{s}_upper_part", f"{s}_lower_part", f"{s}_joint", f"{s}_hand", f"{s}_foot")}
    by_kind: dict[str, dict] = {}
    found = [(kind, stem, w, body_width(rig, parent, skip)) for kind, stem, w, parent in _limbs(rig)]
    for kind, stem, w, body in found:
        body = body or max((b for _, _, _, b in found), default=0.0)     # legs on a bare hip: the arms' body
        if not body:
            continue
        want = BODY_SHARE[kind] * body
        if w < THIN * want:
            row = by_kind.setdefault(kind, {"kind": kind, "ids": [], "px": w, "body": body, "want": want})
            row["ids"].append(stem)
            row["px"] = min(row["px"], w)
    return list(by_kind.values())


def say(rig_id: str, rows: list[dict]) -> str:
    """'character "app": the arms are 44 px wide on a 250 px body (…)'."""
    parts = [f'the {r["kind"]}s are {r["px"]:.0f} px wide' for r in rows]
    want = " / ".join(f'{r["want"]:.0f} px' for r in rows)
    body = max(r["body"] for r in rows)
    return (f'character "{rig_id}": {" and ".join(parts)} on a {body:.0f} px body (thin as a stick at video size; leave '
            f'widths out of limb() to size them from the body, or about {want})')


def rigs(holder: dict):
    """Every rig node under a document, comp or layer."""
    todo = [holder]
    while todo:
        n = todo.pop()
        if n.get("type") == "rig":
            yield n
        for key in ("comps", "layers"):
            todo += [c for c in n.get(key, []) if isinstance(c, dict)]
