"""The fonts a text can name, as the engine's one registry lists them (render/src/scene/fonts.rs, font_list.rs): the
fonts shipped with the app first, then the fonts installed on this computer, each family once with its real weights,
whether it has italics, and its files. Read once per run from `rostrum2d-render fonts` (a font installed while the app
runs shows after a restart). The picker, the importers, the agents' inspect_fonts and the check on a font an operation
sets all read this; nothing else scans a fonts folder.
"""
from __future__ import annotations

import json
import subprocess
from functools import lru_cache

from .engine import EngineError, find_exe


@lru_cache(maxsize=1)
def _listed() -> dict:
    exe = find_exe()
    run = subprocess.run([str(exe), "fonts"], capture_output=True, text=True, encoding="utf-8", timeout=120,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if run.returncode != 0:
        raise EngineError(f"the 2D engine could not list the fonts: {run.stderr.strip() or run.returncode}")
    return json.loads(run.stdout)


def families() -> list[dict]:
    """[{family, source ("shipped" | "installed"), weights, range, variable, italic, upright, files}], shipped first."""
    return _listed()["families"]


def names() -> set[str]:
    """Every family name a text may give (a variable font's second name, "Inter Variable", too)."""
    return {f["family"] for f in families()} | set(_listed()["aliases"])


def family(name: str) -> dict | None:
    return next((f for f in families() if f["family"] == name), None)


def missing_words(name: str) -> str:
    """'font "Helvetica" is not in the app or on this computer (close: Helvetica Neue …)', as the engine says it."""
    word = name.lower().split()[0] if name.strip() else ""
    close = [f["family"] for f in families() if word and word in f["family"].lower()][:8]
    return (f'font "{name}" is not in the app or on this computer' + (f" (close: {', '.join(close)})" if close else "")
            + "; inspect_fonts names every font there is")


def refusal(name: str) -> str | None:
    """Why an operation may not set this font, or None. No engine built: no check (nothing can be drawn then, and
    the look tools say so)."""
    try:
        return None if name in names() else missing_words(name)
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
