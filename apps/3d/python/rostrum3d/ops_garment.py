"""Garment operations (PR7): make a sewing pattern (`garment.make`), add, replace or remove one of its pieces
(`garment.piece`), sew or unpick two edges (`garment.sew`). Each is one operation, so one undo step; a pattern that can't
be made fails loudly, naming the piece or seam (garment.py). A pattern is a mesh (Shape "pattern"): every other setting
is mesh.set's, its cloth settings the Simulation group's.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from . import fields as F, garment
from .kind import REGISTRY as R
from .ops_items import PLACE, _holder, new_item

PIECES = Param.text("pieces", label="Pieces", help='JSON text: [{"name", "outline": [[x, y], …] metres, "at": [x, y, z], '
                    '"turn": degrees about up (180 faces back), "wrap": metres (0 flat)}, …]')
SEAMS = Param.text("seams", label="Seams", help='JSON text: [{"a": [piece, edge], "b": [piece, edge], "flip": false}, …]; '
                   "edge i runs from outline point i to the next")
NAME = Param.text("name", label="Piece", required=True, help="The piece's name, unique in the pattern")
EDGE = lambda side: [Param.text(f"{side}Piece", label=f"Piece {side.upper()}", required=True),  # noqa: E731
                     Param.number(f"{side}Edge", label=f"Edge {side.upper()}", min=0, max=10000, integer=True, required=True,
                                  help="Edge i runs from outline point i to the next, as the outline was written")]
_FIELDS = [p for p in F.unconditional("mesh") if p.name not in ("shape", "name", "pieces", "seams")]


def _write(ctx, id_: str, pieces: list, seams: list) -> None:
    """Check the whole pattern, then store it (loud: names the piece or seam)."""
    try:
        garment.check(pieces, seams)
    except garment.PatternError as e:
        ctx.fail(codes.BAD_ARGUMENT, f'pattern "{id_}"', str(e), hint="Guide: simulate › Garments from patterns")
    ctx.set(id_, "pieces", garment.text(pieces))
    ctx.set(id_, "seams", garment.text(seams))


def _pattern(ctx, id_: str) -> tuple[list, list]:
    item = ctx.item(id_)
    if item.get("shape") != "pattern":
        ctx.fail(codes.BAD_ARGUMENT, f'"{id_}"', f'is a {item.get("shape", "box")} mesh, not a sewing pattern',
                 hint="garment.make makes one")
    return garment.read(item.get("pieces") or "", "pieces"), garment.read(item.get("seams") or "", "seams")


@R.operation("garment.make", "Make a garment from a sewing pattern: flat pieces (outline, where it sits, which way it "
             "faces, how far it wraps) and the edges sewn together. It is cloth from the start: run the simulation and the "
             "seams pull together over Sewing time and it drapes on what Stays still under it.",
             label="Add sewing pattern", params=[*PLACE, PIECES, SEAMS, *_FIELDS])
def garment_make(ctx, targets, args):
    try:
        pieces, seams = garment.read(args.get("pieces") or "", "pieces"), garment.read(args.get("seams") or "", "seams")
    except garment.PatternError as e:
        ctx.fail(codes.BAD_ARGUMENT, "pattern", str(e))
    given = {k: v for k, v in args.items() if k in {p.name for p in _FIELDS}}
    item = new_item(ctx, "mesh", args, {"shape": "pattern", "simulate": "cloth", **given})
    parent, key = _holder(ctx, args.get("into"))
    ctx.insert(parent, key, item, args.get("index"))
    _write(ctx, item["id"], pieces, seams)
    return item


@R.operation("garment.piece", "Add a piece to a sewing pattern, replace the piece of that name, or remove it (its "
             "seams go with it).", target="mesh", label="Change pattern piece",
             params=[NAME, Param.points("outline", label="Outline", min=2, max=2, help="[[x, y], …] metres, flat"),
                     Param.list("at", "number", label="At", min=-1e5, max=1e5, min_items=3, max_items=3,
                                help="[x, y, z]: where the outline's origin sits, in the item's space"),
                     Param.number("turn", label="Turn", min=-360, max=360, unit="°", help="About up: 0 faces +z, 180 faces −z"),
                     Param.number("wrap", label="Wrap", min=0, max=100, unit="m",
                                  help="Radius of the upright cylinder behind it that it curves round (0 = flat)"),
                     Param.toggle("remove", label="Remove", help="Take the piece out")])
def garment_piece(ctx, targets, args):
    for t in targets:
        pieces, seams = _pattern(ctx, t)
        old = next((p for p in pieces if p.get("name") == args["name"]), None)
        if args.get("remove"):
            if old is None:
                ctx.fail(codes.BAD_ARGUMENT, f'piece "{args["name"]}"', f"is not in {t}",
                         [p.get("name") for p in pieces])
            pieces = [p for p in pieces if p is not old]
            seams = [s for s in seams if args["name"] not in (s["a"][0], s["b"][0])]
        else:
            piece = {k: args[k] for k in ("outline", "at", "turn", "wrap") if args.get(k) is not None}
            piece = {**(old or {}), "name": args["name"], **piece}
            if "outline" not in piece:
                ctx.fail(codes.BAD_ARGUMENT, f'piece "{args["name"]}"', f"is new in {t} and needs an outline")
            pieces = [piece if p is old else p for p in pieces] if old else [*pieces, piece]
        _write(ctx, t, pieces, seams)


@R.operation("garment.sew", "Sew two edges of a sewing pattern together (they pull closed when it simulates), or unpick "
             "them (remove). Which ends meet is picked by what is nearer at the start; flip swaps them.", target="mesh",
             label="Sew edges", params=[*EDGE("a"), *EDGE("b"),
                                        Param.toggle("flip", label="Flip", help="Join each end to the other edge's far end"),
                                        Param.toggle("remove", label="Unpick", help="Take this seam out")])
def garment_sew(ctx, targets, args):
    a, b = [args["aPiece"], int(args["aEdge"])], [args["bPiece"], int(args["bEdge"])]
    for t in targets:
        pieces, seams = _pattern(ctx, t)
        same = [s for s in seams if {tuple(s["a"]), tuple(s["b"])} == {tuple(a), tuple(b)}]
        if args.get("remove"):
            if not same:
                ctx.fail(codes.BAD_ARGUMENT, f"seam {a} – {b}", f"is not in {t}")
            seams = [s for s in seams if s not in same]
        else:
            seams = [s for s in seams if s not in same] + [{"a": a, "b": b, **({"flip": True} if args.get("flip") else {})}]
        _write(ctx, t, pieces, seams)
