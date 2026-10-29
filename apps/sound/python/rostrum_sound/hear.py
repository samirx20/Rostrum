"""Hearing one stretch of the song in about a second, without a full render (render_audition with `from` / `at`):
the engine renders the stretch itself (contract: `render` with from / to), as it is in the whole song's render: mastered
with the song's own decisions (master_memo.py: the gain to the target, the limiter's hold), sample for sample what the
full render has there. With those decisions known it renders on its own: the tracks from the render cache, a changed
track only over the stretch and a few seconds before it, the master stage on that span. Without them (the song's first
listen) the song is mastered whole once and the stretch cut from it; its decisions are kept for the next. The WAV is kept by content in the engine's
share of the one cache (`sound/auditions/`): the same stretch of the same song again is the same file, found at once.
Nothing in the document changes and no version is written (a check, not a delivery: render_mix makes those).

    hear(engine, doc, start, end, solo=None, mute=None, master=True, song=None)  # -> {file, from_s, to_s, cached, mastered, ...}
    picture(png, wav, result)                                          # the stretch: wave, loudness, spectrum over time
    notes(wav, doc, result)                                            # the asked moments inside it, measured

A picture is drawn with Pillow and numpy (no plotting library to load), so it costs tens of milliseconds.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from rostrum_core.cache import LEVELS, put_file

from . import master_memo, settings
from .compile import compile as compile_doc
from .doc import markers

KEEP = ("lufs", "truePeak", "peak", "lra", "clipped", "renderSeconds", "series", "master", "tracks")   # tracks: each part over the stretch (hear_measure)
MOST_S = 60.0                 # one stretch at most (longer: render_mix with from / to)


def window(start: float, end: float | None, around: float | None) -> tuple[float, float]:
    """[from, to] seconds: `around` seconds each side of `start` (an `at`), else start .. end, else 4 s from start."""
    if around is not None:
        return max(0.0, start - around), start + around
    return start, end if end is not None else start + 4.0


def _key(schedule: dict, a: float, b: float, given) -> str:
    return hashlib.sha256((json.dumps(schedule, sort_keys=True, default=str) + f"|{a:.4f}|{b:.4f}|{json.dumps(given, sort_keys=True)}").encode()).hexdigest()[:24]


def hear(engine, doc: dict, start: float, end: float, solo=None, mute=None, master: bool = True, out_dir: Path | None = None,
         song: str | None = None) -> dict:
    """The stretch [start, end) of the song as it is written now, rendered once into the content-keyed cache. `song`
    (master_memo.song_of): whose mastering decisions to use and keep. `mastered`: "song" (the song's decisions as it is
    now), "earlier" (the decisions the song last measured, before a later change), "alone" (no master)."""
    schedule = compile_doc(doc, solo=solo, mute=mute, master=master)
    alone = bool(solo or mute)
    k = master_memo.key(compile_doc(doc, master=master) if alone else schedule)
    given, fresh = master_memo.given(song, k) if song and master else (None, False)
    ask = {"masterAs": given} if given else {"inSong": True} if master else {}
    folder = Path(out_dir) if out_dir else settings.cache_dir() / "sound" / "auditions"
    out = folder / f"{_key(schedule, start, end, given)}.wav"
    facts = out.with_suffix(".json")
    if out.is_file() and out.with_suffix(LEVELS).is_file() and facts.is_file():
        return {**json.loads(facts.read_text(encoding="utf-8")), "file": str(out), "cached": True}
    r = {}
    put_file(out, lambda tmp: r.update(engine.request("render", schedule=schedule, out=str(tmp), stems=[], **{"from": start, "to": end}, **ask) or {}),
             "render_audition", beside=(LEVELS,))
    if song and not alone and not given:
        master_memo.remember(song, k, r)              # worked out over the song now: the next stretch renders on its own
    if song and given and not fresh:                  # the song changed since it was measured: measured again, for the next
        master_memo.refresh(engine, song, k, compile_doc(doc, master=master) if alone else schedule)
    rng = r.get("range") or [start, end]
    got = {"from_s": round(rng[0], 3), "to_s": round(rng[1], 3), "seconds": round(rng[1] - rng[0], 3), **{k: r[k] for k in KEEP if k in r},
           "mastered": "alone" if not master else "earlier" if given and not fresh else "song", "windowed": bool(r.get("windowed"))}
    facts.write_text(json.dumps(got), encoding="utf-8")
    return {**got, "file": str(out), "cached": False}


def notes(wav: str, doc: dict, r: dict) -> list[dict]:
    """The song's asked moments (markers named hit, stop, drums out, climax ...) inside the stretch, measured on it as
    the listening check measures them, plus a true peak over the master's ceiling and clipped samples. Notes to read."""
    from .listen.faults import check
    from .listen.weakest import from_markers
    a, b = r["from_s"], r["to_s"]
    inside = [{**m, "at": m["at"] - a} for m in from_markers(markers.all(doc)) if a <= m["at"] < b]
    found = check(wav, inside, whole=False)["faults"] if inside else []
    out = [{"id": f.get("id", f["kind"]), "kind": f["kind"], "at_s": round(f["at_s"] + a, 3), "words": f.get("words", "")} for f in found]
    ceiling = ((doc.get("master") or [{}])[0] or {}).get("truePeak", -1)
    if r.get("truePeak") is not None and r["truePeak"] > ceiling:
        out.append({"id": "true_peak", "kind": "true_peak", "at_s": a, "words": f"true peak {r['truePeak']:.1f} dBTP, over the master's {ceiling:g}"})
    if r.get("clipped"):
        out.append({"id": "clipped", "kind": "clipped", "at_s": a, "words": f"{r['clipped']} clipped samples"})
    return out


