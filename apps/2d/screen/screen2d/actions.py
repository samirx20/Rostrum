"""The one list of actions on selected layers (Group, Mask, Align, Lock, Delete, Bring forward …): select first, then
act (apps/2d/UX_SPEC.md 4.3, shared/gui-kit/INTERACTION.md 1.2). The context bar, the right-click menus, Ctrl+K and
the shortcuts all read `available`, so they always agree and nothing is greyed: an action is listed only when the
selection allows it. Each action is one change (all its calls in one apply) made of operations an agent calls too.

PLAIN DATA, shaped for the kit's one action list (rostrum_gui/actions.py `Action`, S31), so it moves there with no
rework: id, label, job (a key map job: its key comes from the key map) or keys (2D's own key), importance ("primary" =
on the context bar, "secondary" = under ⋯ and in menus), rank (lower first), group (menu divider), bar (the context bar
button it sits under), min_targets / max_targets / kinds, `when` (a condition on the selection's facts, in the one
condition language: action_rules.Facts lists the facts), `calls` (an operation, a target rule and argument rules:
action_rules.py) or `do` (not a document change: copy / cut to the clipboard, remember a style, rename). A selection
holding a locked layer is offered only what is marked `locked_ok` (Unlock).
"""
from __future__ import annotations

from .action_rules import Facts, allows, calls_of

# The shared keys these actions use (INTERACTION.md Part 2). Until the kit's key map (S31) is in main; then
# KeyMap("2d", APP_KEYS).key_of(job) replaces this table.
SHARED_KEYS = {"group": "Ctrl+G", "ungroup": "Ctrl+Shift+G", "copy": "Ctrl+C", "cut": "Ctrl+X", "duplicate": "Ctrl+D",
               "delete": "Delete", "rename": "F2", "forward": "Ctrl+]", "backward": "Ctrl+[", "front": "Ctrl+Shift+]",
               "back": "Ctrl+Shift+[", "hide": "Ctrl+Shift+H", "lock": "Ctrl+Shift+L", "copy_style": "Ctrl+Alt+C",
               "paste_style": "Ctrl+Alt+V"}

FACT = lambda name: {"fact": name}            # noqa: E731
NOT = lambda name: {"not": {"fact": name}}    # noqa: E731
ALL = lambda *names: {"all": [{"fact": n} for n in names]}   # noqa: E731


def _op(name, target, **args):
    return {"op": name, "target": target, "args": args}


def _a(id_, label, *, rank=100, importance="secondary", group="", bar="", job="", keys="", when=None, calls=None,
       do="", min_targets=1, max_targets=None, kinds=None, locked_ok=False):
    return {"id": id_, "label": label, "rank": rank, "importance": importance, "group": group, "bar": bar, "job": job,
            "keys": keys, "when": when, "calls": calls, "do": do, "min_targets": min_targets, "max_targets": max_targets,
            "kinds": kinds, "locked_ok": locked_ok}


_MATTES = {"luma": "Use its brightness", "alphaInverted": "Outside its shape", "lumaInverted": "Use its darkness"}
_EDGES = {"left": ("Align left", "Alt+A"), "hcenter": ("Centre across", "Alt+H"), "right": ("Align right", "Alt+D"),
          "top": ("Align top", "Alt+W"), "vcenter": ("Centre up and down", "Alt+V"), "bottom": ("Align bottom", "Alt+S")}
_BOOLEANS = {"union": "Ctrl+Alt+U", "subtract": "Ctrl+Alt+S", "intersect": "Ctrl+Alt+I", "exclude": "Ctrl+Alt+X"}
_ORDER = {"front": "Bring to front", "forward": "Bring forward", "backward": "Send backward", "back": "Send to back"}
_MASK = lambda m: _op("mask.make", "stack_but_top", cutter="$top", mode=m, id="$new:group", at="$at")   # noqa: E731

