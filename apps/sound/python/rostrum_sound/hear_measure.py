"""A heard stretch as numbers (render_audition's `measure`, on by default): for an agent that cannot hear, the moment
read as measurements, never a verdict.

    measure(wav, r, step=None)  # -> {"step_s", "loudness": [{"t", "lufs"}], "bands": [{"t", sub, bass, lowMid, mid, high}],
                                #     "hits": [{"t", "db"}], "strongest_hit": {"t", "db"},
                                #     "loudest_row": {"t", "lufs"}, "parts": [{id, lufs, peak_db, from_s, to_s,
                                #     onsets, bands}]}
    lines(m, written=None)      # the same, as a few lines of plain numbers

Times are song seconds. `loudness`: LUFS (K-weighted, BS.1770) over each `step` of the stretch, from its start.
`bands`: the energy (dB, full scale) per band over each step, the engine's bands (sub < 60 Hz, bass 60-250, lowMid
250-1k, mid 1-4 kHz, high 4-16 kHz), so the mix's rows and each part's figures name the same ranges. `hits`: where the
mix's level jumps (10 ms frames, RISE_DB over the loudest of the 50 ms before, above -50 dBFS, 80 ms apart: the engine's
rule for a part's starts, with a smaller rise since in a mix other parts ring under a hit), with the peak (dBFS) of the
50 ms from there; `strongest_hit` is the sharpest attack, `loudest_row` the loudest stretch of sound (a
swell can be loudest after its strongest hit). `parts`: each track alone as it reaches the mix (before the
master), as the engine measured it over the stretch: integrated LUFS, peak, when it first / last sounds, where its
sounds start, its bands. A start in the stretch's first 20 ms is not counted (the cut begins there, so everything
sounding would read as a start). Reading the WAV and measuring a 4 s stretch takes a few tens of milliseconds.
"""
from __future__ import annotations

import math

import numpy as np

BANDS = (("sub", 20.0, 60.0), ("bass", 60.0, 250.0), ("lowMid", 250.0, 1000.0), ("mid", 1000.0, 4000.0), ("high", 4000.0, 16000.0))
FLOOR = -70.0
RISE_DB = 6.0                 # the mix's hits (a part alone: the engine's 12 dB)
EDGE_S = 0.02                 # a start this close to the stretch's beginning is the cut, not a sound


def step_for(seconds: float) -> float:
    """Rows of 0.5 s up to 8 s, 1 s up to 20 s, else 2 s or more: about 16 rows at most."""
    return 0.5 if seconds <= 8 else 1.0 if seconds <= 20 else max(2.0, math.ceil(seconds / 16))


def _biquad(b, a, w):
    z = np.exp(-1j * w)
    return (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)


def _k_weight(freqs: np.ndarray, sr: float) -> np.ndarray:
    """|H|^2 of the BS.1770 K filter (the high shelf, then the high pass) at `freqs`."""
    w = 2 * np.pi * freqs / sr
    A, w0 = 10 ** (4.0 / 40), 2 * np.pi * 1500.0 / sr
    c, s = math.cos(w0), 2 * math.sqrt(A) * math.sin(w0) / math.sqrt(2)          # Q = 1/sqrt(2)
    shelf = _biquad((A * ((A + 1) + (A - 1) * c + s), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - s)),
                    ((A + 1) - (A - 1) * c + s, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - s), w)
    w1 = 2 * np.pi * 38.0 / sr
    al, c = math.sin(w1) / (2 * 0.5), math.cos(w1)
    hp = _biquad(((1 + c) / 2, -(1 + c), (1 + c) / 2), (1 + al, -2 * c, 1 - al), w)
    return np.abs(shelf * hp) ** 2


def _db(power: float) -> float:
    return round(max(FLOOR, 10 * math.log10(power)) if power > 0 else FLOOR, 1)


