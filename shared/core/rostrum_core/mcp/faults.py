"""Notes (shared/mcp/CONVENTIONS.md § 4): what a check measured, given only when the agent asks for it.

Rostrum never fixes, refuses or blocks an agent's work (Sam, 2026-10-29): anything in a video can be right when it is
deliberate. So a check never changes a reply's header, a file's name or a call's result. A look or render tool takes
`notes: true` (NOTES below); only then does it run its checks and set `Reply.faults`, and the reply ends with

    Notes (2): [loudness] -16.9 LUFS, the master's target is -14 (whole song) | [cut_edge:ball] ...

A note is {id, what, when}: `what` is an observation with its measurement ("text 'X' crosses shape 'Y'"), never an
instruction; `id` is stable across re-runs, so the agent can follow one note from version to version.
"""
from __future__ import annotations

NOTES = {"notes": {"type": "boolean", "default": False,
                   "description": "Also run the checks and list what they measured (notes: observations, never "
                                  "required). Off by default: look at the picture and judge it yourself."}}


def note(id: str, what: str, when: str | None = None) -> dict:
    """One note: `id` stable across re-runs, `what` measured in plain words, `when` a time or marker (None: the whole
    piece / picture)."""
    return {"id": id, "what": what, "when": when}


def fault(id: str, what: str, fix: str | None = None, when: str | None = None) -> dict:
    """The older call shape (Sound, 2D): the same note; `fix` is not said (a note observes, it does not instruct)."""
    return note(id, what, when)


def asked(args: dict | None) -> bool:
    """Did the call ask for notes (`notes: true`)?"""
    return bool((args or {}).get("notes"))


def _line(n: dict) -> str:
    when = f" ({n['when']})" if n.get("when") else ""
    return f"[{n['id']}] {n['what']}{when}"


def lines(notes: list[dict]) -> str:
    """The reply's closing line for the notes asked for."""
    if not notes:
        return "Notes: the checks measured nothing to note."
    return f"Notes ({len(notes)}): " + " | ".join(_line(n) for n in notes)
