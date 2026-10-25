"""The written arrangement as facts, read from the document (no render needed): every track's notes, hits and clips
in seconds, the markers, sections and bar lines, and for every marker what each track starts nearest it.

Times go through `doc/times.py` (the one place they become seconds), so this is what the render plays.
"""
from __future__ import annotations

from rostrum_core import RostrumError

from ..doc import keys, markers, meter, tempo, times

ON_MS = 10.0     # a start this close to a marker is "on" it


def _clip_len(c: dict) -> float:
    n = c.get("length")
    return float(n) * float(c.get("stretch", 1) or 1) if isinstance(n, (int, float)) else 1.0


def read(data: dict) -> dict:
    """{tracks: [{id, notes: [[start, end, midi, vel]], hits: [[t, drum]], clips: [[start, end]]}], markers, sections,
    bars (every bar line, the closing one included), bar_count, end}."""
    tracks, last, broken = [], 0.0, []
    for t in data.get("tracks", []):
        notes = []
        for n in t.get("notes", []):
            s = times.seconds(n["at"], data, n["id"])
            try:
                e = s + times.length_seconds(n["dur"], data, s, n, n["id"])
            except RostrumError:                  # a broken tie is a warning here: drawn as a short stub, listed
                e = s + 0.05
                broken.append(n["id"])
            for m in keys.midis(n["pitch"]):
                notes.append([s, e, m, float(n.get("vel", 0.8) or 0.8)])
        hits = [[times.seconds(h["at"], data, h["id"]), str(h["drum"])] for h in t.get("hits", [])]
        clips = [[s, s + _clip_len(c)] for c in t.get("clips", []) for s in [times.seconds(c["at"], data, c["id"])]]
        lines = [[times.seconds(x["at"], data, x["id"]), str(x.get("text", ""))[:24]] for x in t.get("lines", [])]
        ends = [n[1] for n in notes] + [h[0] + 0.2 for h in hits] + [c[1] for c in clips] + [x[0] + 1 for x in lines]
        last = max([last, *ends])
        tracks.append({"id": t["id"], "notes": notes, "hits": hits, "clips": clips, "lines": lines})
    end = times.seconds(data["length"], data, "length") if data.get("length") is not None else last
    sections = [[s["name"], times.seconds(s["at"], data, "section"), times.seconds(s["end"], data, "section")]
                for s in data.get("sections", [])]
    return {"tracks": tracks, "markers": markers.all(data), "sections": sections,
            "bars": meter.bar_seconds(data, end), "bar_count": meter.bar_count(data, end), "end": end, "broken": broken}


def starts(track: dict) -> list[float]:
    return sorted({round(x, 6) for x in [n[0] for n in track["notes"]] + [h[0] for h in track["hits"]] +
                   [c[0] for c in track["clips"]] + [x[0] for x in track["lines"]]})


def near_markers(data: dict, arr: dict) -> list[dict]:
    """Per marker: each track's nearest start, its offset in ms and in beats (+ = after the marker), and which tracks
    start on it (within ON_MS)."""
    out = []
    for name, at in arr["markers"]:
        beat_s = tempo.beat_seconds(data, at)
        rows = []
        for t in arr["tracks"]:
            ss = starts(t)
            if ss:
                s = min(ss, key=lambda x: abs(x - at))
                rows.append({"track": t["id"], "start_s": round(s, 4), "off_ms": round((s - at) * 1000, 1),
                             "off_beats": round((s - at) / beat_s, 3)})
        on = [r["track"] for r in rows if abs(r["off_ms"]) <= ON_MS]
        out.append({"marker": name, "at_s": round(at, 4), "on": on, "tracks": rows})
    return out


def summary(arr: dict, near: list[dict]) -> str:
    busy = "; ".join(f"{t['id']} {len(t['notes'])} notes {len(t['hits'])} hits"
                     + (f" {len(t['clips'])} clips" if t["clips"] else "")
                     + (f" ({starts(t)[0]:.2f}–{max([n[1] for n in t['notes']] + [h[0] for h in t['hits']] + [c[1] for c in t['clips']] or [0]):.2f} s)" if starts(t) else " (empty)")
                     for t in arr["tracks"])
    marks = "; ".join(f'"{m["marker"]}" {m["at_s"]:.2f} s: ' + (", ".join(m["on"]) + " start on it" if m["on"] else
                      "nothing starts on it (nearest " + ", ".join(f'{r["track"]} {r["off_ms"]:+.0f} ms' for r in
                      sorted(m["tracks"], key=lambda r: abs(r["off_ms"]))[:2]) + ")") for m in near)
    broken = arr.get("broken", [])
    return (f"{arr['end']:.2f} s, {arr['bar_count']} bars. Tracks: {busy or 'none'}." + (f" Markers: {marks}." if near else "")
            + (f" {len(broken)} held note(s) end before they start and are drawn short: {', '.join(broken[:5])}"
               f"{' …' * (len(broken) > 5)} (the warnings say how to fix them)." if broken else ""))