W, ROW, LEFT = 960, 110, 46        # picture width, one row's height, the scale margin on the left
INK, SOFT, GRID = (40, 40, 40), (110, 110, 110), (228, 228, 224)


def picture(png: str, wav: str, r: dict, title: str) -> str:
    """Three rows over the stretch's own seconds: the wave (peak envelope per pixel), the loudness (short-term and
    momentary LUFS, true peak per 100 ms, in dB), and a spectrum over time (log frequency, 40 Hz .. 16 kHz)."""
    from PIL import Image, ImageDraw
    import soundfile as sf
    y, sr = sf.read(wav, dtype="float32", always_2d=True)
    a, b = r["from_s"], r["to_s"]
    span, pw = max(b - a, 1e-6), W - LEFT
    head, gap = 26, 20
    rows = [head + gap * (i + 1) + ROW * i for i in range(3)]           # each row's top; its title sits in the gap above
    h = rows[2] + ROW + 22
    img = Image.new("RGB", (W, h), (250, 250, 248))
    d = ImageDraw.Draw(img)
    d.text((6, 6), f"{title}: {a:.2f} - {b:.2f} s    {r.get('lufs', -70):.1f} LUFS, true peak {r.get('truePeak', -120):.1f} dBTP", fill=INK)
    step = next(s for s in (0.25, 0.5, 1, 2, 5, 10) if span / s <= 12)
    ticks = [t for t in np.arange(np.ceil(a / step) * step, b + 1e-9, step)]
    xs = [LEFT + (t - a) / span * (pw - 1) for t in ticks]
    for top in rows[:2]:                          # the seconds grid under the wave and the loudness
        for x in xs:
            d.line([(x, top), (x, top + ROW)], fill=GRID)
    # 1. the wave
    top = rows[0]
    d.text((LEFT, top - 14), "wave", fill=SOFT)
    mono = np.abs(y).max(axis=1) if len(y) else np.zeros(1)
    edges = np.linspace(0, len(mono), pw + 1).astype(int)
    mid = top + ROW // 2
    for i in range(pw):
        seg = mono[edges[i]:max(edges[i + 1], edges[i] + 1)]
        v = float(seg.max()) if len(seg) else 0.0
        d.line([(LEFT + i, mid - v * ROW / 2), (LEFT + i, mid + v * ROW / 2)], fill=(60, 110, 200))
    # 2. loudness over time
    top = rows[1]
    d.text((LEFT, top - 14), "loudness (dB): short-term dark green, momentary light green, true peak red", fill=SOFT)
    lo, hi = -50.0, 0.0
    yof = lambda v: top + ROW - (min(max(v, lo), hi) - lo) / (hi - lo) * ROW   # noqa: E731
    for db in (-40, -30, -20, -10, 0):
        d.line([(LEFT, yof(db)), (W, yof(db))], fill=GRID)
        d.text((6, yof(db) - 6), f"{db}", fill=SOFT)
    ser = r.get("series") or {}
    for key, colour in (("momentary", (165, 205, 165)), ("shortTerm", (40, 140, 60)), ("truePeak", (205, 80, 60))):
        vals = ser.get(key) or []
        pts = [(LEFT + i / max(1, len(vals) - 1) * (pw - 1), yof(v)) for i, v in enumerate(vals) if v is not None]
        if len(pts) > 1:
            d.line(pts, fill=colour, width=2)
    # 3. spectrum over time
    top = rows[2]
    d.text((LEFT, top - 14), "spectrum, 40 Hz - 16 kHz (darker = louder)", fill=SOFT)
    x = y.mean(axis=1) if len(y) else np.zeros(2048)
    n = 2048
    x = np.pad(x, (0, max(0, n - len(x))))
    starts = np.linspace(0, len(x) - n, pw).astype(int)
    frames = np.stack([x[s:s + n] for s in starts])
    spec = np.abs(np.fft.rfft(frames * np.hanning(n), axis=1)) + 1e-9
    freqs = np.fft.rfftfreq(n, 1 / sr)
    bands = np.geomspace(40, min(16000, sr / 2), ROW)[::-1]
    lvl = 20 * np.log10(spec[:, np.clip(np.searchsorted(freqs, bands), 0, len(freqs) - 1)].T)
    lvl = np.clip((lvl - (lvl.max() - 70)) / 70, 0, 1)
    shade = (255 * (1 - lvl)).astype(np.uint8)
    img.paste(Image.fromarray(np.stack([shade, shade, np.minimum(255, shade.astype(int) + 12).astype(np.uint8)], axis=2), "RGB"), (LEFT, top))
    for f, label in ((100, "100"), (1000, "1k"), (10000, "10k")):
        yy = top + int(np.searchsorted(-bands, -f))
        d.line([(LEFT - 6, yy), (LEFT - 1, yy)], fill=SOFT)
        d.text((6, yy - 6), label, fill=SOFT)
    # the song's seconds under the rows
    for t, x0 in zip(ticks, xs):
        d.line([(x0, top + ROW), (x0, top + ROW + 4)], fill=SOFT)
        d.text((x0 - 8, top + ROW + 6), f"{t:g} s", fill=INK)
    Path(png).parent.mkdir(parents=True, exist_ok=True)
    img.save(png)
    return png
