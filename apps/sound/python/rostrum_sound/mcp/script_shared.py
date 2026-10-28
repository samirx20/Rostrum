"""run_script publishes a script's `marker(name, at, shared=True)` to the project's markers (the list edit_markers changes,
inspect_markers shows and 2D follows). A script never writes a file itself: the song records the request
(builder_music.py) and this step adds the markers, in seconds, before the script's tree merges (the merge checks that
every "#name" the song uses exists). The same name at the same time is already there; at another time a loud error
naming both, and nothing is changed."""
from __future__ import annotations

from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core import markers as M

from ..script import run_source, shared_asked
from .script_twins import script_name

SAME = 1e-3


def publish(ctx, doc, args: dict) -> None:
    source = args.get("source") or (Path(args["path"]).read_text(encoding="utf-8") if args.get("path") else "")
    if "shared" not in source:
        return                                            # no marker(..., shared=True) asked: no dry run
    run_source(source, script_name(args), doc)
    asked = shared_asked()
    if not asked:
        return
    folder = ctx.app.folder
    if not folder:
        raise RostrumError(codes.BAD_ARGUMENT, "marker", f'marker "{asked[0][0]}" (shared=True)', "needs a project: this "
                           "server was started without a project folder", hint="Open one with run_open_project, or drop shared=True.")
    rows = {M._key(r["name"]): r for r in M.listing(folder)}
    calls, said = [], []
    for name, at in asked:
        row = rows.get(M._key(name))
        if row is None:
            calls.append({"op": "marker.add", "args": {"name": name, "at": round(at, 6)}})
            said.append(f'"{name}" at {at:.3f} s')
        elif abs(float(row["at"]) - at) > SAME:
            raise RostrumError(codes.BAD_ARGUMENT, "marker", f'marker "{name}" at {at:.3f} s (shared=True)',
                               f'is already a project marker "{row["name"]}" at {float(row["at"]):.3f} s: one name is one marker',
                               hint=f'Write the script\'s marker at {float(row["at"]):g} s (or use "#{row["name"]}" without making it), '
                                    "move the project marker with edit_markers, or use another name. Nothing was changed.")
    if calls:
        M.edit(folder, calls, ctx.who, f"Script {script_name(args)}: shared markers")
        ctx.note("published to the project's markers (2D and the other apps see them; move them with edit_markers): " + ", ".join(said) + ".")