def _rows(y: np.ndarray, sr: float, a: float, step: float):
    """Per row: loudness from the row's whole spectrum (rectangular, so a hit on the row's edge counts in full), bands
    from 2048-sample Hann frames (half overlapping) whose middle falls in the row."""
    n, N, hop = max(1, int(round(step * sr))), 2048, 1024
    x = np.pad(y.mean(axis=1), (N // 2, N))
    starts = np.arange(0, max(1, len(y)), hop)
    win = np.hanning(N).astype(np.float32)
    fr = np.stack([x[s:s + N] for s in starts]) * win
    stft = np.abs(np.fft.rfft(fr, axis=1)) ** 2 * 2 / (N * float((win ** 2).sum()))
    fN = np.fft.rfftfreq(N, 1 / sr)
    per = np.stack([stft[:, (fN >= lo) & (fN < hi)].sum(axis=1) for _, lo, hi in BANDS], axis=1)
    loud, bands = [], []
    for s in range(0, len(y), n):
        seg = y[s:s + n]
        if len(seg) < n // 4 and s:                  # a sliver at the end: not a row of its own
            break
        f = np.fft.rfftfreq(len(seg), 1 / sr)
        power = (np.abs(np.fft.rfft(seg, axis=0)) ** 2).sum(axis=1) * 2 / len(seg) ** 2     # mean square, channels summed
        ms = float((power * _k_weight(f, sr)).sum())
        t = round(a + s / sr, 2)
        loud.append({"t": t, "lufs": round(max(FLOOR, -0.691 + 10 * math.log10(ms)), 1) if ms > 0 else FLOOR})
        rows = per[(starts >= s) & (starts < s + n)]
        bands.append({"t": t, **{k: _db(float(rows[:, i].mean()) if len(rows) else 0.0) for i, (k, _, _) in enumerate(BANDS)}})
    return loud, bands


def _hits(y: np.ndarray, sr: float, a: float) -> list[dict]:
    hop = max(1, int(sr * 0.01))
    m = np.abs(y).max(axis=1)
    k = len(m) // hop
    if not k:
        return []
    fr = 20 * np.log10(np.maximum(m[:k * hop].reshape(k, hop).max(axis=1), 1e-6))
    out, last = [], -1.0
    for i in range(k):
        t = i * 0.01
        if fr[i] < -50 or t < EDGE_S or fr[max(0, i - 5):i].max(initial=-120.0) + RISE_DB > fr[i] or t - last < 0.08:
            continue
        out.append({"t": round(a + t, 2), "db": round(float(fr[i:i + 5].max()), 1)})
        last = t
    return out


def _parts(r: dict, a: float) -> list[dict]:
    out = []
    for p in r.get("tracks") or []:
        span = p.get("span")
        bands = p.get("bands") or []
        out.append({"id": p.get("id"), "lufs": round(p["lufs"], 1) if p.get("lufs") is not None and p["lufs"] > -200 else None,
                    "peak_db": round(20 * math.log10(max(p.get("peak") or 0, 1e-6)), 1),
                    "from_s": round(a + span[0], 2) if span else None, "to_s": round(a + span[1], 2) if span else None,
                    "onsets": [round(a + t, 2) for t in p.get("onsets") or [] if t >= EDGE_S],
                    "bands": {k: round(v, 1) for (k, _, _), v in zip(BANDS, bands)}})
    return out


def measure(wav: str, r: dict, step: float | None = None) -> dict:
    """The stretch's numbers (see the module doc) from its WAV and the engine's reply `r` (from_s, to_s, tracks)."""
    import soundfile as sf
    y, sr = sf.read(wav, dtype="float32", always_2d=True)
    a = float(r.get("from_s", 0.0))
    step = float(step) if step else step_for(len(y) / sr)
    loud, bands = _rows(y, sr, a, step)
    hits = _hits(y, sr, a)
    return {"step_s": step, "loudness": loud, "bands": bands, "hits": hits,
            "strongest_hit": max(hits, key=lambda h: h["db"]) if hits else None,
            "loudest_row": max(loud, key=lambda x: x["lufs"]) if loud else None, "parts": _parts(r, a)}


def _num(v) -> str:
    return "silent" if v is None else f"{v:.1f}"


def lines(m: dict, written: dict | None = None) -> str:
    """The numbers as a few plain lines (times in song seconds)."""
    top = m.get("loudest_row")
    out = [f"Loudness per {m['step_s']:g} s (LUFS, row from): " + ", ".join(f"{r['t']:.1f}s {r['lufs']:.1f}" for r in m["loudness"])
           + (f"; loudest row {top['t']:.1f}s {top['lufs']:.1f}" if top else "")]
    out.append("Bands per row (dB; sub<60 Hz, bass 60-250, lowMid 250-1k, mid 1-4k, high 4-16k):")
    out += [f"  {r['t']:.1f}s " + " ".join(f"{k} {r[k]:.0f}" for k, _, _ in BANDS) for r in m["bands"]]
    hits = m["hits"]
    out.append(f"Mix hits ({len(hits)}, s @ dBFS): " + (", ".join(f"{h['t']:g}@{h['db']:.1f}" for h in hits[:16])
               + (f" ... {len(hits) - 16} more" if len(hits) > 16 else "") + f"; strongest hit {m['strongest_hit']['t']:g}@{m['strongest_hit']['db']:.1f}" if hits else "none"))
    for p in m["parts"]:
        sounds = f"sounds {p['from_s']:g}-{p['to_s']:g}" if p["from_s"] is not None else "silent here"
        ons = p["onsets"]
        b = p["bands"]
        out.append(f"Part {p['id']} (alone, before master): {_num(p['lufs'])} LUFS, peak {p['peak_db']:.1f} dB, {sounds}; "
                   f"{len(ons)} starts" + (" " + " ".join(f"{t:g}" for t in ons[:12]) + (" ..." if len(ons) > 12 else "") if ons else "")
                   + ("; bands " + " ".join(f"{k} {v:.0f}" for k, v in b.items()) if b and p["from_s"] is not None else ""))
    if written:
        for o in written.get("over") or []:
            rng = f", {o['low']}-{o['high']}" if o.get("low") else ""
            first = f", first {o['first_s']:g} last {o['last_s']:g}" if o.get("first_s") is not None else ""
            out.append(f"Written {o['track']}: {o.get('notes', 0)} notes, {o.get('hits', 0)} hits{rng}{first}")
        at = written.get("at")
        if at:
            what = "; ".join(f"{t['track']} " + " ".join([n["pitch"] for n in t.get("notes", [])] + [str(h["drum"]) for h in t.get("hits", [])])
                             for t in at.get("tracks", []))
            out.append(f"Sounding at {at['t']:g} s: {what or 'nothing written'}" + (f"; chord {at['chord']}" if at.get("chord") else ""))
    return "\n".join(out)
