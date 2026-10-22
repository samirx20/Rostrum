"""Rostrum2D's actions on selected layers (Group, Mask, Align, Lock, Delete, Bring forward …) as entries of the kit's
ONE action list (rostrum_gui/actions.py): select first, then act (INTERACTION.md 1.2). The context bar, the
right-click menus, Ctrl+K and the keys all read `LIST`, so they always agree and nothing is greyed. Each action is
one change (all its calls in one apply) made of operations an agent calls too. Data only, no Qt.

An action here is a kit `Action` (id `layer:<name>`): "primary" = on the context bar, else under ⋯ and in menus;
`group` a divider in menus; `bar` the bar button it sits under ("Boolean"). Shared keys come through `job`, 2D's own
through `keys` (keys2d.py). `do` marks what is not a document change by itself: "copy_style" (remember the layer
whose style is pasted), "rename", "clip_copy" / "clip_cut" / "paste" (the system clipboard: clipboard.py).
"""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum_core.ids import counted
from rostrum_core.tree import index
from rostrum2d.ops_group import HOLDERS, _why_not
from rostrum_gui.actions import Action, ActionList

from .keys2d import KEYS2D

SHAPES = ("shape", "path")


class Facts:
    """What the selection is. `ids` are in the order they were picked (the first is the primary); `stack` bottom first."""

    def __init__(self, doc, ids: list[str], state: dict | None = None):
        """`state`: {"at": id -> its own seconds at the playhead, "copied": the layer whose style is copied ("" for
        none), "clipboard": layers can be pasted} (screen state the actions read)."""
        self.doc, self.ids, self.count = doc, ids, len(ids)
        self.state = {"at": lambda i: 0.0, "copied": "", "clipboard": False, **(state or {})}
        self.at = self.state["at"]
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
    return lambda f: [_call("group.make", f.stack, id=_fresh(f, "group"), **{"as": how})]


def _mask(mode):
    return lambda f: [_call("mask.make", f.stack[:-1], cutter=f.stack[-1], mode=mode, id=_fresh(f, "group"), at=f.at(f.ids[0]))]


def _align(edge):
    return lambda f: [_call("layer.align", f.ids, edge=edge, at=f.at(f.ids[0]))]


def _match(dims):
    return lambda f: [_call("layer.match_size", f.ids[1:], to=f.ids[0], dims=dims, at=f.at(f.ids[0]))]


def _reorder(how):
    return lambda f: arrange_calls(f.doc, f.ids, how)


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


def _act(key, label, valid, calls=None, importance="secondary", group="", bar="", do="", unlocked=True, **kw):
    """A kit Action. `unlocked`: a selection holding a locked layer takes nothing but Unlock until it is unlocked."""
    ok = (lambda f: not f.locked and valid(f)) if unlocked else valid
    return Action(f"layer:{key}", label, valid=ok, calls=calls, importance=importance, group=group, bar=bar, do=do, **kw)


def _paste_style(f):
    c = f.state["copied"]
    return [_call("style.apply", [i for i in f.ids if i != c], **{"from": c})] if c and f.doc.has(c) else []


_MATTES = {"luma": "Use its brightness", "alphaInverted": "Outside its shape", "lumaInverted": "Use its darkness"}
_EDGES = {"left": ("Align left", "align_left"), "hcenter": ("Centre across", "centre_across"),
          "right": ("Align right", "align_right"), "top": ("Align top", "align_top"),
          "vcenter": ("Centre up and down", "centre_down"), "bottom": ("Align bottom", "align_bottom")}
_ORDER = {"front": "Bring to front", "forward": "Bring forward", "backward": "Send backward", "back": "Send to back"}
_ANY = lambda f: True                                                      # noqa: E731
_SHAPES = lambda f: f.shapes and f.same_parent                             # noqa: E731

