"""Measures the sample files themselves (no engine, no render) and checks the default levels against them.

    python devtools/level_files.py kit <drums|studio|jazz> [--write]   a kit's per-piece table, as kit_levels.py makes it
    python devtools/level_files.py inst <name> [<name> ...]            what a plain instrument's recording sounds like, and
                                                                       its level with the preset table's gain on it

The engine-free twin of kit_levels.py / level_match.py: it reads each SFZ the way the engine's sampler picks a region (key,
velocity, first round robin, every layer of the hit summed, each region's `volume`), and measures the loudest 400 ms
(K-weighted LUFS, rostrum_sound/listen/bs1770.py), the same measure. `kit` places every piece against the kit's kick and snare
(kit_levels.PLACE), then sets one gain for the whole kit so its level-match groove (kick, snare, eighth hats) is as loud as
the kit as recorded, and writes engine/data/kit_levels.json with `--write` (rebuild the engine after). Checked on the studio
and rock kits: within about 1.5 dB of the engine's own table, piece by piece (the engine tames transients, this does not).
It ignores the performance layer, envelopes and pitch shift: a number says how loud a hit or a held note's recording is, not
how a finished mix sounds.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import checkout_paths  # noqa: E402

checkout_paths.use_this_checkout()

from rostrum_sound.doc import preset_level  # noqa: E402
from rostrum_sound.listen.bs1770 import integrated, k_weight  # noqa: E402

from kit_levels import GROOVE, MOST, PLACE, TABLE as KIT_TABLE  # noqa: E402

SOUNDS = Path.home() / ".rostrum" / "assets" / "sounds"
SR = 48000
VEL = 108                                  # velocity 0.85
GM = {"kick": 36, "kick2": 35, "rim": 37, "snare": 38, "clap": 39, "snare2": 40, "hat": 42, "pedalHat": 44, "openHat": 46,
      "lowTom": 41, "floorTom": 43, "tomLow": 45, "tom": 47, "midTom": 47, "tomHigh": 50, "highTom": 50, "crash": 49,
      "cymbal": 49, "ride": 51, "china": 52, "rideBell": 53, "splash": 55, "crash2": 57, "ride2": 59, "stir": 60, "shaker": 70}
KITS = {"drums": ("muldjord-kit/MuldjordKit SFZ+FLAC-20201018/rostrum-gm.sfz", "studio"), "studio": ("studio-kit/studio-kit.sfz", None),
        "jazz": ("swirly-kit/swirly-kit.sfz", "studio")}
PLACE = {**PLACE, "stir": -8}              # the brush circle sits with the ride
# A jazz kit is played from the ride and the brushes with the kick feathered under them (swirly_kit.py): its pieces are placed
# for that, not like a rock kit's (where the ride sits 8 dB under the snare, which buried a ride-and-brushes part).
JAZZ_PLACE = {**PLACE, "kick": -6, "kick2": -6, "ride": 0, "ride2": 0, "rideBell": -3, "stir": -2, "hat": -6, "pedalHat": -6,
              "openHat": -6, "rim": -3, "tom": -3, "midTom": -3, "tomLow": -3, "lowTom": -3, "floorTom": -3, "tomHigh": -3,
              "highTom": -3, "crash": -4, "cymbal": -4, "crash2": -4, "splash": -4, "shaker": -10}


def parse(path: Path) -> list[dict]:
    """The regions of an SFZ, each with its group's / master's / global's opcodes under its own, `sample` made a full path."""
    text = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8", errors="replace"))
    held: dict[str, dict] = {"control": {}, "global": {}, "master": {}, "group": {}}
    regions = []
    for head, body in re.findall(r"<(\w+)>([^<]*)", text):
        ops = {k: v.strip() for k, v in re.findall(r"(\w+)=(.*?)(?=\s+\w+=|\s*$)", body.strip(), re.S)}
        if head == "region":
            r = {**held["global"], **held["master"], **held["group"], **ops}
            r["sample"] = str(path.parent / held["control"].get("default_path", "").replace("\\", "/") / r["sample"].replace("\\", "/"))
            regions.append(r)
        elif head in held:
            held[head] = ops
            if head in ("global", "master"):
                held["group"] = {}
            if head == "global":
                held["master"] = {}
    return regions


def pick(regions: list[dict], key: int, vel: int) -> list[dict]:
    """The layers one hit plays: regions covering key and velocity, the first round robin of each."""
    def covers(r):
        return (int(r.get("lokey", r.get("key", 0))) <= key <= int(r.get("hikey", r.get("key", 127)))
                and int(r.get("lovel", 0)) <= vel <= int(r.get("hivel", 127)) and int(r.get("seq_position", 1)) == 1
                and float(r.get("lorand", 0)) == 0 and r.get("trigger", "attack") == "attack")
    return [r for r in regions if covers(r)]


def read(path: str, rate: int = SR) -> np.ndarray:
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    if sr != rate:
        from scipy.signal import resample_poly
        f = Fraction(rate, sr).limit_denominator(1000)
        x = resample_poly(x, f.numerator, f.denominator, axis=0).astype("float32")
    return np.repeat(x, 2, axis=1) if x.shape[1] == 1 else x[:, :2]


def layers(rs: list[dict]) -> np.ndarray:
    """The picked layers played together, each at its region's `volume`."""
    parts = [read(r["sample"]) * 10 ** (float(r.get("volume", 0)) / 20) for r in rs]
    out = np.zeros((max(len(p) for p in parts), 2), "float32")
    for p in parts:
        out[:len(p)] += p
    return out


