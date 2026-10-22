"""The "Did it help?" line of a cleaned clip (DESIGN.md §3.10 step 6): what the clean-up measured, in plain words.

    measure_facts(media, recipe) -> the numbers (listen.clean_compare: the original vs its cleaned take), measured once
    and kept as a small JSON file next to the cleaned take's cache entry key, so a repaint, a new selection or the next
    session reads it and never measures again. `words(facts)` turns them into {"line", "warn"}.
`Measures` asks for a clip's line off the screen's thread (the first time a take is read takes a moment) and says
`changed` when it lands; until then the line is "" (the bar shows nothing rather than a guess).
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from rostrum_sound import cleanup, settings
from rostrum_sound.listen.cleanup import clean_compare

MINUS = "−"
SAME_DB, ECHO_DB, QUIETER_DB = 1.5, 3.0, 3.0        # smaller than this = "about the same"; speech down more than this = a warning


def _file(media: str, take: str) -> Path:
    src = Path(media)
    key = hashlib.sha256(f"{take}|{src.stat().st_size}|{src.stat().st_mtime_ns}".encode()).hexdigest()[:24]
    return settings.cache_dir() / "sound" / "cleanup-measure" / f"{key}.json"


def measure_facts(media: str, recipe: dict) -> dict | None:
    """The numbers for this clean-up (None while its take is not made). Computed once, then read from the file."""
    take = cleanup.cached(media, recipe)
    if take is None:
        return None
    path = _file(media, take)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    facts = clean_compare(media, take)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_text(json.dumps(facts), encoding="utf-8")
    tmp.replace(path)
    return facts


def _db(x: float) -> str:
    return f"{MINUS if x < 0 else '+'}{abs(x):.0f} dB"


def words(facts: dict) -> dict:
    """{"line": "Background noise −18 dB · voice level unchanged · room echo shorter", "warn": ""}."""
    c, parts, warn = facts["change"], [], ""
    if c["floor_db"] is not None:
        parts.append(f"Background noise {_db(c['floor_db'])}" if abs(c["floor_db"]) >= SAME_DB else "Background noise unchanged")
    if c["level_db"] is not None:
        parts.append("voice level unchanged" if abs(c["level_db"]) < SAME_DB else f"voice level {_db(c['level_db'])}")
        if c["level_db"] < -QUIETER_DB:
            warn = "The voice got quieter too: try less."
    if c["tail_drop_db"] is not None and abs(c["tail_drop_db"]) >= ECHO_DB:
        parts.append("room echo shorter" if c["tail_drop_db"] > 0 else "room echo longer")
    line = " · ".join(parts)
    return {"line": line[:1].upper() + line[1:], "warn": warn}


class Measures(QObject):
    changed = Signal()
    _landed = Signal(str, str, dict)          # (key, error, words) from the worker

    def __init__(self, parent=None):
        super().__init__(parent)
        self._known: dict[str, dict] = {}       # clip id + recipe -> {"line", "warn"} (or {} while it is being measured)
        self.error = ""
        self._landed.connect(self._land)

    def of(self, clip_id: str, media: str, recipe: dict) -> dict:
        """The words for this clip's clean-up once measured, {} until then (the first ask starts the measuring)."""
        key = f"{clip_id}|{media}|{sorted(recipe.items())}"
        if key in self._known:
            return self._known[key]
        self._known[key] = {}
        threading.Thread(target=self._run, args=(key, media, recipe), daemon=True, name="clean-measure").start()
        return {}

    def forget(self, clip_id: str):
        """A take was just (re)made for this clip: measure it afresh on the next ask."""
        for k in [k for k in self._known if k.startswith(clip_id + "|")]:
            del self._known[k]

    def _run(self, key, media, recipe):
        try:
            facts = measure_facts(media, recipe)
            self._landed.emit(key, "", words(facts) if facts else {})
        except Exception as e:  # noqa: BLE001  said on the bar, never a silent blank
            self._landed.emit(key, f"Error: clean-up measurement: {getattr(e, 'line', lambda: e)()}", {})

    def _land(self, key, error, said):
        self.error = error
        if key in self._known:
            self._known[key] = said or {"line": "", "warn": ""}
        self.changed.emit()