ACTIONS = [
    _act("group", "Group", lambda f: f.groupable, _make("group"), "primary", "make", job="group", min_targets=2),
    _act("ungroup", "Ungroup", lambda f: f.releasable, lambda f: [_call("group.release", f.ids)], "primary", "make",
         job="ungroup"),
    _act("clip", "Clip to a box", lambda f: f.groupable, _make("clip"), group="make"),
    _act("layout", "Auto layout (a row)", lambda f: f.groupable, _make("layout"), group="make", job="auto_layout",
         min_targets=2),
    _act("swap", "Make swap set", lambda f: f.groupable, _make("swap"), group="make", min_targets=2),
    _act("rig", "Make rig", lambda f: f.groupable, lambda f: [_call("rig.make", f.stack, id=_fresh(f, "rig"))], group="make"),
    _act("mask", "Mask with top layer", lambda f: f.maskable, _mask("alpha"), "primary", "mask", job="mask",
         min_targets=2),
    *[_act(f"mask_{m}", f"Mask: {words.lower()}", lambda f: f.maskable, _mask(m), group="mask", min_targets=2)
      for m, words in _MATTES.items()],
    _act("release_mask", "Release mask", lambda f: f.matted, lambda f: [_call("mask.release", f.ids)], group="mask"),
    *[_act(op, op.capitalize(), _SHAPES, lambda f, op=op: [_call("shape.boolean", f.stack, op=op, id=_fresh(f, "path"))],
           "primary", "shape", "Boolean", job=op, min_targets=2, kinds=SHAPES, promoted=lambda f: True)
      for op in ("union", "subtract", "intersect", "exclude")],
    *[_act(f"align_{e}", words, lambda f: f.groupable, _align(e), "primary", "arrange", "Align", job=job)
      for e, (words, job) in _EDGES.items()],
    *[_act(f"distribute_{a}", words, lambda f: f.same_parent,
           lambda f, a=a: [_call("layer.distribute", f.ids, axis=a, at=f.at(f.ids[0]))], "primary", "arrange",
           "Distribute", min_targets=3) for a, words in (("x", "Even gaps across"), ("y", "Even gaps down"))],
    *[_act(f"match_{d}", words, lambda f: f.same_parent and "text" not in f.kinds and "camera" not in f.kinds,
           _match(d), group="arrange", min_targets=2)
      for d, words in (("w", "Match width"), ("h", "Match height"), ("both", "Match size"))],
    _act("copy_style", "Copy style", _ANY, group="look", do="copy_style", job="copy_style", max_targets=1),
    _act("paste_style", "Paste style", _ANY, _paste_style, group="look", job="paste_style"),
    _act("lock", "Lock", lambda f: len(f.locked) < len(f.plain),
         lambda f: [_call("layer.lock", [i for i in f.plain if i not in f.locked])], group="state", job="lock"),
    _act("unlock", "Unlock", lambda f: bool(f.locked), lambda f: [_call("layer.unlock", f.locked)], group="state",
         job="lock", unlocked=False),
    _act("hide", "Hide", lambda f: len(f.hidden) < len(f.plain),
         lambda f: [_call("layer.hide", [i for i in f.plain if i not in f.hidden], on=True)], group="state", job="hide"),
    _act("show", "Show", lambda f: bool(f.hidden), lambda f: [_call("layer.hide", f.hidden, on=False)], group="state",
         job="hide"),
    *[_act(k, label, _ANY, _reorder(k), group="order", job=k) for k, label in _ORDER.items()],
    # the edit block (the kit puts it last in the right-click menu, never on the bar): keys and menus only
    _act("copy", "Copy", _ANY, do="clip_copy", job="copy"),
    _act("cut", "Cut", _ANY, do="clip_cut", job="cut"),
    _act("paste", "Paste", lambda f: f.state["clipboard"], do="paste", job="paste", min_targets=0, unlocked=False),
    _act("duplicate", "Duplicate", _ANY, lambda f: [_call("layer.duplicate", f.ids)], job="duplicate"),
    _act("rename", "Rename", _ANY, do="rename", job="rename", max_targets=1),
    _act("delete", "Delete", _ANY, lambda f: [_call("layer.remove", f.ids)], job="delete"),
]

LIST = ActionList(ACTIONS, KEYS2D, noun="layer")
