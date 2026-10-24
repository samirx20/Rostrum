"""The one list of actions on selected layers (Group, Mask, Align, Lock, Delete, Bring forward …): select first, then
act (apps/2d/UX_SPEC.md 4.3, shared/gui-kit/INTERACTION.md 1.2). The context bar, the right-click menus, Ctrl+K and
the shortcuts all read `available`, so they always agree and nothing is greyed: an action is listed only when the
selection allows it. Each action is one change (all its calls in one apply) made of operations an agent calls too.

PLAIN DATA, read into the kit's one action list (rostrum_gui/actions.py, ACTIONS.md): id, label, job (a key map job:
its key comes from the key map, shared or keys2d.py), importance ("primary" = on the context bar, "secondary" = under ⋯
and in menus), rank (lower first), group (menu divider), bar (the button or side menu it sits under: Combine, Mask,
Align, Make, Match, Order), min_targets / max_targets / kinds, `when` (a condition on the selection's facts, in the
one condition language: action_rules.Facts lists them), `panel` (False: not in the settings panel's actions — keys, Ctrl+K), `promoted` (True, or a fact: while it holds the action comes
first; a secondary one is then the context bar's first button, out of its `bar` menu: Make rig on parts named like a
body), `calls` (an operation, a target rule and argument rules: action_rules.py) or `do` (not a document change: the clipboard, copy style, rename). A selection holding a locked
layer is offered only what is marked `locked_ok` (Unlock, Paste); one holding the frame (what the scene exports, never
grouped, masked, copied or deleted) only what is marked `frame_ok` (Lock, Unlock, K, its keys' eases, frame_actions.py).
"""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum_gui.actions import SHORT_MENU, Action, ActionList

from . import cover_move, frame_actions, pin_depth
from .action_rules import Facts, calls_of
from .eases import EASES
from .keys2d import KEYS2D

__all__ = ["ACTIONS", "DATA", "Facts", "LIST"]

FACT, NOT = (lambda name: {"fact": name}), (lambda name: {"not": {"fact": name}})
ALL = lambda *names: {"all": [{"fact": n} for n in names]}   # noqa: E731


def _op(name, target, **args):
    return {"op": name, "target": target, "args": args}


def _a(id_, label, *, rank=100, importance="secondary", group="", bar="", job="", when=None, calls=None, do="",
       min_targets=1, max_targets=None, kinds=None, locked_ok=False, frame_ok=False, promoted=False, why="", panel=True, icon=""):
    return {"frame_ok": frame_ok, "icon": icon, "panel": panel, "id": id_, "label": label, "rank": rank, "importance": importance, "group": group, "bar": bar, "job": job,
            "when": when, "calls": calls, "do": do, "min_targets": min_targets, "max_targets": max_targets,
            "kinds": kinds, "locked_ok": locked_ok, "promoted": promoted, "why": why}


_MATTES = {"luma": "By its brightness", "alphaInverted": "Outside its shape", "lumaInverted": "By its darkness"}
_EDGES = {"left": ("Align left", "align_left"), "hcenter": ("Align centre", "centre_across"),
          "right": ("Align right", "align_right"), "top": ("Align top", "align_top"),
          "vcenter": ("Align middle", "centre_down"), "bottom": ("Align bottom", "align_bottom")}
def _to_frame(words: str):
    """An align's label: one layer aligns to the frame, so it says so ("Align left to the frame")."""
    return lambda f, w=words: w + " to the frame" if f.count == 1 else w


_ORDER = {"front": "Bring to front", "forward": "Bring forward", "backward": "Send backward", "back": "Send to back"}
_DEPTHS = {"far": 3.0, "middle": 1.0, "near": 0.25}        # the depths background.add's defaults use (far → near)
_MASK = lambda m: _op("mask.make", "stack_but_top", cutter="$top", mode=m, id="$new:group", at="$at")   # noqa: E731

