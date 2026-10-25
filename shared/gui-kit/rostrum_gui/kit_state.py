"""The kit's own names, kept apart from every app's (an app subclasses DocBridge and adds mix-ins, so both share one
object). S24's bug: the kit and Rostrum2D both used `self._opened` for different things and the kit's overwrote
the app's. So:
- **State:** everything the kit keeps lives on one `self._kit` (a `KitState`, fixed fields: a typo fails at once).
  Apps read the primary selection as `self._sel` (a read-only property) and the rest through the kit's properties.
- **Names:** a name the kit defines (method, property, slot, signal, class attribute) may be redefined by an app
  class only if it is in `HOOKS` (meant to be overridden); anything else raises at construction, naming both.
- **Instance attributes:** setting any kit name on the bridge raises; `doc`, `who`, `model` and `_kit` are set once,
  by the kit.
"""
from __future__ import annotations

# What an app may override (call super() where it extends rather than replaces).
HOOKS = frozenset({
    "label_of", "kind_label", "starts", "subtitle", "edit_call", "relative_call", "shown_values", "facts_of", "on_page", "anim_state", "list_choices", "animate_calls",
    "expr_state", "clear_expr_calls", "sections", "selection_label", "extra_commands",
    "select", "run", "open_item", "say", "commands", "historyCount", "undoLabel", "redoLabel", "_commands", "_rows", "_first", "_on_doc", "_before_followers",
    "staticMetaObject",
})
ONCE = frozenset({"doc", "who", "model", "_kit", "_unsubscribe"})


class KitState:
    """Every piece of the bridge's own screen state (see each module for its meaning)."""
    __slots__ = ("sel", "selection", "more", "status", "scrub", "partners", "opened", "static", "op_kind",
                 "open_groups", "search", "handlers", "agent", "shown_sel", "held", "touched", "told", "paced", "stepping", "panel", "rows_due",
                 "ready_kinds", "kinds_job", "ahead_filter", "kinds", "stepped", "seen", "evaluated")

    def __init__(self, opened):
        self.sel, self.selection, self.more, self.status = "", [], False, ""
        self.scrub = None                   # the open scrub (edits.Scrub), if any
        self.panel = None                   # after_frame.AfterFrame: a pick's panel, the frame after (bridge_select)
        self.rows_due = None                # after_frame.AfterFrame: the panel's rows after a document change (the same)
        self.partners = []                  # other documents in this person's one history (join_history)
        self.opened = [opened]              # where each history stood when this window opened (historyCount)
        self.static = []                    # the rows' fixed layout for the selection's kind
        self.op_kind = (None, "")           # the selection's field operation and kind
        self.open_groups, self.search = {}, ""      # {group: open?} the person chose (rows._open_groups)
        self.handlers = {}                  # parts.handle / invoke
        self.agent = None                   # agent_watch.AgentWatch (the bridge makes it)
        self.shown_sel = None               # selectedItem as last announced (_follow_doc re-announces only a change)
        self.held = None                    # (param, item ids): the field being typed in and the items it is for
        self.told = [0, ("", "", [])]       # [historyCount, (undo, redo, versions)]: worked out once per change
        self.touched = None                 # what the last change touched (touched.py); None = can't tell: everything
        self.ahead_filter = None            # an app's say on which items have a panel worth making ahead: fn(item) -> bool
        self.ready_kinds, self.kinds_job = set(), None      # kinds whose panel is made ahead; the job that finds a new kind
        self.paced = None                  # news.OnceAFrame: the panel's rows during a drag (the bridge makes it)
        self.stepping = False               # the rows being worked out are a drag's step: values only (rows.evaluate step),
                                            # (data before the steps, what they touched) = k.stepped as the rows took it
        self.stepped = None                 # the drag's steps since the rows last followed: (data before them, Touched or None)
        self.seen = None                    # the document's data as last heard (where the next step starts from)
        self.evaluated = {}                 # {item id: (data, layout, its rows as evaluated)}: rows.evaluate kept
        self.kinds = (None, (), [])         # (song data, ids, their types): bridge_select.kinds_of, once per selection


def _is_kit(cls) -> bool:
    return cls.__module__.startswith("rostrum_gui.")


def kit_names(cls) -> frozenset:
    """Every name the kit's classes in this bridge class's bases define, and its instance attributes."""
    return frozenset(n for c in cls.__mro__ if _is_kit(c) for n in vars(c) if not n.startswith("__")) | ONCE


_checked: dict = {}


def check(cls) -> frozenset:
    """Raise if an app class in `cls`'s bases redefines a kit name that isn't a hook; the kit's names, checked once
    per class."""
    if cls not in _checked:
        names = kit_names(cls)
        for c in cls.__mro__:
            if _is_kit(c) or c.__module__.startswith(("PySide6", "Shiboken", "builtins")):
                continue
            clash = sorted((set(vars(c)) & names) - HOOKS)
            if clash:
                raise TypeError(f"{c.__module__}.{c.__qualname__} redefines the kit's {', '.join(clash)}: "
                                f"rename it (or, if the kit means it to be overridden, add it to kit_state.HOOKS)")
        _checked[cls] = names
    return _checked[cls]
