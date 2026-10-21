"""Sync check: sharp sounds' onsets against the motion's sharp events, whooshes' loudest moment against the move's
fastest moment (the onset tool can't see a swell's start; its peak is what the ear locks to).

    python check_sync.py <wav> <new-events.json> [fps]
"""
import json
import sys

import numpy as np

from rostrum_sound.listen.core import load, mono
from rostrum_sound.listen.onsets import onsets

SHARP = {"snap", "press", "step"}


def envelope_peak(m, sr, t0, t1, win=0.01):
    a, b = int(t0 * sr), int(t1 * sr)
    seg = m[a:b] ** 2
    hop = int(win * sr)
    if len(seg) < hop:
        return t0
    rms = [seg[i:i + hop].mean() for i in range(0, len(seg) - hop, hop // 2)]
    return t0 + (int(np.argmax(rms)) * (hop // 2) + hop / 2) / sr


def main():
    wav, evs = sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8"))
    frame = 1.0 / float(sys.argv[3] if len(sys.argv) > 3 else 30)
    sharp = [e["at"] for e in evs if e["kind"] in SHARP] + [e["release"] for e in evs if e["kind"] == "press"]
    sharp += [e["lands"]["at"] for e in evs if e["kind"] == "move" and e["lands"] and e["lands"]["hardness"] >= 0.15]
    r = onsets(wav, expect=sorted(sharp), tolerance=frame)
    y, sr = load(wav)
    m = mono(y)
    rows = [{"at": x["expected_s"], "offset_ms": x["offset_ms"]} for x in r["expected"]]
    worst = max(abs(x["offset_ms"]) for x in rows)
    moves = []
    for e in (e for e in evs if e["kind"] == "move"):
        p = envelope_peak(m, sr, e["at"], e["end"] + 0.1)
        moves.append({"layer": e["layer"], "fastest_s": e["peak_at"], "loudest_s": round(p, 3),
                      "offset_ms": round((p - e["peak_at"]) * 1000, 1)})
    print(json.dumps({"sharp_worst_ms": worst, "sharp_all_within_a_frame": r["all_pass"], "sharp": rows,
                      "whooshes": moves}, indent=1))


if __name__ == "__main__":
    main()
