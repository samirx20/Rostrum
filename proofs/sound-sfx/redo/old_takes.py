"""The takes the old pass (proofs/sound/sfx/door_pass.py) placed, each with the kind it stood in for,
so the sound-match model can score old and new against the same descriptions.

Run (main venv, from proofs/sound-sfx):  python -m redo.old_takes <out.json>"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sound"))
from rsnd import Library  # noqa: E402

USED = [  # (catalogue name, take numbers, the kind it was used for in the old pass)
    ("whoosh.cloth", range(6), "sleeve"), ("cloth.blanket", (1, 5), "sleeve"),
    ("impact.wood-light", (1, 3), "palm_pat"), ("impact.slap", (0,), "palm_pat"),
    ("impact.wood-heavy", (2,), "palm_pat"), ("impact.wood-medium", (1,), "palm_pat"),
    ("tech.creaking-door", (0,), "palm_slide"), ("impact.scrape", (1,), "palm_slide"),
    ("impact.metal-light", range(5), "ring_clink"), ("impact.scrape", (2,), "ring_clink"),
    ("impact.metal-heavy", (1,), "ring_clink"), ("impact.plate-heavy", (0,), "ring_clink"),
    ("impact.clamour", (3, 4), "padlock"), ("impact.tin-medium", range(5), "padlock"),
    ("ambience.room-tone-office", (0,), "room"),
]


def main():
    lib, out = Library(), []
    for name, ns, kind in USED:
        for n in ns:
            t = lib.take(name, n)
            out.append({"kind": kind, "path": str(t["path"]), "offset": t["offset"], "length": t["length"],
                        "label": f"{name} #{n}"})
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"old_takes": len(out)}))


if __name__ == "__main__":
    main()
