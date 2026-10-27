"""Make the harmonica's SFZ files and its file list from VCSL's Hohner Super 64 (CC0, a chromatic harmonica).

    python devtools/harmonica_pack.py <tree.json>

`tree.json` is GitHub's recursive tree of sgossner/VCSL at COMMIT (the pin the other VCSL packs use). VCSL ships no
SFZ for its harmonicas, only the samples: three breaths (Normal, Accented, Vib) each sampled on C, E and G of every
octave from C2 to C6 by VCSL's names (they sound an octave higher: C3 to C7), plus a short breath-out "release" sound per sample. This writes one SFZ per breath (the release
sounds trigger when the key lifts, as VCSL's own note suggests, with a short attack: VCSL suggests 100 ms, but the sounds are only ~0.1 s long and it would swallow them) under
`library_data/packs/sfz/vcsl-harmonica/`, and the pack's entry in `library_data/packs/files.json`. The files are stored
under short names (no spaces) inside the pack folder.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

COMMIT = "dfcf4a4918771eee884b96ad4493de82ef84daf6"
BASE = f"https://raw.githubusercontent.com/sgossner/VCSL/{COMMIT}/"
PACKS = Path(__file__).resolve().parents[1] / "rostrum_sound" / "library_data" / "packs"
DIR = "Aerophones/Free Aerophones/Harmonica-Hohner-Super64/"
# the breaths: (VCSL's folder and name stem, the sustain's name pattern, our file, what it is)
BREATHS = [("Normal", "Normal _", "harmonica.sfz"), ("Accented", "Accented_", "harmonica-accent.sfz"), ("Vib", "Vib_", "harmonica-vibrato.sfz")]
ROOTS = {"C": 0, "E": 4, "G": 7}
LOW, HIGH = 47, 98          # playable keys: one below the lowest sample to two above the highest


def key(name: str) -> int:
    """The key a sample sounds on. VCSL names the Super 64's notes an octave low ("C4" sounds C5, 523 Hz: measured),
    so a name's octave is one more than it says (the instrument plays C3 to D7, as Hohner gives it)."""
    return 12 * (int(name[1:]) + 2) + ROOTS[name[0]]


def zones(names: list[str]) -> list[tuple[str, int, int, int]]:
    """(name, key it was sung on, lowest key, highest key): each sample covers half way to its neighbours."""
    ks = sorted((key(n), n) for n in names)
    out = []
    for i, (k, n) in enumerate(ks):
        lo = LOW if i == 0 else (ks[i - 1][0] + k) // 2 + 1
        hi = HIGH if i == len(ks) - 1 else (k + ks[i + 1][0]) // 2
        out.append((n, k, lo, hi))
    return out


def main(tree_path: str) -> None:
    blobs = {e["path"]: e for e in json.loads(Path(tree_path).read_text(encoding="utf-8"))["tree"] if e["type"] == "blob"}
    rows = []        # VCSL's LICENSE file is not at this pin; the pack's catalog entry carries the CC0 notice
    out = PACKS / "sfz" / "vcsl-harmonica"
    out.mkdir(parents=True, exist_ok=True)
    for folder, stem, sfz in BREATHS:
        names = sorted(p.rsplit("_", 1)[1][:-4] for p in blobs if p.startswith(f"{DIR}Sustains/{folder}/"))
        lines = [f"// Rostrum: Hohner Super 64 harmonica, {folder} breath (VCSL, CC0), on every note C3 to C7 (VCSL names them an octave low); the breath-out sound plays when a key lifts (packMaps)."]
        lines.append("<global> loop_mode=no_loop amp_veltrack=60 ampeg_attack=0.01 ampeg_release=0.12")
        for name, k, lo, hi in zones(names):
            src = f"{DIR}Sustains/{folder}/Hohner-Super64_{stem}{name}.wav"
            rows.append(["r", src, blobs[src]["sha"], blobs[src]["size"], f"{folder.lower()}/{name}.wav"])
            lines.append(f"<region> sample={folder.lower()}/{name}.wav pitch_keycenter={k} lokey={lo} hikey={hi}")
        lines.append("<group> trigger=release ampeg_attack=0.005 ampeg_release=0.15 amp_veltrack=0")
        for name, k, lo, hi in zones(names):
            rel = f"{DIR}Releases/{folder}/Hohner-Super64_{stem}rel_{name}.wav"
            rows.append(["r", rel, blobs[rel]["sha"], blobs[rel]["size"], f"{folder.lower()}/release_{name}.wav"])
            lines.append(f"<region> sample={folder.lower()}/release_{name}.wav pitch_keycenter={k} lokey={lo} hikey={hi}")
        (out / sfz).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    fj = PACKS / "files.json"
    data = json.loads(fj.read_text(encoding="utf-8"))
    data["vcsl-harmonica"] = {"bases": {"r": BASE}, "files": rows}
    fj.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8", newline="\n")
    print(f"{len(rows)} files, {sum(r[3] for r in rows) / 1e6:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1])
