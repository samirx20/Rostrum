"""The ONE action list (INTERACTION.md 1.2): select first, then act. Each app writes its actions here as data, and
the four doors read the same list, so they always agree: the context bar, the right-click menu, Ctrl+K's "Do" group
and the shortcuts. Nothing is greyed: an action that can't run on this selection is absent, and a key pressed (or a
name typed) for it gets one plain sentence saying why.

The guard is generic and lives here, not in each app's lambdas: too few or too many selected, a kind the action
doesn't take, the registry's `valid_when` failing on an item, the app's own `valid`, or calls that would change
nothing. Registry operations feed the list through `from_operation`, so an operation and its action never disagree.
Keys come from the key map (keymap.py), never typed here. Each run is one change: all its calls in one apply.

`facts` is the app's own object with `.ids` and `.items` (item dicts with "type"), optionally `.doc` (for the
registry's facts about an item) and anything else the app's callables read (the playhead, a time range).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from rostrum_core.conditions import holds

from .keymap import normal

EDIT_JOBS = ("copy", "cut", "paste", "duplicate", "rename", "delete", "delete_close_gap")    # keys + right-click's last block only
# Right-click, the same short menu everywhere (Sam, H48): these jobs only, in this order, a divider between blocks.
# Everything else on a selection lives at the top of the settings panel (`action_views.panel`) and in Ctrl+K.
SHORT_MENU = (("edit", ("cut", "copy", "paste", "duplicate", "delete")), ("make", ("group", "ungroup")),
              ("order", ("forward", "backward")), ("state", ("hide", "lock", "rename")))
NUMBERS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}


@dataclass(frozen=True)
class Action:
    id: str
    label: str | Callable = ""                # or label(facts) -> str ("Mute" / "Unmute")
    valid: Callable | None = None             # valid(facts) -> bool: the app's own condition
    valid_when: dict | None = None            # a registry condition, checked on every selected item
    when: dict | None = None                  # a condition on the selection's own facts (facts.facts: {"groupable": …})
    kinds: tuple | None = None                # item types it acts on; None = any
    min_targets: int = 1                      # 0 = needs nothing selected (a time range action)
    max_targets: int | None = None
    importance: str = "secondary"             # "primary": on the context bar; "secondary": under ⋯ and in menus
    rank: int = 100                           # lower first
    promoted: Callable | None = None          # promoted(facts) -> bool: put it first
    job: str = ""                             # a key map job ("group"): its key comes from the key map
    keys: str = ""                            # an app-only key, which must be in the app's key map
    group: str = ""                           # menu divider group
    bar: str = ""                             # the bar button it sits under ("Align"); the settings panel's row title
    panel: bool = True                        # listed in the settings panel's actions (False: keys / Ctrl+K only)
    row: str = ""                             # a settings row's param id: it shows as a button on that row, not on the bar or panel
    row_label: str | Callable = ""            # its word on that button ("Pick"), else its label
    icon: str = ""                            # a ToolIcon name: in the settings panel an icon button (name on hover)
    calls: Callable | None = None             # calls(facts) -> [operation calls]
    do: str = ""                              # an app's own non-operation action ("copy", "rename")
    why: str = ""                             # the app's own sentence for why it isn't offered
    release: str = ""                         # a hold key let go: the app's own "do" run then (only if the press ran)

    def __post_init__(self):
        if self.importance not in ("primary", "secondary"):
            raise ValueError(f"action {self.id}: importance {self.importance!r} is not primary or secondary")
        if bool(self.calls) == bool(self.do):
            raise ValueError(f"action {self.id}: give it either calls or do (exactly one)")

    @property
    def edit(self) -> bool:
        return self.job in EDIT_JOBS

    def label_for(self, facts) -> str:
        return self.label(facts) if callable(self.label) else (self.label or self.id)


def from_operation(op, **overrides) -> Action:
    """An action from a registry Operation: its name, label, kinds, valid_when, importance and min_targets."""
    if "calls" not in overrides and "do" not in overrides:
        missing = [p.name for p in op.params if p.required and p.default is None]
        if missing:
            raise ValueError(f"operation {op.name} needs {', '.join(missing)}: give from_operation a calls= that "
                             "fills them")
        overrides["calls"] = (lambda f: [{"op": op.name, "target": list(f.ids), "args": {}}]) if op.targets else (
            lambda f: [{"op": op.name, "args": {}}])
    base = {"id": op.name, "label": op.label or op.name, "valid_when": op.valid_when, "kinds": op.targets,
            "importance": "primary" if op.importance == "primary" else "secondary",
            "min_targets": getattr(op, "min_targets", 1) if op.targets else 0}
    return Action(**{**base, **overrides})


def plural(kind: str) -> str:
    return kind + ("es" if kind.endswith(("s", "x", "ch", "sh")) else "s")


class ActionList:
    def __init__(self, actions, keymap, noun: str = "item", short_menu: tuple | None = None):
        """`short_menu`: right-click lists only those jobs (SHORT_MENU); None = every valid action (not moved yet)."""
        self.actions, self.keymap, self.noun, self.short_menu = list(actions), keymap, noun, short_menu
        ids = [a.id for a in self.actions]
        if len(set(ids)) != len(ids):
            raise ValueError(f"two actions share an id: {sorted({i for i in ids if ids.count(i) > 1})}")
        for a in self.actions:
            if a.job and not keymap.has(a.job):
                raise ValueError(f'action {a.id}: "{a.job}" is not a job in the key map')
            if a.keys and keymap.where(a.keys) in ("", "shared"):
                raise ValueError(f"action {a.id}: its key {a.keys} must be one of the app's own keys in the key map")

    def job_of(self, a: Action) -> str:
        return a.job or (self.keymap.job_of(a.keys) if a.keys else "")

    def keys_of(self, a: Action) -> str:
        return normal(a.keys) if a.keys else (self.keymap.key_of(a.job) if a.job else "")

    def _check(self, a: Action, facts, kind_facts=None):
        """(why it is absent | None, its calls). The one guard every door uses. `kind_facts`: {item id: the kind's
        facts}, shared by every action of one `available` (each `valid_when` read them again per action)."""
        n, items = len(facts.ids), facts.items
        if n < a.min_targets:
            return "few", []
        if a.max_targets is not None and n > a.max_targets:
            return "many", []
        if a.kinds is not None and any(it["type"] not in a.kinds for it in items):
            return "kind", []
        doc = getattr(facts, "doc", None)
        if a.valid_when and not all(holds(a.valid_when, it, _kind_facts(it, doc, kind_facts)) for it in items):
            return "when", []
        if a.when and not holds(a.when, {}, getattr(facts, "facts", {})):
            return "invalid", []
        if a.valid and not a.valid(facts):
            return "invalid", []
        calls = a.calls(facts) if a.calls else []
        if a.calls and not calls:
            return "nothing", []
        return None, calls

    def available(self, facts) -> list[dict]:
        """The actions this selection allows, resolved, in order: promoted first, then by rank."""
        out, kind_facts = [], {}
        for i, a in enumerate(self.actions):
            reason, calls = self._check(a, facts, kind_facts)
            if reason is None:
                first = 0 if a.promoted and a.promoted(facts) else 1
                out.append(((first, a.rank, i), {
                    "id": a.id, "label": a.label_for(facts), "keys": self.keys_of(a),
                    "importance": "primary" if first == 0 else a.importance,    # promoted: a button while it holds
                    "group": "edit" if a.edit else a.group, "bar": a.bar, "calls": calls, "do": a.do,
                    "edit": a.edit, "rank": a.rank, "job": self.job_of(a), "release": a.release, "panel": a.panel, "icon": a.icon,
                    "row": a.row, "row_label": a.row_label(facts) if callable(a.row_label) else a.row_label,
                    "min_targets": a.min_targets}))
        return [e for _, e in sorted(out, key=lambda x: x[0])]

    def why_not(self, facts, typed: str) -> str:
        """One plain sentence for an action asked for (a label typed, or an id) that isn't offered; "" if it is."""
        t = typed.strip().lower()
        a = next((x for x in self.actions if t in (x.id.lower(), x.label_for(facts).lower())), None)
        if a is None:
            return f'Nothing here is called "{typed.strip()}".'
        return self._sentence(a, facts)

    def _sentence(self, a: Action, facts) -> str:
        reason, _ = self._check(a, facts)
        if reason is None:
            return ""
        if a.why:
            return a.why
        label, what = a.label_for(facts).rstrip("…. "), " or ".join(plural(k) for k in a.kinds) if a.kinds else plural(self.noun)
        if reason == "few":
            n = a.min_targets
            if n == 1:
                return f"{label} needs {what} selected first."
            return f"{label} needs {NUMBERS.get(n, n)} or more {what} selected."
        if reason == "many":
            n = a.max_targets
            if n == 0:
                return f"{label} works only with nothing selected."
            return f"{label} works on at most {NUMBERS.get(n, n)} {what if n > 1 else a.kinds[0] if a.kinds else self.noun}."
        if reason == "kind":
            return f"{label} works only on {what}."
        if reason == "nothing":
            return f"{label} would change nothing here."
        return f"{label} doesn't fit what is selected."

    def on_key(self, facts, job_or_keys: str):
        """A shortcut pressed: (entry to run, "") or (None, why). A job with no action here: (None, "")."""
        job = job_or_keys if self.keymap.has(job_or_keys) else self.keymap.job_of(job_or_keys)
        mine = [a for a in self.actions if job and self.job_of(a) == job]
        if not mine:
            return None, ""
        ids = {a.id for a in mine}
        entry = next((e for e in self.available(facts) if e["id"] in ids), None)
        if entry:
            return entry, ""
        near = next((a for a in mine if self._check(a, facts)[0] not in ("kind",)), mine[0])
        return None, self._sentence(near, facts)


from .action_views import bar, commands, menu, panel  # noqa: E402,F401  (the views live beside: one import for apps)


def _kind_facts(item: dict, doc, kept: dict | None) -> dict:
    """The document kind's facts of `item` (none without a document), worked out once per `kept` (one `available`)."""
    if doc is None:
        return {}
    if kept is None:
        return doc.kind.facts(item, doc)
    if item["id"] not in kept:
        kept[item["id"]] = doc.kind.facts(item, doc)
    return kept[item["id"]]