def loudest_400ms(x: np.ndarray) -> float:
    p = (k_weight(x, SR) ** 2).sum(axis=1)
    w = int(0.4 * SR)
    c = np.concatenate([[0], np.cumsum(p)])
    return float(-0.691 + 10 * np.log10(((c[w:] - c[:-w]) / w).max() + 1e-12)) if len(c) > w else -120.0


def kit_hits(kit: str) -> dict[str, np.ndarray]:
    """{piece: one hit} on the kit's SFZ, the keys it lacks from its fill kit."""
    main, fill = KITS[kit]
    pools = [parse(SOUNDS / main)] + ([parse(SOUNDS / KITS[fill][0])] if fill else [])
    out = {}
    for name, key in GM.items():
        for regions in pools:
            if (rs := pick(regions, key, VEL)):
                out[name] = layers(rs)
                break
    return out


def kit_table(kit: str) -> dict[str, float]:
    place = JAZZ_PLACE if kit == "jazz" else PLACE
    hits = kit_hits(kit)
    loud = {d: loudest_400ms(h) for d, h in hits.items() if d in place}
    ref = loud["snare"] if kit == "jazz" else (loud["kick"] + loud["snare"]) / 2     # the brush snare is the jazz kit's own level
    gains = {d: float(np.clip(ref + place[d] - v, -MOST, MOST)) for d, v in loud.items()}
    main, fill = KITS[kit]
    pools = [parse(SOUNDS / main)] + ([parse(SOUNDS / KITS[fill][0])] if fill else [])

    def groove(db: dict[str, float]) -> float:
        song = np.zeros((int(8.5 * SR), 2), "float32")
        for d, t, v in GROOVE:
            rs = next(r for r in (pick(p, GM[d], round(v * 127)) for p in pools) if r)
            h = layers(rs) * 10 ** (db.get(d, 0.0) / 20)
            a = int(t * SR)
            song[a:a + len(h)] += h[:len(song) - a]
        return integrated(song, SR)
    shift = groove({}) - groove(gains)
    return {d: round(g + shift, 2) for d, g in sorted(gains.items())}


def calibration(engine: dict) -> float:
    """The median dB the engine's own table sits above this tool's, over the kits the engine measured (it tames transients, so
    its whole-kit gain differs a little from the raw recordings'): added to a kit only this tool has measured."""
    gaps = [engine[k][d] - g for k in engine if k in KITS for d, g in kit_table(k).items() if d in engine[k]]
    return float(np.median(gaps))


def instrument_levels(names: list[str]) -> None:
    """For each plain instrument: the recording's loudest 400 ms at a mid note, velocity 100, and with the table's gain on it."""
    table = preset_level.starting_levels_db()
    for name in names:
        found = _recorded(name)
        if not found:
            print(f"{name}: not a recorded instrument here")
            continue
        regions, key = found
        rs = pick(regions, key, 100)
        if not rs:
            print(f"{name}: no region at key {key}")
            continue
        try:
            raw = loudest_400ms(layers(rs[:1]))
        except (OSError, sf.LibsndfileError) as e:
            print(f"{name}: a sample could not be read ({e})")
            continue
        start = table.get(f"builtIn:{name}", 0.0)
        print(f"{name:14} key {key}: recording {raw:6.1f} LUFS, table gain {start:+5.1f} dB -> {raw + start:6.1f}")


def _recorded(name: str):
    """(regions, a mid key the first articulation covers) for a plain name, from the engine's table (contract/names_instruments.rs)."""
    src = (Path(__file__).resolve().parents[2] / "engine" / "src" / "contract" / "names_instruments.rs").read_text(encoding="utf-8")
    plain = re.search(rf'\("{name}", Rec\("(\w+)"', src)
    entry = plain and re.search(rf'rec\("{plain.group(1)}", (\w+|"[^"]+"), "[^"]*", \((\d+), (\d+)\), &\[\("\w+", "([^"]+)"\)', src)
    if not entry:
        return None
    pack = {"VS": "vsco2-strings", "VB": "vsco2-brass", "VW": "vsco2-woodwinds", "VM": "vcsl-mallets"}.get(entry.group(1), entry.group(1).strip('"'))
    lo, hi = int(entry.group(2)), int(entry.group(3))
    return parse(SOUNDS / pack / entry.group(4)), (lo + hi) // 2


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("what", choices=["kit", "inst"])
    p.add_argument("names", nargs="+")
    p.add_argument("--write", action="store_true")
    a = p.parse_args()
    if a.what == "inst":
        return instrument_levels(a.names)
    for kit in a.names:
        now = json.loads(KIT_TABLE.read_text(encoding="utf-8"))
        table = kit_table(kit)
        if kit not in now["kits"]:             # a kit the engine never measured: this tool's numbers, brought to the engine's scale
            offset = calibration(now["kits"])
            table = {d: round(g + offset, 2) for d, g in table.items()}
            print(f"{kit}: no engine table to compare; moved by {offset:+.2f} dB, the median gap on the kits it has")
        print(kit, " ".join(f"{d} {g:+.1f}" + (f" (engine {now['kits'][kit][d]:+.1f})" if d in now["kits"].get(kit, {}) else "") for d, g in table.items()))
        if a.write:
            now["kits"][kit] = table
            KIT_TABLE.write_text(json.dumps(now, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
