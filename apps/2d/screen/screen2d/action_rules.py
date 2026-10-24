"""How the plain-data action list (actions.py) is read: what the selection is (its facts), and how an action's
"calls" (an operation name, a target rule and argument rules) become operation calls. No Qt.

An action's `when` is a condition in the one condition language (`rostrum_core.conditions.holds`, the same as a
field's `valid_when`), read on the selection's facts below. Its `calls`:

    {"op": "group.make", "target": "stack", "args": {"id": "$new:group", "as": "group"}}
    {"rule": "order", "how": "front"}                    a named rule that makes several calls (layer.arrange)
    {"rule": "depth", "value": 3.0}                      Set depth: layer.set_depth (kept where shown) + background.fit
    {"rule": "attach"} · {"rule": "frame", "how": "view"}  Attach to bone (rig_attach.py) · the frame's (frame_actions.py)
    {"rule": "pin", "on": True}                          Pin to frame / Unpin from frame: layer.pin (pin_depth.py)

Target rules: ids (in pick order) · stack (bottom first) · stack_but_top · rest (all but the first) · locked ·
unlocked · hidden · shown · not_copied · styled (texts following a style). Argument values starting with "$" are rules: $new:<type> (a fresh id, so the
screen can select what was made) · $at (the playhead in the first layer's own seconds) · $top (the top of the stack) ·
$first (the first picked) · $copied (the layer whose style was copied). Anything else is passed as it is.
"""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum2d.frame import TYPE as FRAME
from rostrum2d.names import display_name
from rostrum2d.ops_group import HOLDERS, _why_not
from rostrum2d.rig.bodynames import bodylike
from rostrum2d.rig.guess import guessable
from rostrum2d.rig.mirror import pairs as mirror_pairs
from rostrum_core.ids import counted
from rostrum_core.tree import index

from . import frame_actions, pin_depth, rig_attach
from .rig_mouths import is_eyes, is_mouth

SHAPES = ("shape", "path")


class Facts:
    """What the selection is. `ids` are in the order they were picked (the first is the primary); `stack` bottom first.
    `facts` holds the named truths an action's `when` reads. `state`: {"at": id -> its own seconds at the playhead,
    "copied": the layer whose style is copied ("" for none), "clipboard": layers can be pasted, "picked": the selection as
    the kit holds it, bones too} (screen state)."""

    def __init__(self, doc, ids: list[str], state: dict | None = None):
        self.state = {"at": lambda i: 0.0, "copied": "", "clipboard": False, "keys": [], **(state or {})}
        self.at, copied = self.state["at"], self.state["copied"]
        self.doc, self.ids, self.count = doc, ids, len(ids)
        self.items = [doc.item(i) for i in ids]
        self.kinds = {it["type"] for it in self.items}
        where = {i: doc.parent_of(i) for i in ids}
        parents = {w[0] for w in where.values()}
        self.stack = sorted(ids, key=lambda i: where[i][2])
        p = doc.item(next(iter(parents))) if len(parents) == 1 else None
        plain = [i for i, it in zip(ids, self.items) if it["type"] != FRAME]      # the frame is locked, never hidden
        self.lists = {"ids": ids, "stack": self.stack, "stack_but_top": self.stack[:-1], "rest": ids[1:],
                      "locked": [i for i, it in zip(ids, self.items) if it.get("locked")],
                      "hidden": [i for i in plain if doc.item(i).get("hidden")],
                      "not_copied": [i for i in ids if i != copied], "keys": list(self.state["keys"]),
                      "styled": [i for i, it in zip(ids, self.items) if it.get("textStyle")]}   # texts following a text style
        self.lists["comp"] = [_comp_of(doc, ids[0])] if ids else []   # the whole picture: the composition the layers are in
        self.lists["unlocked"] = [i for i in ids if i not in self.lists["locked"]]
        self.lists["shown"] = [i for i in plain if i not in self.lists["hidden"]]
        self.copied = copied if copied and doc.has(copied) else ""
        groupable = bool(p) and p["type"] in HOLDERS and p.get("layout", "none") == "none" and FRAME not in self.kinds
        groups = self.kinds == {"group"}
        self.facts = {
            "one": self.count == 1, "same_parent": p is not None, "groupable": groupable,
            "one_group": self.count == 1 and groups,       # a group alone: Ungroup, not "Group" echoing its own title
            "shapes": self.kinds <= set(SHAPES), "has_text": "text" in self.kinds, "has_frame": FRAME in self.kinds,
            "releasable": groups and all(_why_not(it, doc.item(where[it["id"]][0])) is None for it in self.items),
            "rigable": self.count > 1 or groups,           # Make rig: several parts, or a group of them (one rectangle has nothing to rig)
            "maskable": groupable and all(F.param(it["type"], "matte") for it in self.items),
            "matted": any(it.get("matte") for it in self.items) or (
                bool(p) and any(s.get("matte") in ids for s in p.get("layers", []))),
            "any_locked": bool(self.lists["locked"]), "any_unlocked": bool(self.lists["unlocked"]),
            "any_hidden": bool(self.lists["hidden"]), "any_shown": bool(self.lists["shown"]),
            "style_copied": bool(self.copied) and any(i != self.copied for i in ids),
            "clipboard": bool(self.state["clipboard"]), "keys_picked": bool(self.state["keys"]),
            "fills": self.kinds <= {"shape", "text", "path"},
            "texts": self.kinds == {"text"}, "styled": bool(self.lists["styled"]),    # Styles ▾ (text_styles.py)
            "picture": self.kinds <= {"image", "video", "render3d"},     # Fill the frame comes first for a photo or clip
            "picture_mix": bool(self.kinds & {"image", "video", "render3d"}) and bool(self.kinds & {"shape", "path", "text"}),   # Mask comes first
            "has_sound": bool(self.state.get("sound")) and FRAME not in self.kinds,   # Add a sound here (sound_cue_pick.py)
            # a character (rig/guess.py, rig_mouths.py): Bones from part names, Lip sync…, Add blinks…
            "bones_guessable": self.count == 1 and guessable(self.items[0]),
            "mirrorable": self.count == 1 and self.items[0]["type"] == "rig" and bool(mirror_pairs(self.items[0])),   # Mirror pose ▾ (rig/mirror.py)
            "attachable": rig_attach.pair(doc, list(self.state.get("picked", []))) is not None,   # a part + a bone
            "body_parts": groupable and p["type"] != "rig" and "rig" not in self.kinds and bodylike(_part_names(self.items)),   # Make rig first
            "mouth_set": self.count == 1 and is_mouth(self.items[0]),
            "eyes_set": self.count == 1 and is_eyes(self.items[0]),
            "depth_ok": self.kinds == {"drawing"} and bool(p) and p["type"] == "comp",   # Set depth: drawings of the scene itself
            **frame_actions.facts(self),                    # Frame the view, Cut here … (frame_actions.py)
            **pin_depth.facts(self)}                        # Pin to frame / Unpin from frame (pin_depth.py)


