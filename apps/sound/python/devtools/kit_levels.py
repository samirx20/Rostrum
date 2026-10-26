"""Measures each recorded kit's pieces and writes their starting levels (`apps/sound/engine/data/kit_levels.json`, read by
the engine for an even kit: `{"kit": …, "even": true}`, instruments/sfz/tame.rs). Rebuild the engine after writing.

    python devtools/kit_levels.py [--engine <rostrum-sound.exe>]

Each piece is struck once at velocity 0.85 on an even kit (transients tamed); its loudness is the hit's loudest 400 ms
(K-weighted, LUFS). Every piece is then set to its part's place against the kit's kick and snare (PLACE, dB: kick, snare,
clap and toms level; cymbals, hats, ride, rim and shaker under), at most ±MOST dB, and the whole kit is moved by one
gain so the level-match groove (devtools/level_match.py: kick, snare, eighth hats) is exactly as loud as on the kit as
recorded: the instrument table (library_data/preset_levels.json) stays true for both.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import checkout_paths  # noqa: E402

checkout_paths.use_this_checkout()

from rostrum_sound.engine import Engine  # noqa: E402
from rostrum_sound.listen.bs1770 import integrated, k_weight  # noqa: E402

TABLE = Path(__file__).resolve().parents[2] / "engine" / "data" / "kit_levels.json"
KITS = ("drums", "studio", "jazz")
PLACE = {"kick": 0, "kick2": 0, "snare": 0, "snare2": 0, "clap": 0, "lowTom": 0, "floorTom": 0, "tomLow": 0, "tom": 0,
         "midTom": 0, "tomHigh": 0, "highTom": 0, "rim": -6, "hat": -9, "pedalHat": -9, "openHat": -6, "crash": -4,
         "cymbal": -4, "crash2": -4, "china": -4, "splash": -4, "ride": -8, "ride2": -8, "rideBell": -8, "shaker": -12}
MOST = 12.0
# The level-match groove (devtools/level_match.py kit()): 4 bars at 120 bpm.
GROOVE = [(d, b * 2.0 + at, v) for b in range(4) for d, at, v in
          [("kick", 0, 0.9), ("kick", 1.25, 0.75), ("snare", 0.5, 0.8), ("snare", 1.5, 0.85)] + [("hat", x * 0.25, 0.5) for x in range(8)]]
SCHEDULE = "rostrum-sound-schedule/1"


def hit_lufs(x, sr) -> float:
    p = (k_weight(x, sr) ** 2).sum(axis=1)
    w = int(0.4 * sr)
    c = np.concatenate([[0], np.cumsum(p)])
    return float(-0.691 + 10 * np.log10(((c[w:] - c[:-w]) / w).max() + 1e-12))


def render(engine, out, tracks, length):
    return engine.request("render", schedule={"contract": SCHEDULE, "length": length, "tracks": tracks}, out=str(out),
                          stems="all", master=False)


def kit_table(engine, out, kit, now: dict) -> dict:
    """{piece: dB} for one kit: measured on the even kit (the table it plays now taken back out)."""
    names = engine.request("range", instrument={"kit": kit})["drums"]
    tracks = [{"id": d, "instrument": {"kit": kit, "even": True}, "perform": False, "volume": 1, "hits": [{"drum": d, "at": 0.2, "vel": 0.85}]}
              for d in names if d in PLACE]
    r = render(engine, out, tracks, 3)
    loud = {t["id"]: hit_lufs(*sf.read(r["stems"][t["id"]])) - now.get(t["id"], 0.0) for t in tracks}
    ref = (loud["kick"] + loud["snare"]) / 2
    gains = {d: float(np.clip(ref + PLACE[d] - v, -MOST, MOST)) for d, v in loud.items()}
    # One gain for the whole kit: the groove as loud as on the kit as recorded.
    raw = render(engine, out, [{"id": "g", "instrument": {"kit": kit}, "perform": False, "volume": 1,
                                "hits": [{"drum": d, "at": t, "vel": v} for d, t, v in GROOVE]}], 8.5)
    target = integrated(sf.read(raw["stems"]["g"])[0], 48000)
    parts = render(engine, out, [{"id": d, "instrument": {"kit": kit, "even": True}, "perform": False, "volume": 1,
                                  "hits": [{"drum": d, "at": t, "vel": v} for dd, t, v in GROOVE if dd == d]} for d in ("kick", "snare", "hat")], 8.5)
    mix = sum(sf.read(parts["stems"][d])[0] * 10 ** ((gains[d] - now.get(d, 0.0)) / 20) for d in ("kick", "snare", "hat"))
    shift = target - integrated(mix, 48000)
    return {d: round(g + shift, 2) for d, g in sorted(gains.items())}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--engine")
    a = p.parse_args()
    now = json.loads(TABLE.read_text(encoding="utf-8"))["kits"] if TABLE.exists() else {}
    engine = Engine(Path(a.engine) if a.engine else None)
    out = Path(os.environ.get("TEMP", ".")) / "kit_levels.wav"
    try:
        kits = {k: kit_table(engine, out, k, now.get(k, {})) for k in KITS}
    finally:
        engine.close()
    TABLE.write_text(json.dumps({"about": "Each recorded kit piece's starting level (dB) on an even kit: measured by "
                                          "apps/sound/python/devtools/kit_levels.py (hit loudness at velocity 0.85, placed "
                                          "against the kit's kick and snare, the level-match groove kept as loud as the "
                                          "kit as recorded). Rebuild the engine after a change.", "kits": kits}, indent=1) + "\n",
                     encoding="utf-8")
    for k, t in kits.items():
        print(k, " ".join(f"{d} {g:+.1f}" for d, g in t.items()))


if __name__ == "__main__":
    main()
