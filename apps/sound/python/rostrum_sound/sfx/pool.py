"""The cut pool: a recording cut into single sounds on their transients, each measured.

A long recording ("padlock handling", 11 s) holds dozens of small sounds; the agent needs each on
its own, starting on its transient, to place it on a frame. Analysis runs once per file and is
stored (content-keyed cache), so later calls only read JSON."""
import hashlib
import json
import os
from pathlib import Path

import librosa
import numpy as np

from ..listen.core import LOW_END_HZ, band_share

ANALYSIS_VERSION = 1
SR, HOP = 48000, 128
LEAD_S = 0.005                      # a cut starts 5 ms before its transient
DEFAULTS = {"mode": "hits", "max_s": 0.6, "min_s": 0.04, "per_file": 25, "min_snr": 18.0, "length": 0.5}
CACHE_DIR = Path(os.path.expanduser("~")) / ".rostrum" / "cache" / "sound-pool"


def _db(x):
    return 20 * np.log10(max(float(x), 1e-9))


def _rms_db(x):
    r = librosa.feature.rms(y=x, frame_length=1024, hop_length=HOP)[0]
    return 20 * np.log10(np.maximum(r, 1e-9))


def _facts(x, a, b, floor_db):
    seg = x[a:b]
    spec = np.abs(np.fft.rfft(seg * np.hanning(seg.size)))
    freqs = np.fft.rfftfreq(seg.size, 1 / SR)
    peak = float(_db(np.abs(seg).max()))
    return {"start": round(a / SR, 4), "end": round(b / SR, 4), "peak_db": round(peak, 1),
            "floor_db": round(floor_db, 1), "snr_db": round(peak - float(floor_db), 1),
            "attack_ms": round(int(np.argmax(np.abs(seg))) / SR * 1000, 1),
            "centroid_hz": round(float((spec * freqs).sum() / max(spec.sum(), 1e-9))),
            "low_end_pct": round(100 * band_share(seg, SR, [("low", 0, LOW_END_HZ)])["low"], 1)}


def _hits(x, o, env, floor):
    on = librosa.onset.onset_detect(y=x, sr=SR, hop_length=HOP, backtrack=True, units="samples", delta=0.12)
    out = []
    for i, a in enumerate(on):
        a = max(0, int(a) - int(LEAD_S * SR))
        b = min(x.size, a + int(o["max_s"] * SR), int(on[i + 1]) if i + 1 < len(on) else x.size)
        seg_env = env[a // HOP: max(a // HOP + 1, b // HOP)]
        pk = int(np.argmax(seg_env))
        quiet = np.nonzero(seg_env[pk:] < seg_env[pk] - 40)[0]          # trim the tail 40 dB under the peak
        if quiet.size:
            b = min(b, a + (pk + int(quiet[0])) * HOP)
        if b - a >= int(o["min_s"] * SR):
            out.append(_facts(x, a, b, floor))
    return out


def _beds(x, o, env, floor):
    n = int(o["length"] * SR)
    if x.size <= n:
        return [_facts(x, 0, x.size, floor)]
    loud = sorted(range(0, x.size - n, n // 2), key=lambda s: -float(np.mean(env[s // HOP:(s + n) // HOP])))
    return [_facts(x, s, s + n, floor) for s in sorted(loud[:o["per_file"]])]


def _analyse(path, o):
    """The slow part: read, find the sounds, measure them. Called once per (file, version, options)."""
    x, _ = librosa.load(path, sr=SR, mono=True)
    if x.size < int(0.05 * SR):
        raise ValueError(f"{path}: recording is shorter than 50 ms")
    env = _rms_db(x)
    floor = float(np.percentile(env, 10))
    cuts = (_hits if o["mode"] == "hits" else _beds)(x, o, env, floor)
    cuts = [c for c in cuts if c["snr_db"] >= o["min_snr"]]          # noisy recordings drop out
    return sorted(cuts, key=lambda c: -c["peak_db"])[:o["per_file"]]


def _key(path, o):
    st = os.stat(path)
    raw = json.dumps([os.path.abspath(path), st.st_size, st.st_mtime_ns, ANALYSIS_VERSION, o], sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()


def cut(recording, cache_dir=None, **options):
    """Cut `recording` into single sounds. options: mode ("hits" one cut per transient | "beds"
    windows of `length` s over the loud stretches), max_s, min_s, per_file, min_snr (dB over the
    file's noise floor), length. Returns {"file", "cached", "cuts": [{start, end, peak_db,
    floor_db, snr_db, attack_ms, centroid_hz, low_end_pct}]} (times in seconds, loudest first).
    Cached under ~/.rostrum/cache/sound-pool/ keyed by path, size, mtime and analysis version."""
    path = os.fspath(recording)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{path}: recording not found")
    unknown = set(options) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"cut: unknown options {sorted(unknown)}; use {sorted(DEFAULTS)}")
    o = {**DEFAULTS, **options}
    if o["mode"] not in ("hits", "beds"):
        raise ValueError(f"cut: mode must be 'hits' or 'beds', not '{o['mode']}'")
    store = Path(cache_dir or CACHE_DIR)
    f = store / f"{_key(path, o)}.json"
    if f.is_file():
        return {"file": path, "cached": True, "cuts": json.loads(f.read_text(encoding="utf-8"))}
    cuts = _analyse(path, o)
    store.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(cuts), encoding="utf-8")
    return {"file": path, "cached": False, "cuts": cuts}


def pool(paths, cache_dir=None, **options):
    """`cut` over many recordings -> {"files", "from_cache", "cuts": [{file, ...facts}]}.
    A file that cannot be cut stops the whole call with its name in the error."""
    cuts, cached = [], 0
    for p in paths:
        r = cut(p, cache_dir=cache_dir, **options)
        cached += r["cached"]
        cuts += [{"file": r["file"], **c} for c in r["cuts"]]
    return {"files": len(list(paths)), "from_cache": cached, "cuts": cuts}
