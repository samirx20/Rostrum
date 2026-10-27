"""look_shots: one contact sheet for several shots of a document, a row per shot (the edit's view of the whole piece)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools, sheet
from rostrum_core.mcp.files import look_path

from rostrum3d.compile import shot_info

from . import draw
from .look import _settings
from .shot import LOOK, renderer_of, seconds, size_of

tools = Tools()


def chosen(ctx, doc, wanted) -> list[str]:
    """Shot ids for the ids or names asked (default: every shot, in the document's order). Unknown → fail naming the known ones."""
    shots = doc.data.get("shots", [])
    if not shots:
        raise RostrumError(codes.NOT_FOUND, ctx.tool, "shot", "the document has no shot yet", hint="Add one with the shot() script call.")
    known = [f'{s["id"]} ("{s.get("name") or s["id"]}")' for s in shots]
    out = []
    for w in wanted or [s["id"] for s in shots]:
        hit = next((s for s in shots if w == s["id"]), None) or next((s for s in shots if str(s.get("name", "")).lower() == str(w).lower()), None)
        if hit is None:
            raise RostrumError.not_found(ctx.tool, "shot", w, known, "the shots of this document (id or name)")
        if hit["id"] not in out:
            out.append(hit["id"])
    return out


def frames_of(info: dict, count: int) -> list[int]:
    """`count` frames spread evenly from the shot's first to its last, without repeats."""
    a, b = info["start"], info["end"]
    return sorted({round(a + (b - a) * i / (count - 1)) for i in range(count)}) if count > 1 else [a]


def stack(rows: list[Path], dest: Path) -> tuple[int, int]:
    """The row pictures one under the other, left-aligned on the sheet's background; written whole to `dest`."""
    pics = [Image.open(r).convert("RGB") for r in rows]
    big = Image.new("RGB", (max(p.width for p in pics), sum(p.height for p in pics)), sheet.BACK)
    y = 0
    for p in pics:
        big.paste(p, (0, y))
        y += p.height
    sheet._save_whole(big, dest)
    return big.size


@tools.tool("look_shots", {"properties": {
    "shots": {"type": "array", "items": {"type": "string"}, "minItems": 1, "description": "Shot ids or names (as the Shots list shows them), in the order of the rows. Default: every shot of the document."},
    "item": {"type": "string", "description": "The document's project item id. Optional when only one document is open."},
    "count": {"type": "integer", "minimum": 1, "maximum": 8, "default": 4, "description": "Frames in each row, evenly spaced from the shot's first to last frame (a shot with fewer frames gives every row that many)."},
    "tile_width": {"type": "integer", "minimum": 64, "maximum": 640, "default": 320, "description": "Width of each tile in px; a tile's height follows its shot's own shape."},
    "quality": LOOK["quality"], "renderer": LOOK["renderer"]}})
def look_shots(ctx, args):
    """One contact sheet for several shots, ONE ROW PER SHOT: `count` frames spread over that shot, each tile labelled with the shot's
    name, the frame and its time. Each shot is drawn through its own camera by the same render path as export (Storm for quality fast,
    Cycles for final; renderer picks by name). Use it to compare shots side by side, check a cut's two ends or a whole sequence's
    framing, before look_frame on one of them. An unknown shot fails, listing the document's shots."""
    doc = ctx.document(args.get("item"))
    ids = chosen(ctx, doc, args.get("shots"))
    infos = [dict(shot_info(doc.data, i)) for i in ids]
    names = {s["id"]: s.get("name") or s["id"] for s in doc.data["shots"]}
    for i in infos:
        if not i.get("camera"):
            raise RostrumError(codes.NOT_FOUND, ctx.tool, f'shot "{i["id"]}"', "has no camera, so there is nothing to look through",
                               hint="Add a camera item and set it as the shot's camera.")
    count = min([args.get("count", 4)] + [len(frames_of(i, args.get("count", 4))) for i in infos])
    renderer, tile_w, engine = renderer_of(args), args.get("tile_width", 320), draw.engine_of(ctx)
    dest = look_path(f'{doc.item_id or "doc"}_shots_{renderer}', project=doc.folder)

    def job_fn(job):
        done, rows, per = 0, [], {}
        with tempfile.TemporaryDirectory(prefix="rostrum3d_shots_") as tmp:
            for info in infos:
                frames, scene = frames_of(info, count), draw.scene_of(doc, info["id"])
                w, h = size_of(info, {"width": tile_w})
                tiles = []
                for f in frames:
                    png = Path(tmp) / f'{info["id"]}_f{f}.png'
                    draw.render(ctx.tool, f'frame {f} of {info["id"]}', engine, scene, camera=info["camera"], renderer=renderer, frame=f,
                                width=w, height=h, png=str(png), **_settings(renderer))
                    tiles.append((png, f'{names[info["id"]]}  f{f}  {seconds(info, f):.2f} s'))
                    done += 1
                    job.progress(done, count * len(infos))
                row = Path(tmp) / f'row_{info["id"]}.png'
                sheet.contact_sheet(tiles, tile_w, len(tiles), row)
                rows.append(row)
                per[info["id"]] = {"name": names[info["id"]], "frames": frames, "times": [round(seconds(info, f), 4) for f in frames], "camera": info["camera"]}
            sw, sh = stack(rows, dest)
        said = "; ".join(f'{names[i]} ({len(per[i]["frames"])} frames, {per[i]["times"][0]:g}–{per[i]["times"][-1]:g} s)' for i in ids)
        return Reply(f"Contact sheet of {len(ids)} shots, one row each, top to bottom: {said}. {renderer}, {sw}×{sh}.",
                     {"shots": per, "rows": ids, "width": sw, "height": sh, "renderer": renderer}, [dest], [dest], engine.take_notices())

    return ctx.long(f"look_shots {', '.join(ids)}", job_fn)