DATA = [
    _a("group", "Group", rank=10, importance="primary", group="make", job="group", min_targets=2,
       when={"all": [FACT("groupable"), NOT("one_group")]}, calls=_op("group.make", "stack", id="$new:group", **{"as": "group"})),
    _a("ungroup", "Ungroup", rank=10, importance="primary", group="make", job="ungroup", when=FACT("releasable"),
       calls=_op("group.release", "ids")),
    _a("clip", "Crop to a box", rank=60, group="make", bar="Make", when=FACT("groupable"),
       calls=_op("group.make", "stack", id="$new:group", **{"as": "clip"})),
    _a("layout", "Auto layout (a row)", rank=60, group="make", bar="Make", job="auto_layout", min_targets=2, when=FACT("groupable"),
       calls=_op("group.make", "stack", id="$new:group", **{"as": "layout"})),
    _a("swap", "Make swap set", rank=60, group="make", bar="Make", min_targets=2, when=FACT("groupable"),
       calls=_op("group.make", "stack", id="$new:group", **{"as": "swap"})),
    _a("rig", "Make rig", rank=60, group="make", bar="Make", when=ALL("groupable", "rigable"), promoted="body_parts",
       calls=_op("rig.make", "stack", id="$new:rig")),
    # a character (UX_SPEC 3.23): a rig with no bones named like a body; a mouth or an eyes swap set
    _a("guess_bones", "Bones from part names", rank=8, importance="primary", group="make", max_targets=1,
       when=FACT("bones_guessable"), calls=_op("rig.guess_bones", "ids")),
    _a("attach", "Attach to bone", rank=8, importance="primary", group="make", when=FACT("attachable"), calls={"rule": "attach"},
       why="Select a part of a rig, then Ctrl+click the bone it should follow"),
    *[_a(f"mirror_{how}", words, rank=65, importance="primary", group="make", bar="Mirror pose", max_targets=1, when=FACT("mirrorable"),
         calls=_op("pose.mirror", "ids", how=how, t="$at"))
      for how, words in (("left_to_right", "Left side onto the right"), ("right_to_left", "Right side onto the left"),
                         ("swap", "Swap left and right"))],
    _a("lipsync", "Lip sync…", rank=8, importance="primary", group="make", max_targets=1, when=FACT("mouth_set"), do="lipsync"),
    _a("blinks", "Add blinks…", rank=8, importance="primary", group="make", max_targets=1, when=FACT("eyes_set"), do="blinks"),
    _a("mask", "Mask: by its shape", rank=20, importance="primary", group="mask", bar="Mask", job="mask", min_targets=2,
       when=FACT("maskable"), calls=_MASK("alpha"), promoted="picture_mix"),
    *[_a(f"mask_{m}", f"Mask: {words.lower()}", rank=20, importance="primary", group="mask", bar="Mask", min_targets=2, when=FACT("maskable"),
         calls=_MASK(m), promoted="picture_mix") for m, words in _MATTES.items()],
    _a("release_mask", "Release mask", rank=20, importance="primary", group="mask", bar="Mask", when=FACT("matted"), calls=_op("mask.release", "ids")),
    *[_a(op, op.capitalize(), rank=5, importance="primary", group="shape", bar="Combine", job=op, min_targets=2,
         when=ALL("shapes", "same_parent"), promoted=True, calls=_op("shape.boolean", "stack", op=op, id="$new:path"), icon=op)
      for op in ("union", "subtract", "intersect", "exclude")],
    *[_a(f"align_{e}", _to_frame(words), rank=30, importance="primary", group="arrange", bar="Align", job=job, when=FACT("groupable"),
         calls=_op("layer.align", "ids", edge=e, at="$at"), icon="align-" + e) for e, (words, job) in _EDGES.items()],
    *[_a(f"distribute_{ax}", words, rank=40, importance="primary", group="arrange", bar="Distribute", min_targets=3,
         when=FACT("same_parent"), calls=_op("layer.distribute", "ids", axis=ax, at="$at"), icon="distribute-" + ax)
      for ax, words in (("x", "Even gaps across"), ("y", "Even gaps down"))],
    *[_a(f"match_{d}", words, rank=70, group="arrange", bar="Match", min_targets=2,
         when={"all": [FACT("same_parent"), NOT("has_text")]},
         calls=_op("layer.match_size", "rest", to="$first", dims=d, at="$at"),
         why=f"{words} needs two or more layers (shapes, pictures, groups) in one place. Text has no size of its own: leave it out.")
      for d, words in (("w", "Match width"), ("h", "Match height"), ("both", "Match size"))],
    _a("fill_frame", "Fill the frame", rank=65, group="arrange", bar="Fit to frame",   # one control, two ways (on the bar for a picture or clip, else under ⋯)
       when={"all": [FACT("groupable"), NOT("has_text")]}, calls=_op("layer.fill_frame", "ids", mode="cover", at="$at")),
    _a("fit_inside", "Fit inside the frame", rank=66, group="arrange", bar="Fit to frame",
       when={"all": [FACT("groupable"), NOT("has_text")]}, calls=_op("layer.fill_frame", "ids", mode="inside", at="$at")),
    *[_a(f"depth_{k}", f"{k.capitalize()} ({v:g})", rank=75, importance="primary", group="arrange", bar="Set depth",
         kinds=("drawing",), when=FACT("depth_ok"), calls={"rule": "depth", "value": v},
         why="Set depth is for drawings of the scene itself, not inside a group.")
      for k, v in _DEPTHS.items()],
    _a("depth_typed", "Other depth…", rank=76, importance="primary", group="arrange", bar="Set depth", kinds=("drawing",),
       when=FACT("depth_ok"), do="depth", why="Set depth is for drawings of the scene itself, not inside a group."),
    *pin_depth.data(_a), *cover_move.data(_a),                             # Pin to frame / Unpin, Cover the frame's move
    _a("stagger", "Stagger…", rank=35, importance="primary", group="arrange", min_targets=2, do="stagger"),
    _a("sound_here", "Add a sound here…", rank=40, group="arrange", max_targets=1, when=FACT("has_sound"), do="sound_here",
       why="Ties a sound from Sound's library to the layer's start; RostrumSound mixes it"),
    _a("key_here", "Key here", rank=45, group="animate", job="key_here", calls={"rule": "pose"}, panel=False, frame_ok=True),   # K; the diamonds
    *frame_actions.data(_a, lambda how: {"rule": "frame", "how": how}),    # Frame the view, Cut here … (frame_actions.py)
    *[_a(f"ease_{e['value']}", f"Ease: {e['label']}", rank=50, group="animate", bar="Ease", job=e["job"],
         when=FACT("keys_picked"), calls=_op("key.set", "keys", ease=e["value"]), panel=False, frame_ok=True) for e in EASES if e["value"] != "custom"],
    # Styles ▾ on texts (rostrum2d/text_styles.py): the document's styles come first (_List.available adds them)
    _a("style_save", "Save as style", rank=81, importance="primary", group="look", bar="Styles", kinds=("text",),
       max_targets=1, when=NOT("styled"), calls=_op("style.define", "ids")),
    _a("style_detach", "Detach style", rank=81, importance="primary", group="look", bar="Styles", kinds=("text",),
       when=FACT("styled"), calls=_op("style.detach", "styled")),
    _a("copy_style", "Copy style", rank=80, group="look", job="copy_style", max_targets=1, do="copy_style"),
    _a("paste_style", "Paste style", rank=80, group="look", job="paste_style", when=FACT("style_copied"),
       calls=_op("style.apply", "not_copied", **{"from": "$copied"})),
    _a("lock", "Lock", rank=90, group="state", job="lock", when=FACT("any_unlocked"), calls=_op("layer.lock", "unlocked"),
       frame_ok=True),
    _a("unlock", "Unlock", rank=90, group="state", job="lock", when=FACT("any_locked"), locked_ok=True, frame_ok=True,
       calls=_op("layer.unlock", "locked")),
    _a("hide", "Hide", rank=90, group="state", job="hide", when=FACT("any_shown"), calls=_op("layer.hide", "shown", on=True)),
    _a("show", "Show", rank=90, group="state", job="hide", when=FACT("any_hidden"), calls=_op("layer.hide", "hidden", on=False)),
    _a("copy", "Copy", rank=100, group="edit", job="copy", do="clip_copy"),
    _a("cut", "Cut", rank=100, group="edit", job="cut", do="clip_cut"),
    _a("paste", "Paste", rank=100, group="edit", job="paste", do="paste", min_targets=0, when=FACT("clipboard"),
       locked_ok=True),
    _a("duplicate", "Duplicate", rank=100, group="edit", job="duplicate", calls=_op("layer.duplicate", "ids")),
    _a("delete", "Delete", rank=100, group="edit", job="delete", calls=_op("layer.remove", "ids")),
    *[_a(k, label, rank=110, group="order", bar="Order", job=k, calls={"rule": "order", "how": k}, panel=False) for k, label in _ORDER.items()],
    _a("rename", "Rename", rank=110, group="order", job="rename", max_targets=1, do="rename"),
]


