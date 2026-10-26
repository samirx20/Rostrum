"""Make the jazz kit's General MIDI map and its file list from Karoryfer Swirly Drums (CC0, a brushed kit).

    python devtools/swirly_kit.py <tree.json>

`tree.json` is GitHub's recursive tree of sfzinstruments/karoryfer.swirly-drums at COMMIT
(https://api.github.com/repos/sfzinstruments/karoryfer.swirly-drums/git/trees/<COMMIT>?recursive=1). Only the dry
close-mic samples are used (the pack's own "wet" and "wetter" room copies are left out: a space is the mixer's job).
The pack's programs steer everything with CC knobs and macros; this writes one flat SFZ on GM keys, the shape of the
studio kit: a group per drum, velocity layers spread evenly, the four round robins in turn. Writes
`library_data/packs/sfz/swirly-kit/swirly-kit.sfz` and the pack's entry in `library_data/packs/files.json`.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

COMMIT = "c40dafe0011cb2e54c0c220ff0fa308a11fc60f5"
BASE = f"https://raw.githubusercontent.com/sfzinstruments/karoryfer.swirly-drums/{COMMIT}/"
PACKS = Path(__file__).resolve().parents[1] / "rostrum_sound" / "library_data" / "packs"
# key(s), sample folder, the sample names' stem, the mics (name suffix, dB), the choke group / what chokes it. The dB set
# a starting balance measured on single hits at velocity 0.7 (the marching kick is recorded ~12 dB over the brushes, the
# stir ~25 dB under): a feathered kick under the ride and the brushes, as a jazz kit is played.
DRUMS = [
    ((36,), "marching_kick", "marching_kick", (("_reso", -9), ("_beater", -12)), ""),
    ((38,), "snare_main", "snare_hit", (("_top", 1), ("_btm", 3)), ""),
    ((40,), "snare_edge", "snare_edge", (("_top", 1), ("_btm", 3)), ""),
    ((60,), "snare_stir", "stir_dl1", (("", 10), ("_skin", 8)), ""),
    ((42,), "hat_closed", "hh_closed", (("", 0),), "group=1"),
    ((44,), "hat_foot", "hh_foot", (("", 0),), "group=1"),
    ((46,), "hat_open", "hh_open", (("", 0),), "group=2 off_by=1"),
    ((49,), "crash", "crash", (("", 3),), ""),
    ((51,), "ride", "ride", (("", 5),), ""),
    ((55,), "splash", "splash", (("", 3),), ""),
    ((41, 43), "tom_floor", "tom_floor", (("", 4),), ""),
    ((45,), "tom_xmed", "tom_xmed", (("", 4),), ""),
    ((47, 48), "tom_mhi", "tom_mhi", (("", 4),), ""),
    ((50,), "tom_vhi", "tom_vhi", (("", 6),), ""),
]
HEAD = ("// Rostrum jazz kit: Karoryfer Swirly Drums (CC0), a brushed kit, dry close mics, on General MIDI keys;\n"
        "// the brush stir on key 60 (\"stir\"). Made by apps/sound/python/devtools/swirly_kit.py.\n")


def main(tree_path: str) -> None:
    blobs = {e["path"]: e for e in json.loads(Path(tree_path).read_text(encoding="utf-8"))["tree"] if e["type"] == "blob"}
    lines, files = [HEAD], []
    for keys, folder, stem, mics, choke in DRUMS:
        layers = defaultdict(lambda: defaultdict(dict))      # velocity layer -> round robin -> mic suffix -> path
        mic = "|".join(re.escape(m) for m, _ in mics if m)
        pat = re.compile(rf"^{re.escape(stem)}(?:_vl(\d+))?({mic})?_rr(\d+)({mic})?\.wav$")     # the stir names its mic first
        for path in blobs:
            parts = path.split("/")
            if len(parts) == 3 and parts[0] == "Samples" and parts[1] == folder and (m := pat.match(parts[2])):
                layers[int(m[1] or 1)][int(m[3])][m[2] or m[4] or ""] = path
        if not layers:
            sys.exit(f"no samples for {folder}/{stem}")
        n = len(layers)
        for key in keys:
            lines.append(f"<group> lokey={key} hikey={key} pitch_keytrack=0 loop_mode=one_shot amp_veltrack=45 {choke}".rstrip())
            for i, vl in enumerate(sorted(layers), 1):
                lo, hi = round((i - 1) * 127 / n) + 1, round(i * 127 / n)
                rrs = layers[vl]
                for rr in sorted(rrs):
                    for suffix, db in mics:
                        path = rrs[rr].get(suffix)
                        if path is None:
                            sys.exit(f"missing mic {suffix!r} for {folder} vl{vl} rr{rr}")
                        lines.append(f"<region> sample=swirly/{path} lovel={lo} hivel={hi} seq_length={len(rrs)} "
                                     f"seq_position={rr} volume={db}")
                        files.append(path)
    out = PACKS / "sfz" / "swirly-kit" / "swirly-kit.sfz"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    rows = [["swirly", p, blobs[p]["sha"], blobs[p]["size"]] for p in dict.fromkeys(files)]
    fj = PACKS / "files.json"
    data = json.loads(fj.read_text(encoding="utf-8"))
    data["swirly-kit"] = {"bases": {"swirly": BASE}, "prefix_base": True, "files": rows}
    fj.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8", newline="\n")
    print(f"{len(rows)} files, {sum(r[3] for r in rows) / 1e6:.1f} MB -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
