"""Build eval_set.json from the installed sound library (the catalogue read by proofs/sound/rsnd).

  .venv\\Scripts\\python.exe proofs\\sound-sfx\\match\\make_eval_set.py      (from the worktree root)

Paths are written absolute (they live under ~/.rostrum/assets/sounds/, outside the repo).
True labels come from the catalogue names below, which a person checked by name only; a take that
the eval keeps getting "wrong" may be mislabelled in the catalogue, so listen before blaming the model.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "sound"))
from rsnd.library import Library  # noqa: E402

LABELS = {
    "metal-impact": "a small metal object hitting metal",
    "wood-impact": "a knock on wood",
    "glass-clink": "glass clinking against glass",
    "cloth": "cloth rustling and fabric movement",
    "whoosh": "a fast whoosh through the air",
    "door": "a door opening or closing",
    "footsteps": "footsteps",
    "paper": "paper rustling, crumpling or tearing",
    "pour": "water pouring into a glass",
    "zipper": "a zipper being pulled",
}

# label -> [(catalogue name, take indexes)]
PICK = {
    "metal-impact": [("impact.metal-light", [0, 2]), ("impact.metal-medium", [0, 3]), ("impact.metal-heavy", [1]), ("impact.tin-medium", [0])],
    "wood-impact": [("impact.wood-light", [0, 2]), ("impact.wood-medium", [1]), ("impact.wood-heavy", [0]), ("impact.plank-medium", [0, 3])],
    "glass-clink": [("glass.bottle-clink", [0, 5]), ("glass.toast", [0, 7]), ("impact.glass-light", [1]), ("liquid.ice-clink", [0])],
    "cloth": [("cloth.blanket", [0, 2, 4]), ("whoosh.synthetic-coat-rubbed", [0]), ("foley.shoulder-grab", [0])],
    "whoosh": [("whoosh.basic", [0, 10, 20]), ("whoosh.fast", [0]), ("whoosh.sword-through-the-air", [0]), ("whoosh.slow", [1])],
    "door": [("tech.creaking-door", [0]), ("tech.door-open", [0, 5, 10]), ("tech.door-close", [0, 2])],
    "footsteps": [("footstep.wood", [0]), ("footstep.concrete", [1]), ("footstep.heels", [0]), ("footstep.hard", [0]), ("footstep.wood-floor", [0])],
    "paper": [("paper.crumple", [0]), ("paper.page-turn", [0]), ("paper.tear", [0]), ("paper.newspaper", [0, 9])],
    "pour": [("liquid.pour-water-glass", [0, 1]), ("liquid.pour-wine", [0]), ("liquid.pour-water-mug", [0])],
    "zipper": [("cloth.zipper", [0, 1, 2])],
}


def build(lib=None):
    lib = lib or Library()
    items = []
    for label, picks in PICK.items():
        for name, idx in picks:
            for n in idx:
                t = lib.take(name, n)  # raises if the pack isn't installed
                items.append({"name": f"{name}#{n}", "path": str(Path(t["path"]).resolve()),
                              "offset": t["offset"], "length": t["length"], "true_label": label})
    return {"labels": LABELS, "items": items}


if __name__ == "__main__":
    es = build()
    out = HERE / "eval_set.json"
    out.write_text(json.dumps(es, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(es['items'])} takes, {len(es['labels'])} labels -> {out}")
