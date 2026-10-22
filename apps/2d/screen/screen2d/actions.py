"""The one list of actions on selected layers (Group, Mask, Align, Lock, Delete, Bring forward …): select first, then
act (apps/2d/DESIGN.md). The action bar, the right-click menus, Ctrl+K and the shortcuts all read `available`, so they
always agree and nothing is greyed: an action is listed only when the selection allows it. Each action is one change
(all its calls in one apply) made of operations an agent calls too. Data only, no Qt.

An action: key (`layer:<name>`), label, shortcut, importance ("bar" = on the action bar, else "menu"), group (a divider
in menus), `bar` (the bar button it sits under, e.g. "Boolean"), valid(Facts), calls(Facts, state) -> operation calls.
`special` marks those that are not document changes: "copy" (remember the layer whose style is pasted), "rename", and
"clip_copy" / "clip_cut" (the system clipboard: clipboard.py; Cut also removes, one change). Paste is layer_order's.
"""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum_core.ids import counted
from rostrum_core.tree import index
from rostrum2d.ops_group import HOLDERS, _why_not

SHAPES = ("shape", "path")


class Facts:
    """What the selection is. `ids` are in the order they were picked (the first is the primary); `stack` bottom first."""

    def __init__(self, doc, ids: list[str]):
        self.doc, self.ids, self.count = doc, ids, len(ids)
        self.items = [doc.item(i) for i in ids]
        self.kinds = {it["type"] for it in self.items}
        where = {i: doc.parent_of(i) for i in ids}
        self.parents = {w[0] for w in where.values()}
        self.same_parent = len(self.parents) == 1
        self.stack = sorted(ids, key=lambda i: where[i][2])
        self.parent = doc.item(next(iter(self.parents))) if self.same_parent else None
        p = self.parent
        self.groupable = bool(p) and p["type"] in HOLDERS and p.get("layout", "none") == "none" and "camera" not in self.kinds
        self.shapes = self.kinds <= set(SHAPES)
        self.groups = self.kinds == {"group"}
        self.releasable = self.groups and all(_why_not(it, doc.item(where[it["id"]][0])) is None for it in self.items)
        self.maskable = self.groupable and all(F.param(it["type"], "matte") for it in self.items)
        self.matted = any(it.get("matte") for it in self.items) or (
            bool(p) and any(s.get("matte") in ids for s in p.get("layers", [])))
        self.plain = [i for i, it in zip(ids, self.items) if it["type"] != "camera"]
        self.locked = [i for i in self.plain if doc.item(i).get("locked")]
        self.hidden = [i for i in self.plain if doc.item(i).get("hidden")]


def _call(_op, target, /, **args):
    return {"op": _op, "target": list(target), "args": args}


def _fresh(f, type_):
    """An id for the layer an action makes, so the screen can select it afterwards."""
    return counted(index(f.doc.data, f.doc.kind.lists), type_)


def _make(how):
    return lambda f, st: [_call("group.make", f.stack, id=_fresh(f, "group"), **{"as": how})]


def _mask(mode):
    return lambda f, st: [_call("mask.make", f.stack[:-1], cutter=f.stack[-1], mode=mode, id=_fresh(f, "group"), at=st["at"](f.ids[0]))]


def _align(edge):
    return lambda f, st: [_call("layer.align", f.ids, edge=edge, at=st["at"](f.ids[0]))]


def _match(dims):
    return lambda f, st: [_call("layer.match_size", f.ids[1:], to=f.ids[0], dims=dims, at=st["at"](f.ids[0]))]


def _reorder(how):
    return lambda f, st: arrange_calls(f.doc, f.ids, how)


def reordered(stack: list[str], picked: set[str], how: str) -> list[str]:
    """The stack (index 0 = bottom) after moving the picked layers; their order among themselves stays."""
    mine, rest = [i for i in stack if i in picked], [i for i in stack if i not in picked]
    if how in ("front", "back"):
        return rest + mine if how == "front" else mine + rest
    out, step = list(stack), (1 if how == "forward" else -1)
    for i in (reversed(range(len(out))) if step > 0 else range(len(out))):
        j = i + step
        if out[i] in picked and 0 <= j < len(out) and out[j] not in picked:
            out[i], out[j] = out[j], out[i]
    return out


def arrange_calls(doc, layers: list[str], how: str) -> list[dict]:
    """layer.arrange calls that put each parent's stack in the new order (none when nothing would move)."""
    calls, by_parent = [], {}
    for layer in layers:
        by_parent.setdefault(doc.parent_of(layer)[0], set()).add(layer)
    for parent, picked in by_parent.items():
        now = [c["id"] for c in doc.item(parent)["layers"]]
        for i, id_ in enumerate(reordered(now, picked, how)):
            if now[i] != id_:
                calls.append(_call("layer.arrange", [id_], index=i))
                now.remove(id_)
                now.insert(i, id_)
    return calls


def _act(key, label, valid, calls=None, shortcut="", importance="menu", group="", bar="", special=""):
    return {"key": f"layer:{key}", "label": label, "shortcut": shortcut, "importance": importance, "group": group,
            "bar": bar, "valid": valid, "calls": calls, "special": special}


_MATTES = {"luma": "Use its brightness", "alphaInverted": "Outside its shape", "lumaInverted": "Use its darkness"}
_EDGES = {"left": "Align left", "hcenter": "Centre across", "right": "Align right", "top": "Align top",
          "vcenter": "Centre up and down", "bottom": "Align bottom"}
