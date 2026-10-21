"""lipsync.apply: key a character's mouth layers to a voice clip (LIPSYNC.md § The operation). The phones come from
the shared cache (computed on the first call: a model run). It only adds keys: a mouth key that is already there,
at its time or under its id (a person may have moved or changed it), is left as it is."""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index

from ..kind import REGISTRY as R
from ..ops_keys import key_id, put_key
from . import visemes as V
from .phonemes import LANGUAGES
from .track import TIMING, track

WORDS = {"X": "rest", "A": "closed (M B P)", "B": "slightly open", "C": "open", "D": "wide open", "E": "rounded",
         "F": "puckered (OO W)", "G": "teeth on lip (F V)", "H": "tongue up (L)"}
SECONDS = dict(min=0, max=36000, unit="s")
PARAMS = [
    Param.text("source", label="Voice clip", required=True, help="A WAV file (a made take, or a recording)"),
    Param.number("at", label="Starts at", default=0.0, help="Where the clip starts in the composition", **SECONDS),
    Param.text("text", label="Words said", help="With the words, phones are aligned to them (English); without, "
                                                  "the model's own hearing is used (any language)"),
    Param.number("start", label="Clip from", default=0.0, help="Seconds into the file", importance="secondary",
                  **SECONDS),
    Param.number("end", label="Clip to", help="Seconds into the file (default: its end)", importance="secondary",
                 **SECONDS),
    Param.choice("language", list(LANGUAGES), label="Language of the words", default="english",
                 importance="secondary"),
    *(Param.id(f"shape{s}", kind="layer", label=f"Mouth {s}: {WORDS[s]}") for s in V.SHAPES),
    Param.number("leadFrames", label="Mouth leads by", default=TIMING["lead_frames"], min=0, max=6, unit="frames",
                 importance="secondary"),
    Param.number("minFrames", label="Shortest shape", default=TIMING["min_frames"], min=0, max=6, unit="frames",
                 importance="secondary"),
    Param.number("restGap", label="Rest after silence", default=TIMING["rest_gap"], min=0, max=5, unit="s",
                 importance="secondary"),
    Param.number("tail", label="Sound tail", default=TIMING["tail"], min=0, max=1, unit="s", importance="secondary"),
]


def _comp_of(ctx, id_) -> dict:
    idx = index(ctx.doc, ctx.kind.lists)
    while idx[id_].item["type"] != "comp":
        id_ = idx[id_].parent
    return idx[id_].item


def _inside(ctx, layer, target) -> bool:
    idx = index(ctx.doc, ctx.kind.lists)
    while layer in idx and idx[layer].parent:
        layer = idx[layer].parent
        if layer == target:
            return True
    return False


@R.operation("lipsync.apply", "Key mouth layers to a voice clip: one layer per mouth shape shows at a time (opacity "
             "keys, hold). Missing shapes show the nearest one given. Adds keys only; keys already there stay.",
             target=("rig", "group"), label="Lip sync", params=PARAMS)
def lipsync_apply(ctx, targets, args):
    shapes = {s: args[f"shape{s}"] for s in V.SHAPES if args.get(f"shape{s}")}
    if not shapes:
        ctx.fail(codes.BAD_ARGUMENT, "shapes", "none given", [f"shape{s}" for s in V.SHAPES],
                 hint="Give the mouth layer for at least one shape (X rest, A closed, D wide open …).")
    timing = {k: args[c] for k, c in (("lead_frames", "leadFrames"), ("min_frames", "minFrames"),
                                       ("rest_gap", "restGap"), ("tail", "tail")) if c in args}
    for t in targets:
        outside = [lay for lay in shapes.values() if not _inside(ctx, lay, t)]
        if outside:
            ctx.fail(codes.BAD_ARGUMENT, f"mouth layers {outside}", f"are not inside {t}")
        fps = _comp_of(ctx, t).get("fps", 30)
        job = track(args["source"], args.get("at", 0.0), fps, shapes, args.get("text"), args.get("start", 0.0),
                    args.get("end"), args.get("language", "english"), where=ctx.where, **timing)
        known = index(ctx.doc, ctx.kind.lists)
        for layer, ks in job["keys"].items():
            there = {round(k["t"], 4) for k in ctx.item(layer).get("keys", []) if k["prop"] == "opacity"}
            for at, v in ks.items():
                if key_id(layer, "opacity", at) not in known and round(at, 4) not in there:
                    put_key(ctx, layer, "opacity", at, {"v": v, "ease": "hold"})
