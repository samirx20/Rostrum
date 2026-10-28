"""A song is one piece: a script under a NEW name that makes the same items as an earlier script would merge a second
copy into the same tracks (the script-first audit: 158 notes where 81 were meant, and a reply of "held back" lines).
That run is refused before anything changes, naming the earlier script to run under instead."""
from __future__ import annotations

from pathlib import Path

from rostrum_core import RostrumError, codes

from ..script import run_source


def script_name(args: dict) -> str:
    return args.get("name") or (Path(args["path"]).name if args.get("path") else "agent_script.py")


def _tracks(tree: dict) -> set[str]:
    return {t["id"] for t in tree.get("tracks", [])}


def refuse_second_copy(doc, args: dict) -> None:
    """Raise when this run's name is new and it makes tracks another script made (a run that fails changes nothing).
    Only tracks count: every script also writes the song's own settings and the master, which merge as one."""
    name, source = script_name(args), args.get("source")
    if not source or name in doc.script_bases or not doc.script_bases:
        return
    mine = _tracks(run_source(source, name, doc))
    twins = {n: sorted(mine & _tracks(b)) for n, b in doc.script_bases.items() if mine & _tracks(b)}
    if twins:
        first, ids = next(iter(twins.items()))
        raise RostrumError(codes.BAD_ARGUMENT, f'script "{name}"', "the script's name",
                           f'is new, but script "{first}" already made the tracks {", ".join(ids)}: under a new name every '
                           "note would be added a second time beside the first",
                           [f'name: "{n}"' for n in twins],
                           hint=f'Run it under name "{first}" to replace what that script made (keep one script name per '
                                "song), or give these tracks other ids to add parts beside it. Nothing was changed.")
