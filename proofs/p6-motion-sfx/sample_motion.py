"""Samples a 2D composition's motion as data for the Sound app: per top-level layer its x, y, scale and opacity at
`rate` samples a second, from the document's keys through Rostrum2D's own evaluator (read-only; nothing rendered).

    python sample_motion.py <2D doc json> <out json> [rate]

Stands in for a `samples` answer of Rostrum2D's look_motion (asked of the 2D app in the P6 report).
"""
import json
import sys

from rostrum2d.evaluate import value_at

PROPS = ("x", "y", "scale", "opacity")


def sample(comp: dict, rate: float = 120.0) -> dict:
    n = int(round(comp["duration"] * rate)) + 1
    ts = [i / rate for i in range(n)]
    layers = {}
    for layer in comp["layers"]:
        lanes = {p: [round(float(value_at(layer, p, t)), 3) for t in ts] for p in PROPS}
        layers[layer["id"]] = {**lanes, "w": layer.get("w"), "h": layer.get("h")}
    return {"rate": rate, "fps": comp["fps"], "width": comp["width"], "height": comp["height"],
            "duration": comp["duration"], "layers": layers}


def main():
    doc = json.load(open(sys.argv[1], encoding="utf-8"))
    comp = doc["comps"][0]
    rate = float(sys.argv[3]) if len(sys.argv) > 3 else 120.0
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(sample(comp, rate), f)


if __name__ == "__main__":
    main()
