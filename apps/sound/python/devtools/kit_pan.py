"""Places the mono close-mic drums of the studio and jazz kits across the stereo field, as a kit is heard from the
audience (sound-gaps 2026-10-28: every close mic sat dead centre, so a lo-fi mix with the studio kit measured an L/R
correlation of 0.98, near mono). Kick and snare stay centred; hats left, ride right, toms from high (left) to floor
(right), crashes either side. The stereo overhead and room mics (`/oh/`) already carry the kit's real image and are
left alone. Writes `pan=` on each close-mic region of the kit's SFZ; running it again gives the same file.

    python devtools/kit_pan.py
"""
from __future__ import annotations

import re
from pathlib import Path

SFZ = Path(__file__).resolve().parents[1] / "rostrum_sound" / "library_data" / "packs" / "sfz"
KITS = ["studio-kit/studio-kit.sfz", "swirly-kit/swirly-kit.sfz"]
# General MIDI key -> pan (-100 left … 100 right), audience view.
PAN = {42: -35, 44: -35, 46: -35,            # hi-hat closed / foot / open
       51: 35, 53: 35, 59: 35,               # ride, bell
       49: -45, 57: 45, 55: -50,             # crash 1 / 2, splash
       50: -25, 48: -15, 47: 0, 45: 15,      # toms high to low
       43: 35, 41: 40,                       # floor toms
       39: 10, 70: -20, 82: 25, 60: 0}       # clap, maracas, shaker, brush stir
OVERHEAD = "/oh/"


def pan_kit(text: str) -> str:
    key, out = None, []
    for line in text.splitlines():
        m = re.match(r"<group>.*\blokey=(\d+)", line)
        if m:
            key = int(m.group(1))
        elif line.startswith("<region>") and key in PAN and OVERHEAD not in line:
            line = re.sub(r" pan=-?\d+", "", line)
            if PAN[key]:
                line += f" pan={PAN[key]}"
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def main() -> None:
    for rel in KITS:
        p = SFZ / rel
        p.write_text(pan_kit(p.read_text(encoding="utf-8")), encoding="utf-8")
        print(p)


if __name__ == "__main__":
    main()
