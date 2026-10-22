"""The marker's right-click menu (INTERACTION.md 1.6 › Markers; qml MarkerFlag.qml), built from the marker operations
(rostrum_core.markers: marker.rename / move / colour / remove) through the kit's one action list (actions.py), so it
shows only what applies to that marker now and what it runs are the same calls agents make:

    Rename            starts the name field on the flag (the screen's own: the list knows the operation)
    Move to playhead  marker.move to the playhead (absent when it is already there)
    Colour ▸          marker.colour, one row per choice
    Shared / Only here    flips whether the project's apps see it (the app's own: owned data); there only when the
                          document is in a project (`can_share`)
    Delete            marker.remove

`rows(facts)` is the menu as the kit's ActionMenu draws it; `entry(facts, value)` is the chosen action, resolved: its
`calls` (run through ONE apply) or its `do` word ("rename", "share").
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


def _colour(name, hexval):
    return Action(id=f"colour:{hexval}", label=name, calls=lambda f: [{"op": "marker.colour", "target": f.ids,
                                                                        "args": {"colour": hexval}}],
                  kinds=("marker",), bar="Colour", group="colour", importance="secondary", rank=30)


def _actions() -> list[Action]:
    op = REGISTRY.get
    move = from_operation(op("marker.move"), importance="secondary", rank=20, group="edit",
                          label="Move to playhead", calls=lambda f: [{"op": "marker.move", "target": f.ids,
                                                                      "args": {"at": f.playhead}}]
                          if abs(f.playhead - f.at) > 1e-6 else [])
    share = Action(id="share", label=lambda f: "Keep it only here" if f.shared else "Share with the project", do="share",
                   kinds=("marker",), valid=lambda f: f.can_share, importance="secondary", rank=40, group="share")
    return [from_operation(op("marker.rename"), do="rename", importance="secondary", rank=10, group="edit"),
            move, *[_colour(n, h) for n, h in COLOURS], share,
            from_operation(op("marker.remove"), importance="secondary", rank=50, group="delete")]


LIST = ActionList(_actions(), KeyMap("marker"), noun="marker")


def rows(facts: MarkerFacts) -> list[dict]:
    return menu(LIST.available(facts))


def entry(facts: MarkerFacts, value: str) -> dict:
    """The chosen row, resolved by the same guard; a value that isn't offered fails loudly."""
    found = next((e for e in LIST.available(facts) if e["id"] == value), None)
    if found is None:
        raise ValueError(f'marker menu: "{value}" is not offered for this marker; ' + LIST.why_not(facts, value))
    return found
