"""A render whose master names a loudness target lands on it (3E audit: master(loudness=-14) rendered -16.9 because the
gentle limiter stops at `maxLimit`, and reaching it took an edit_loudness job and another render).

Before the file is written the song is measured as it is now and, when it would land more than fit_loudness.REACH_OK
under the target, the limit that reaches it is found (fit_loudness.reach, the Export sheet's own push); the file is
rendered at that limit. The song itself keeps its own `maxLimit` (the everyday master stays transparent: playback,
looks without a target), and the reply says how far the limit went and how many dB of limiting it took. When even
the master's top limit is short, the file lands under and the loudness fault names the exact fix."""
from __future__ import annotations

import copy
import tempfile
from pathlib import Path
from types import SimpleNamespace

from .. import fit_loudness as fit
from ..compile import compile as compile_doc


def push(state, doc, item: str, options: dict) -> tuple[dict, dict | None]:
    """-> (fit_loudness.reach's answer ({} when the song already lands on its target or has none), the schedule at the
    pushed limit (None: render the song's own))."""
    song = SimpleNamespace(data=copy.deepcopy(doc.data), folder=getattr(doc, "folder", None))
    span = (options["from"], options["to"]) if "from" in options else None
    with tempfile.TemporaryDirectory(prefix="push_", dir=state.renders(item)) as tmp:
        got = fit.reach(song, state.engine, Path(tmp), span)
    if not got.get("ops"):
        return got, None
    song.data["master"][0].update(got["ops"][0]["args"])
    return got, compile_doc(song)


def words(got: dict) -> str:
    """The reply's sentence on the push ("" with none)."""
    if not got:
        return ""
    keep = f" The song keeps maxLimit {got['was_db']:g}; master(maxLimit={got['max_limit_db']:g}) makes this its own."
    if got["reaches"]:
        return f" Pushed to the target: {got['words'].rstrip('.')}, {got['limit_db']:.1f} dB of limiting.{keep}"
    return f" {got['words']}{keep}"


def fix_when_short(found: list[dict] | None, got: dict) -> None:
    """The loudness fault after a push that hit the master's top limit: raising the limit is no longer a fix."""
    if not got or got.get("reaches"):
        return
    for f in found or []:
        if f["id"] == "loudness":
            f["fix"] = (f"the limiter already pulls at its top ({got['max_limit_db']:g} dB): tame the peaks "
                        f"(edit_loudness {{\"apply\": \"tame_peaks\"}}), turn the most peaked track down (edit_loudness "
                        f"{{\"apply\": \"trim_track\"}}), or lower the master's loudness target to {got['lufs']:.0f}")


def master_as_rendered(master: dict, got: dict) -> dict:
    """The master the file was rendered with, for the loudness facts (fit_loudness.landing)."""
    return {**master, "maxLimit": got["max_limit_db"], "gentle": True} if got.get("ops") else master