ACTIONS = [
    _a("group", "Group", rank=10, importance="primary", group="make", job="group", min_targets=2, when=FACT("groupable"),
       calls=_op("group.make", "stack", id="$new:group", **{"as": "group"})),
    _a("ungroup", "Ungroup", rank=10, importance="primary", group="make", job="ungroup", when=FACT("releasable"),
       calls=_op("group.release", "ids")),
    _a("clip", "Clip to a box", rank=60, group="make", when=FACT("groupable"),
       calls=_op("group.make", "stack", id="$new:group", **{"as": "clip"})),
    _a("layout", "Auto layout (a row)", rank=60, group="make", keys="Shift+A", min_targets=2, when=FACT("groupable"),
       calls=_op("group.make", "stack", id="$new:group", **{"as": "layout"})),
    _a("swap", "Make swap set", rank=60, group="make", min_targets=2, when=FACT("groupable"),
       calls=_op("group.make", "stack", id="$new:group", **{"as": "swap"})),
    _a("rig", "Make rig", rank=60, group="make", when=FACT("groupable"), calls=_op("rig.make", "stack", id="$new:rig")),
    _a("mask", "Mask with top layer", rank=20, importance="primary", group="mask", keys="Ctrl+Alt+M", min_targets=2,
       when=FACT("maskable"), calls=_MASK("alpha")),
    *[_a(f"mask_{m}", f"Mask: {words.lower()}", rank=70, group="mask", min_targets=2, when=FACT("maskable"),
         calls=_MASK(m)) for m, words in _MATTES.items()],
    _a("release_mask", "Release mask", rank=20, group="mask", when=FACT("matted"), calls=_op("mask.release", "ids")),
    *[_a(op, op.capitalize(), rank=5, importance="primary", group="shape", bar="Combine", keys=key, min_targets=2,
         when=ALL("shapes", "same_parent"), calls=_op("shape.boolean", "stack", op=op, id="$new:path"))
      for op, key in _BOOLEANS.items()],
    *[_a(f"align_{e}", words, rank=30, importance="primary", group="arrange", bar="Align", keys=key, when=FACT("groupable"),
         calls=_op("layer.align", "ids", edge=e, at="$at")) for e, (words, key) in _EDGES.items()],
    *[_a(f"distribute_{ax}", words, rank=40, importance="primary", group="arrange", bar="Distribute", min_targets=3,
         when=FACT("same_parent"), calls=_op("layer.distribute", "ids", axis=ax, at="$at"))
      for ax, words in (("x", "Even gaps across"), ("y", "Even gaps down"))],
    *[_a(f"match_{d}", words, rank=70, group="arrange", min_targets=2,
         when={"all": [FACT("same_parent"), NOT("has_text"), NOT("has_camera")]},
         calls=_op("layer.match_size", "rest", to="$first", dims=d, at="$at"))
      for d, words in (("w", "Match width"), ("h", "Match height"), ("both", "Match size"))],
    _a("copy_style", "Copy style", rank=80, group="look", job="copy_style", max_targets=1, do="copy_style"),
    _a("paste_style", "Paste style", rank=80, group="look", job="paste_style", when=FACT("style_copied"),
       calls=_op("style.apply", "not_copied", **{"from": "$copied"})),
    _a("lock", "Lock", rank=90, group="state", job="lock", when=FACT("any_unlocked"), calls=_op("layer.lock", "unlocked")),
    _a("unlock", "Unlock", rank=90, group="state", job="lock", when=FACT("any_locked"), locked_ok=True,
       calls=_op("layer.unlock", "locked")),
    _a("hide", "Hide", rank=90, group="state", job="hide", when=FACT("any_shown"), calls=_op("layer.hide", "shown", on=True)),
    _a("show", "Show", rank=90, group="state", job="hide", when=FACT("any_hidden"), calls=_op("layer.hide", "hidden", on=False)),
    _a("copy", "Copy", rank=100, group="edit", job="copy", do="clip_copy"),
    _a("cut", "Cut", rank=100, group="edit", job="cut", do="clip_cut"),
    _a("duplicate", "Duplicate", rank=100, group="edit", job="duplicate", calls=_op("layer.duplicate", "ids")),
    _a("delete", "Delete", rank=100, group="edit", job="delete", calls=_op("layer.remove", "ids")),
    *[_a(k, label, rank=110, group="order", job=k, calls={"rule": "order", "how": k}) for k, label in _ORDER.items()],
    _a("rename", "Rename", rank=110, group="order", job="rename", max_targets=1, do="rename"),
]


def key_of(a: dict) -> str:
    return a["keys"] or SHARED_KEYS.get(a["job"], "")


def available(doc, ids: list[str], state: dict) -> list[dict]:
    """The actions this selection allows, in list order, resolved: {key ("layer:<id>"), label, shortcut, importance
    ("bar" | "menu"), group, bar, rank, calls, special}. `state`: {"at": id -> own seconds of the playhead, "copied":
    the layer whose style is copied ("" for none)}."""
    if not ids:
        return []
    f, out = Facts(doc, ids, state.get("copied", "")), []
    for a in ACTIONS:
        if (f.facts["any_locked"] and not a["locked_ok"]) or not allows(a, f):
            continue                                    # a locked layer takes nothing until it is unlocked
        calls = calls_of(a, f, state["at"])
        if a["calls"] and not calls:
            continue                                    # a reorder that would move nothing
        out.append({"key": f"layer:{a['id']}", "label": a["label"], "shortcut": key_of(a), "group": a["group"],
                    "importance": "bar" if a["importance"] == "primary" else "menu", "bar": a["bar"],
                    "rank": a["rank"], "calls": calls, "special": a["do"]})
    return out
