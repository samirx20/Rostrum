"""What the Export sheet adds to one delivery (no Qt): the ranges a song has ("What": the whole song · the time range ·
a section) and "+ Another version" rows, each its own target, file type and quality, rendered as its own version
(`renders/<song>/vNNN/`) when Export runs. The first delivery is the sheet's own choices (the master's target); an extra
row's target does not touch the master: its render is compiled from a copy of the song with that target's numbers.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from rostrum_sound import compile as compile_doc
from rostrum_sound import deliver
from rostrum_sound.doc import markers, musical, times

from . import delivery


def ranges(doc, picked) -> list[dict]:
    """[{value, label, start, end}] the song can be exported as: "all", the time range on the ruler when one is set,
    and each section. Times in seconds."""
    out = [{"value": "all", "label": "Whole song", "start": 0, "end": 0}]
    if picked:
        out.append({"value": "range", "label": f"Time range · {musical.clock(picked[0])}–{musical.clock(picked[1])}",
                    "start": picked[0], "end": picked[1]})
    with markers.project(doc.folder):
        for s in doc.data.get("sections", []):
            a, b = times.seconds(s["at"], doc.data, s["id"]), times.seconds(s["end"], doc.data, s["id"])
            out.append({"value": f"section:{s['id']}", "label": f"Section · {s.get('name') or s['id']}", "start": a, "end": b})
    return out


class Versions:
    """The extra delivery rows: [{target, format, rate}] (rate 0 = the song's own)."""

    def __init__(self):
        self.rows: list[dict] = []

    def add(self, main_target: str, fmt: str) -> None:
        """A new row: another target than the first one's (the next in the list), the same file type."""
        keys = list(delivery.BY_KEY)
        taken = {main_target, *(r["target"] for r in self.rows)}
        self.rows.append({"target": next((k for k in keys if k not in taken), keys[0]), "format": fmt, "rate": 0})

    def remove(self, i: int) -> None:
        if 0 <= i < len(self.rows):
            del self.rows[i]

    def set(self, i: int, **kw) -> None:
        if 0 <= i < len(self.rows):
            self.rows[i].update(kw)

    def shown(self, master: dict, render: dict, doc_rate: int) -> list[dict]:
        """For QML: each row with its live line (what the sound that plays now would become at its target)."""
        out = []
        for r in self.rows:
            rates = [x["id"] for x in deliver.rates_for(r["format"])]
            rate = r["rate"] if r["rate"] in rates else doc_rate if doc_rate in rates else 48000
            out.append({**r, "rate": str(rate), "verdict": expected(delivery.BY_KEY[r["target"]], master, render)})
        return out


def _n(v: float) -> str:
    return f"{v:g}".replace("-", "−")


def expected(t: dict, master: dict, render: dict) -> dict:
    """{ok, text} for a version at target `t`, from the render that plays now: the loudness before its own master gain
    is the measured one less that gain, so the song would be turned up or down to reach `t`; the peak follows by the
    same gain, and past the ceiling the limiter holds it (amber: the loud parts get squeezed), or with gentle limiting
    on, past its most limiting the whole song comes out quieter (amber). {} before a render."""
    lufs, peak = render.get("lufs"), render.get("truePeak")
    if not isinstance(lufs, (int, float)) or not isinstance(peak, (int, float)):
        return {}
    gain = (render.get("master") or {}).get("gainDb", 0.0)        # the target gain, or what gentle limiting held back
    need = t["lufs"] - (lufs - gain)
    words = f"Will be turned {'up' if need > 0 else 'down'} {abs(need):.1f} dB to reach {_n(t['lufs'])}"
    over = peak - gain + need - t["peak"]
    most = master.get("maxLimit", 2) if master.get("gentle") else None
    if most is not None and over > most + 0.05:
        return {"ok": False, "text": f"{words}; the loudest peak would pass {_n(t['peak'])} by {over:.1f} dB, more than gentle "
                                     f"limiting allows, so it comes out about {over - most:.1f} dB quieter than {_n(t['lufs'])}"}
    if over > 0.05:
        return {"ok": False, "text": f"{words}; the loudest peak would pass {_n(t['peak'])} by {over:.1f} dB, so the limiter holds it down"}
    return {"ok": True, "text": f"{words}; the loudest peak stays under {_n(t['peak'])}"}


def schedule_for(doc, target: str):
    """The song compiled as if its master had `target`'s numbers (the song itself is not changed)."""
    data, t = copy.deepcopy(doc.data), delivery.BY_KEY[target]
    data["master"][0].update(normalize=True, loudness=t["lufs"], truePeak=t["peak"])
    with markers.project(doc.folder):
        return compile_doc(data)


def last_choices(folder, item: str) -> dict | None:
    """The sheet's own choices the song's newest export was made with, read from its manifest: {"format", "trim",
    "stems", "markers"} (None: never exported). The sheet starts from them, so stems chosen for the last export are
    still chosen in the next window (critic r8: a new window's sheet said "Only the mix" and the next file went out
    without stems). Extra versions ("+ Another version") come after the first of the same Export run and carry no
    stems. Each export writes the sheet's own choices into its first version's manifest (`export_sheet`), so the newest
    of those is read as it is. Older exports, without it, are read back from what was made: an export with stems is
    always its run's first (extra versions carry none), so a run's version with stems is what the sheet chose (the run
    is the versions made from one song state; two exports of one state, the second with stems, read "off" by the run's
    first version: critic r10 must-fix 3)."""
    base = Path(folder) / "renders" / item if folder and item else None
    if base is None or not base.is_dir():
        return None
    made = []
    for d in base.iterdir():
        if re.match(r"^v\d{3,}$", d.name) and (d / "manifest.json").is_file():
            try:
                made.append(json.loads((d / "manifest.json").read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue                                  # a manifest that can't be read tells nothing: the next one does
    if not made:
        return None
    newest = max(made, key=lambda m: m.get("version", 0))
    run = sorted((m for m in made if m.get("source") == newest.get("source")), key=lambda m: m.get("version", 0))
    said = [m["export_sheet"] for m in run if isinstance(m.get("export_sheet"), dict)]
    if said:
        return {**said[-1], "trim": bool(said[-1].get("trim", True)), "markers": bool(said[-1].get("markers"))}
    m = next((m for m in reversed(run) if m.get("stems") or m.get("bus_stems")), run[0])
    stems = "groups" if m.get("stems_by") else "all" if m.get("stems") or m.get("bus_stems") else "off"
    return {"format": (m.get("format") or {}).get("id"), "trim": bool(m.get("trimmed_silence", True)),
            "stems": stems, "markers": bool(m.get("markers_file"))}