_UNLOCKED = {"not": {"fact": "any_locked"}}
_NO_FRAME = {"not": {"fact": "has_frame"}}


def _action(d: dict) -> Action:
    """One data entry as a kit Action: the locked and frame rules join its `when`; its calls are read by action_rules."""
    rules = ([] if d["locked_ok"] else [_UNLOCKED]) + ([] if d["frame_ok"] else [_NO_FRAME]) + ([d["when"]] if d["when"] else [])
    when = {"all": rules} if len(rules) > 1 else rules[0] if rules else None
    calls = (lambda f, spec=d["calls"]: calls_of(spec, f, f.at)) if d["calls"] else None
    return Action(f"layer:{d['id']}", d["label"], when=when, kinds=d["kinds"], min_targets=d["min_targets"],
                  max_targets=d["max_targets"], importance=d["importance"], rank=d["rank"], job=d["job"],
                  group=d["group"], bar=d["bar"], calls=calls, do=d["do"], why=d["why"], panel=d["panel"],
                  promoted=_promoted(d["promoted"]), icon=d["icon"])


def _promoted(p):
    if not p:
        return None
    return (lambda f: True) if p is True else (lambda f, name=p: bool(f.facts.get(name)))


class _List(ActionList):
    """The kit's list (promoted actions first), where a secondary action promoted now also joins the context bar as
    its own button (not in its `bar` menu): the selection makes it the obvious next step. Primaries keep their bar."""

    def available(self, facts) -> list[dict]:
        now = {a.id for a in self.actions if a.promoted and a.importance != "primary" and a.promoted(facts)}
        out = [{**e, "importance": "primary", "bar": ""} if e["id"] in now else e for e in super().available(facts)]
        if facts.facts.get("picture"):                # a photo or clip: Fit to frame is on the bar, first
            out = [{**e, "importance": "primary", "rank": 0} if e["bar"] == "Fit to frame" else e for e in out]
            out.sort(key=lambda e: e["rank"] != 0)
        uses = _style_uses(facts)
        if not facts.doc.data.get("textStyles"):      # no style yet: no Styles ▾, Save as style sits under ⋯
            out = [{**e, "importance": "secondary", "bar": ""} if e["bar"] == "Styles" else e for e in out]
        at = next((n for n, e in enumerate(out) if e["bar"] == "Styles"), len(out))
        return out[:at] + uses + out[at:]

    def owns(self, key: str) -> bool:
        """Whether `key` is one of this list's actions (the document's styles included)."""
        return key.startswith(STYLE_USE) or any(a.id == key for a in self.actions)


STYLE_USE = "layer:style_use:"


def _style_uses(f) -> list[dict]:
    """Styles ▾'s first part: each of the document's text styles the selected texts don't all follow yet (one change:
    style.use). Built from the document, so not in DATA."""
    if f.facts.get("texts") is not True or f.facts.get("any_locked"):
        return []
    return [{"id": STYLE_USE + s["id"], "label": s["name"], "keys": "", "importance": "primary", "group": "look",
             "bar": "Styles", "calls": [{"op": "style.use", "target": list(f.ids), "args": {"style": s["id"]}}],
             "do": "", "edit": False, "rank": 81, "job": ""}
            for s in f.doc.data.get("textStyles", []) if any(it.get("textStyle") != s["id"] for it in f.items)]


ACTIONS = [_action(d) for d in DATA]
# the right-click's Order block is all four moves (only those that would move something are there), never one alone
SHORT = tuple((n, ("front", "forward", "backward", "back") if n == "order" else jobs) for n, jobs in SHORT_MENU)
LIST = _List(ACTIONS, KEYS2D, noun="layer", short_menu=SHORT)
