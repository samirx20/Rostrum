"""The marker's right-click menu (INTERACTION.md 1.6 › Markers; qml MarkerFlag.qml), built from the marker operations
through the kit's one action list (actions.py), so it shows only what applies to that marker now and what it runs are
the same calls agents make:

    Rename            starts the name field on the flag (the screen's own: the list knows the operation)
    Move to playhead  the move operation to the playhead (absent when it is already there)
    Colour ▸          the colour operation, one row per choice (absent when the app's markers have no colour)
    Shared / Only here    flips whether the project's apps see it (the app's own: owned data); there only when the
                          document is in a project (`can_share`)
    Delete            the remove operation

Whose operations: a `MarkerOps` names the registry and the operation for each job. `CORE` is the project's markers
(rostrum_core.markers: marker.rename / move / colour / remove; 2D's). An app with markers of its own builds its menu
from its own (Sound: one `marker.set {name, at}` does rename and move) and adds its own rows (`extra`, Actions):

    menu = MarkerMenu(MarkerOps(KIND.registry, rename=("marker.set", "Rename marker"), move="marker.set",
                                colour="marker.set", remove="marker.remove"), extra=[...])
    menu.rows(facts)                  # the menu as the kit's ActionMenu draws it
    menu.entry(facts, value)          # the chosen action, resolved: its `calls` (ONE apply) or its `do` word

Row ids are the job's, whatever operation does it ("marker.rename", "marker.move", "colour:#f2b33d", "share",
"marker.remove"), so a screen or a scripted step names a row the same way in every app. The module's `rows(facts)` /
`entry(facts, value)` are the core menu's.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rostrum_core.markers import REGISTRY

from .action_views import menu
from .actions import Action, ActionList, from_operation
from .keymap import KeyMap

COLOURS = [("Amber", "#f2b33d"), ("Red", "#ff6b6b"), ("Green", "#4cc38a"), ("Blue", "#4c8dff"),
           ("Violet", "#a78bfa"), ("Grey", "#9aa0aa")]


@dataclass
class MarkerFacts:
    ids: list
    playhead: float = 0.0
    at: float = 0.0                      # where the marker is now
    can_share: bool = False              # the document is in a project
    shared: bool = True
    items: list = field(init=False)

    def __post_init__(self):
        self.items = [{"id": i, "type": "marker"} for i in self.ids]


@dataclass(frozen=True)
class MarkerOps:
    """The operation for each job: a name, or (name, the row's words) when the operation's own label doesn't say the
    job (Sound's "Edit marker" does rename and move). "" = the app has no such job (its row is absent)."""
    registry: object
    rename: str | tuple = "marker.rename"
    move: str | tuple = "marker.move"
    colour: str | tuple = "marker.colour"
    remove: str | tuple = "marker.remove"

    def op(self, job: str):
        """(the registry Operation, the row's words or None) for a job; (None, None) when the app has none."""
        spec = getattr(self, job)
        name, words = spec if isinstance(spec, tuple) else (spec, None)
        return (self.registry.get(name), words) if name else (None, None)


CORE = MarkerOps(REGISTRY)


def _takes(op, arg: str) -> bool:
    return op is not None and any(p.name == arg for p in op.params)


def _colour(op, name, hexval):
    return Action(id=f"colour:{hexval}", label=name, calls=lambda f: [{"op": op.name, "target": f.ids,
                                                                        "args": {"colour": hexval}}],
                  kinds=("marker",), bar="Colour", group="colour", importance="secondary", rank=30)


def actions(ops: MarkerOps = CORE) -> list[Action]:
    """The menu's rows from `ops`, each only where the app's operation can do it (a colour needs a `colour` argument)."""
    out = []
    rename, words = ops.op("rename")
    if rename is not None:
        out.append(from_operation(rename, id="marker.rename", do="rename", importance="secondary", rank=10,
                                  group="edit", **({"label": words} if words else {})))
    move, _ = ops.op("move")
    if _takes(move, "at"):
        out.append(from_operation(move, id="marker.move", importance="secondary", rank=20, group="edit",
                                  label="Move to playhead",
                                  calls=lambda f: [{"op": move.name, "target": f.ids, "args": {"at": f.playhead}}]
                                  if abs(f.playhead - f.at) > 1e-6 else []))
    colour, _ = ops.op("colour")
    if _takes(colour, "colour"):
        out += [_colour(colour, n, h) for n, h in COLOURS]
    out.append(Action(id="share", label=lambda f: "Keep it only here" if f.shared else "Share with the project",
                      do="share", kinds=("marker",), valid=lambda f: f.can_share, importance="secondary", rank=40,
                      group="share"))
    remove, words = ops.op("remove")
    if remove is not None:
        out.append(from_operation(remove, id="marker.remove", importance="secondary", rank=50, group="delete",
                                  **({"label": words} if words else {})))
    return out


class MarkerMenu:
    """One app's marker menu: its operations' rows, then its own (`extra`: Actions on kind "marker", ranked among them)."""

    def __init__(self, ops: MarkerOps = CORE, extra=()):
        self.list = ActionList(actions(ops) + list(extra), KeyMap("marker"), noun="marker")

    def rows(self, facts) -> list[dict]:
        return menu(self.list.available(facts))

    def entry(self, facts, value: str) -> dict:
        """The chosen row, resolved by the same guard; a value that isn't offered fails loudly."""
        found = next((e for e in self.list.available(facts) if e["id"] == value), None)
        if found is None:
            raise ValueError(f'marker menu: "{value}" is not offered for this marker; ' + self.list.why_not(facts, value))
        return found


_CORE_MENU = MarkerMenu()
LIST = _CORE_MENU.list


def rows(facts: MarkerFacts) -> list[dict]:
    return _CORE_MENU.rows(facts)


def entry(facts: MarkerFacts, value: str) -> dict:
    return _CORE_MENU.entry(facts, value)
