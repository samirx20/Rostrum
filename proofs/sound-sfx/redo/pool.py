"""The candidate pool: every downloaded take cut into single sounds, measured, grouped by kind.

A long recording ("padlock and key handling", 11 s) holds dozens of small sounds; the agent needs
each one on its own, starting exactly on its transient, to place it on a frame. So:
- `hits` kinds: one cut per onset (librosa, backtracked to the start of the attack), from 5 ms
  before it to the next onset or `max_s`, the tail trimmed where it falls 40 dB under its peak;
- `beds` kinds (cloth, slides, room): windows of `length` over the loud stretches.
Each cut gets facts: peak dBFS, the file's noise floor, peak-to-floor, attack (ms), brightness
(spectral centroid, Hz), length. Cuts whose peak is under 18 dB above the file's floor are noisy
recordings, dropped.

Run (from proofs/sound-sfx, main venv):  python -m redo.pool <out.json>
"""
import json
import sys
from pathlib import Path

import librosa
import numpy as np

from .kinds import KINDS, TAKES_JSON

SR, HOP = 48000, 128


def _db(x):
    return 20 * np.log10(max(float(x), 1e-9))


def _facts(x, a, b, floor_db):
    seg = x[a:b]
    pk = int(np.argmax(np.abs(seg)))
    spec = np.abs(np.fft.rfft(seg * np.hanning(seg.size)))
    freqs = np.fft.rfftfreq(seg.size, 1 / SR)
    peak_db = _db(np.abs(seg).max())
    return {"offset": round(a / SR, 4), "length": round((b - a) / SR, 4), "peak_db": round(peak_db, 1),
            "floor_db": round(floor_db, 1), "snr_db": round(peak_db - floor_db, 1),
            "attack_ms": round(pk / SR * 1000, 1),
            "centroid_hz": round(float((spec * freqs).sum() / max(spec.sum(), 1e-9)))}


def _rms_db(x):
    r = librosa.feature.rms(y=x, frame_length=1024, hop_length=HOP)[0]
    return 20 * np.log10(np.maximum(r, 1e-9))


def hits(x, k):
    env = _rms_db(x)
    floor = float(np.percentile(env, 10))
    on = librosa.onset.onset_detect(y=x, sr=SR, hop_length=HOP, backtrack=True, units="samples", delta=0.12)
    out = []
    for i, a in enumerate(on):
        a = max(0, int(a) - int(0.005 * SR))
        b = min(x.size, a + int(k["max_s"] * SR), int(on[i + 1]) if i + 1 < len(on) else x.size)
        seg_env = env[a // HOP: max(a // HOP + 1, b // HOP)]
        pk = int(np.argmax(seg_env))
        quiet = np.nonzero(seg_env[pk:] < seg_env[pk] - 40)[0]
        if quiet.size:
            b = min(b, a + (pk + int(quiet[0])) * HOP)
        if b - a >= int(k.get("min_s", 0.04) * SR):
            out.append(_facts(x, a, b, floor))
    return out


def beds(x, k):
    env = _rms_db(x)
    floor = float(np.percentile(env, 10))
    n = int(k["length"] * SR)
    if x.size <= n:
        return [_facts(x, 0, x.size, floor)]
    starts = range(0, x.size - n, n // 2)
    loud = sorted(starts, key=lambda s: -float(np.mean(env[s // HOP:(s + n) // HOP])))
    return [_facts(x, s, s + n, floor) for s in sorted(loud[:k.get("per_file", 4)])]


def build():
    takes = json.loads(Path(TAKES_JSON).read_text(encoding="utf-8"))
    pool = []
    for kind, k in KINDS.items():
        files = [t for t in takes if any(w in t["label"].lower() or w in t["path"].lower() for w in k["words"])
                 and not any(w in t["label"].lower() for w in k.get("not", []))]
        if not files:
            raise RuntimeError(f'kind "{kind}": no take matches {k["words"]}')
        for t in files:
            x, _ = librosa.load(t["path"], sr=SR, mono=True)
            if x.size < int(0.05 * SR):
                continue
            cuts = (hits if k["mode"] == "hits" else beds)(x, k)
            cuts = [c for c in cuts if c["snr_db"] >= k.get("min_snr", 18)]
            cuts = sorted(cuts, key=lambda c: -c["peak_db"])[:k.get("per_file", 10)]
            for c in cuts:
                pool.append({"kind": kind, "path": t["path"], "label": t["label"], "licence": t["licence"],
                             "author": t["author"], "source_url": t["source_url"], **c})
    return pool


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python -m redo.pool <out.json>")
    pool = build()
    Path(sys.argv[1]).write_text(json.dumps(pool, indent=1), encoding="utf-8")
    counts = {k: sum(1 for c in pool if c["kind"] == k) for k in KINDS}
    print(json.dumps({"cuts": len(pool), "per_kind": counts, "out": sys.argv[1]}))


if __name__ == "__main__":
    main()
