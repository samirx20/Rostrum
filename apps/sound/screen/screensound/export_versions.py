"""What the Export sheet adds to one delivery (no Qt): the ranges a song has ("What": the whole song · the time range ·
a section) and "+ Another version" rows, each its own target, file type and quality, rendered as its own version
(`renders/<song>/vNNN/`) when Export runs. The first delivery is the sheet's own choices (the master's target); an extra
row's target does not touch the master: its render is compiled from a copy of the song with that target's numbers.
"""
from __future__ import annotations

import copy

from rostrum_sound import compile as compile_doc
from rostrum_sound import deliver
from rostrum_sound.doc import markers, times

from . import delivery


def ranges(doc, picked) -> list[dict]:
    """[{value, label, start, end}] the song can be exported as: "all", the time range on the ruler when one is set,
    and each section. Times in seconds."""
    out = [{"value": "all", "label": "Whole song", "start": 0, "end": 0}]
    if picked:
        out.append({"value": "range", "label": f"Time range · {_clock(picked[0])}–{_clock(picked[1])}",
                    "start": picked[0], "end": picked[1]})
    with markers.project(doc.folder):
        for s in doc.data.get("sections", []):
            a, b = times.seconds(s["at"], doc.data, s["id"]), times.seconds(s["end"], doc.data, s["id"])
            out.append({"value": f"section:{s['id']}", "label": f"Section · {s.get('name') or s['id']}", "start": a, "end": b})
    return out


def _clock(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


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
    same gain, and past the ceiling the limiter holds it (amber: the loud parts get squeezed). {} before a render."""
    lufs, peak = render.get("lufs"), render.get("truePeak")
    if not isinstance(lufs, (int, float)) or not isinstance(peak, (int, float)):
        return {}
    gain = (render.get("master") or {}).get("gainDb", 0.0) if master.get("normalize") else 0.0
    need = t["lufs"] - (lufs - gain)
    words = f"Will be turned {'up' if need > 0 else 'down'} {abs(need):.1f} dB to reach {_n(t['lufs'])}"
    over = peak - gain + need - t["peak"]
    if over > 0.05:
        return {"ok": False, "text": f"{words}; the loudest peak would pass {_n(t['peak'])} by {over:.1f} dB, so the limiter holds it down"}
    return {"ok": True, "text": f"{words}; the loudest peak stays under {_n(t['peak'])}"}


def schedule_for(doc, target: str):
    """The song compiled as if its master had `target`'s numbers (the song itself is not changed)."""
    data, t = copy.deepcopy(doc.data), delivery.BY_KEY[target]
    data["master"][0].update(normalize=True, loudness=t["lufs"], truePeak=t["peak"])
    with markers.project(doc.folder):
        return compile_doc(data)
