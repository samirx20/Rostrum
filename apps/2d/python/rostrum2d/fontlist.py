"""The fonts a text can name, as the engine's one registry lists them (render/src/scene/fonts.rs, font_list.rs): the
fonts shipped with the app first, then the fonts installed on this computer, each family once with its real weights,
whether it has italics, and its files. Read once per run from `rostrum2d-render fonts` (a font installed while the app
runs shows after a restart). The picker, the importers, the agents' inspect_fonts and the check on a font an operation
sets all read this; nothing else scans a fonts folder.
"""
from __future__ import annotations

import difflib
import json
import subprocess
from functools import lru_cache

from rostrum_core.byname import google_families, google_family

from .engine import EngineError, find_exe


@lru_cache(maxsize=1)
def _read() -> tuple[dict | None, EngineError | OSError | None]:
    """The engine's list, or why there is none (no engine built, it failed): either way once per run, so a text asked
    about per scene description never looks for the engine's file again."""
    try:
        exe = find_exe()
        run = subprocess.run([str(exe), "fonts"], capture_output=True, text=True, encoding="utf-8", timeout=120,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (EngineError, OSError) as e:
        return None, e
    if run.returncode != 0:
        return None, EngineError(f"the 2D engine could not list the fonts: {run.stderr.strip() or run.returncode}")
    listed = json.loads(run.stdout)
    listed["names"] = frozenset({f["family"] for f in listed["families"]} | set(listed["aliases"]))
    listed["by_name"] = {f["family"]: f for f in listed["families"]}
    return listed, None


def _listed() -> dict:
    listed, why = _read()
    if why is not None:
        raise why
    return listed


def families() -> list[dict]:
    """[{family, source ("shipped" | "installed"), weights, range, variable, italic, upright, files}], shipped first."""
    return _listed()["families"]


def names() -> frozenset[str]:
    """Every family name a text may give (a variable font's second name, "Inter Variable", too)."""
    return _listed()["names"]


def family(name: str) -> dict | None:
    return _listed()["by_name"].get(name)


def missing_words(name: str) -> str:
    """'font "Helvetica" is not in the app, on this computer or in Google Fonts (close: Helvetica Neue …; nearest Google Fonts: …)', as the engine says it."""
    word = name.lower().split()[0] if name.strip() else ""
    close = [f["family"] for f in families() if word and word in f["family"].lower()][:8]
    near = difflib.get_close_matches(name, google_families(), n=5, cutoff=0.0)
    return (f'font "{name}" is not in the app, on this computer or in Google Fonts' + (f" (close: {', '.join(close)})" if close else "")
            + f"; nearest Google Fonts: {', '.join(near)}; inspect_fonts names every font there is")


def refusal(name: str) -> str | None:
    """Why an operation may not set this font, or None. No engine built: no check (nothing can be drawn then, and
    the look tools say so). A Google Fonts family is a font there is: fetched the first time a scene draws it
    (missing_font.trouble)."""
    try:
        return None if name in names() or google_family(name) else missing_words(name)
    except (EngineError, OSError):
        return None


def no_italic(name: str) -> str | None:
    """Why a text in this family may not be italic, or None (it has one, or no engine is built)."""
    try:
        fam = family(name)
    except (EngineError, OSError):
        return None
    return f'the font "{name}" has no italic; turn Italic off or pick a font that has one' if fam and not fam["italic"] else None


def setting_refusal(item_id: str, font: str, italic: bool) -> str | None:
    """Why a text may not be set to this font (and slope), naming the field; None when it may. Asked where a font is
    set (text.set / textstyle.set, a script's text(...)), never when a file opens: there a font this computer lacks is a
    Missing font problem (diagnose_engine.py), so the person can still open the file and pick another."""
    if why := refusal(font):
        return f"{item_id}.font: {why}"
    if italic and (why := no_italic(font)):
        return f"{item_id}.italic: {why}"
    return None