_ORDER = {"front": ("Bring to front", "Ctrl+Shift+]"), "forward": ("Bring forward", "Ctrl+]"),
          "backward": ("Send backward", "Ctrl+["), "back": ("Send to back", "Ctrl+Shift+[")}

ACTIONS = [
    _act("group", "Group", lambda f: f.groupable and f.count >= 2, _make("group"), "Ctrl+G", "bar", "make"),
    _act("ungroup", "Ungroup", lambda f: f.releasable, lambda f, st: [_call("group.release", f.ids)], "Ctrl+Shift+G", "bar", "make"),
    _act("clip", "Clip to a box", lambda f: f.groupable, _make("clip"), group="make"),
    _act("layout", "Auto layout (a row)", lambda f: f.groupable and f.count >= 2, _make("layout"), group="make"),
    _act("swap", "Make swap set", lambda f: f.groupable and f.count >= 2, _make("swap"), group="make"),
    _act("rig", "Make rig", lambda f: f.groupable, lambda f, st: [_call("rig.make", f.stack, id=_fresh(f, "rig"))], group="make"),
    _act("mask", "Mask with top layer", lambda f: f.maskable and f.count >= 2, _mask("alpha"), importance="bar", group="mask"),
    *[_act(f"mask_{m}", f"Mask: {words.lower()}", lambda f: f.maskable and f.count >= 2, _mask(m), group="mask") for m, words in _MATTES.items()],
    _act("release_mask", "Release mask", lambda f: f.matted,
         lambda f, st: [_call("mask.release", f.ids)], group="mask"),
    *[_act(op, op.capitalize(), lambda f: f.shapes and f.count >= 2 and f.same_parent,
           lambda f, st, op=op: [_call("shape.boolean", f.stack, op=op, id=_fresh(f, "path"))], importance="bar", group="shape", bar="Boolean")
      for op in ("union", "subtract", "intersect", "exclude")],
    *[_act(f"align_{e}", words, lambda f: f.groupable,
           _align(e), importance="bar", group="arrange", bar="Align") for e, words in _EDGES.items()],
    *[_act(f"distribute_{a}", words, lambda f: f.same_parent and f.count >= 3,
           lambda f, st, a=a: [_call("layer.distribute", f.ids, axis=a, at=st["at"](f.ids[0]))], importance="bar", group="arrange", bar="Distribute")
      for a, words in (("x", "Even gaps across"), ("y", "Even gaps down"))],
    *[_act(f"match_{d}", words, lambda f: f.count >= 2 and f.same_parent and "text" not in f.kinds and "camera" not in f.kinds, _match(d), group="arrange")
      for d, words in (("w", "Match width"), ("h", "Match height"), ("both", "Match size"))],
    _act("copy_style", "Copy style", lambda f: f.count == 1, group="look", special="copy"),
    _act("paste_style", "Paste style", lambda f: False, group="look"),          # valid only with a copied layer: see available()
    _act("lock", "Lock", lambda f: len(f.locked) < len(f.plain), lambda f, st: [_call("layer.lock", [i for i in f.plain if i not in f.locked])], group="state"),
    _act("unlock", "Unlock", lambda f: bool(f.locked), lambda f, st: [_call("layer.unlock", f.locked)], group="state"),
    _act("hide", "Hide", lambda f: len(f.hidden) < len(f.plain), lambda f, st: [_call("layer.hide", [i for i in f.plain if i not in f.hidden], on=True)], group="state"),
    _act("show", "Show", lambda f: bool(f.hidden), lambda f, st: [_call("layer.hide", f.hidden, on=False)], group="state"),
    _act("copy", "Copy", lambda f: True, shortcut="Ctrl+C", group="edit", special="clip_copy"),
    _act("cut", "Cut", lambda f: True, shortcut="Ctrl+X", group="edit", special="clip_cut"),
    _act("duplicate", "Duplicate", lambda f: True, lambda f, st: [_call("layer.duplicate", f.ids)], "Ctrl+D", group="edit"),
    _act("delete", "Delete", lambda f: True, lambda f, st: [_call("layer.remove", f.ids)], "Delete", group="edit"),
    *[_act(k, label, lambda f: True, _reorder(k), keys, group="order") for k, (label, keys) in _ORDER.items()],
    _act("rename", "Rename", lambda f: f.count == 1, shortcut="F2", group="order", special="rename"),
]


def available(doc, ids: list[str], state: dict) -> list[dict]:
    """The actions this selection allows, in menu order (each: key, label, shortcut, importance, group, bar, calls, special).
    A selection holding a locked layer is offered only Unlock. `state`: {"at": id -> own seconds of the playhead, "copied": the layer whose style is copied ("" for none)}."""
    if not ids:
        return []
    f, out = Facts(doc, ids), []
    for a in ACTIONS:
        if f.locked and a["key"] != "layer:unlock":
            continue                                    # a locked layer takes nothing until it is unlocked
        if a["key"] == "layer:paste_style":
            copied = state.get("copied", "")
            if not (copied and doc.has(copied) and any(i != copied for i in ids)):
                continue
            calls = lambda f, st: [_call("style.apply", [i for i in f.ids if i != st["copied"]], **{"from": st["copied"]})]
        elif a["valid"](f):
            calls = a["calls"]
        else:
            continue
        cs = calls(f, state) if calls else []
        if (calls and not cs) or (a["special"] == "" and not calls):
            continue                                    # a reorder that would move nothing
        out.append({**{k: v for k, v in a.items() if k not in ("valid", "calls")}, "calls": cs})
    return out