def _comp_of(doc, id_: str) -> str:
    while doc.item(id_)["type"] != "comp":
        id_ = doc.parent_of(id_)[0]
    return id_


def _part_names(items: list[dict]) -> list[str]:
    """The parts a selection would make a character of: one group's own layers, else the layers picked."""
    one = items[0] if len(items) == 1 and items[0]["type"] == "group" else None
    return [display_name(lay) for lay in (one.get("layers", []) if one else items)]


def calls_of(spec: dict | None, f: Facts, at) -> list[dict]:
    """An action's `calls` spec made into operation calls on this selection ([] = it would change nothing). `at(id)`:
    own seconds of the playhead."""
    if not spec:
        return []
    if "rule" in spec:
        return RULES[spec["rule"]](f, **{k: v for k, v in spec.items() if k != "rule"})
    target = f.lists[spec["target"]] if spec.get("target") else []
    if spec.get("target") and not target:
        return []
    args = {k: _arg(v, f, at) for k, v in spec.get("args", {}).items()}
    return [{"op": spec["op"], "target": list(target), "args": args}]


def _arg(v, f: Facts, at):
    if not (isinstance(v, str) and v.startswith("$")):
        return v
    name, _, rest = v[1:].partition(":")
    if name == "new":
        return counted(index(f.doc.data, f.doc.kind.lists), rest)
    if name == "at":
        return at(f.ids[0])
    if name in ("top", "first", "copied"):
        return {"top": f.stack[-1], "first": f.ids[0], "copied": f.copied}[name]
    raise ValueError(f"unknown argument rule {v!r} in the action list")


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


def _order(f: Facts, how: str) -> list[dict]:
    """layer.arrange calls that put each parent's stack in the new order (none when nothing would move)."""
    calls, by_parent = [], {}
    for layer in f.ids:
        by_parent.setdefault(f.doc.parent_of(layer)[0], set()).add(layer)
    for parent, picked in by_parent.items():
        now = [c["id"] for c in f.doc.item(parent)["layers"]]
        for i, id_ in enumerate(reordered(now, picked, how)):
            if now[i] != id_:
                calls.append({"op": "layer.arrange", "target": [id_], "args": {"index": i}})
                now.remove(id_)
                now.insert(i, id_)
    return calls


def _pose(f: Facts) -> list[dict]:
    """K: key.add fields "pose" on each selected layer at the playhead in its own seconds (one call per layer)."""
    return [{"op": "rig.key", "target": [i], "args": {"t": round(f.at(i), 6)}} if f.doc.item(i)["type"] == "rig"   # a rig: its bones' pose (rig/joints.py)
            else {"op": "key.add", "target": [i], "args": {"fields": "pose", "t": round(f.at(i), 6)}} for i in f.ids]


POSE_WORDS = {"x": "position", "y": "position", "scale": "scale", "zoom": "zoom", "rotation": "rotation", "opacity": "opacity"}


def cutter_name(call: dict, doc) -> str:
    """A mask.make call's cutter in words (the top layer of the selection cuts the others): `"Circle"`."""
    c = call["args"].get("cutter", "")
    return f'"{display_name(doc.item(c))}"' if c and doc.has(c) else "the top layer"


def said(calls: list[dict], label: str, doc) -> str:
    """The words a change is recorded and shown with: K says what it keyed ("Keyed 4 settings on 3 layers")."""
    cut = next((c for c in calls if c["op"] == "mask.make"), None)
    if cut:
        return f"{label} — {cutter_name(cut, doc)} is the cutter"
    pose = [c for c in calls if c["op"] == "key.add" and c["args"].get("fields") == "pose"]
    if not pose:
        return label
    words = {POSE_WORDS[k["prop"]] for c in pose for k in doc.item(c["target"][0]).get("keys", [])
             if k["prop"] in POSE_WORDS and k["t"] == c["args"]["t"]}
    n, m = len(words), len(pose)
    on = "the frame" if m == 1 and doc.item(pose[0]["target"][0])["type"] == FRAME else f"{m} layer{'s' if m != 1 else ''}"
    return f"Keyed {n} setting{'s' if n != 1 else ''} on {on}"


RULES = {"order": _order, "pose": _pose, "depth": pin_depth.depth_calls, "pin": pin_depth.calls, "frame": frame_actions.calls,
         "attach": lambda f: rig_attach.calls(f.doc, list(f.state.get("picked", [])))}
