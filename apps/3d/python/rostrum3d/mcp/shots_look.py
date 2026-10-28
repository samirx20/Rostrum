"""look_shots: one contact sheet for several shots of a document, a row per shot (the edit's view of the whole piece)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools, sheet
from rostrum_core.mcp.files import look_path

from rostrum3d.compile import shot_info

from . import draw, shot_faults
from .look import _settings
from .shot import COUNT, ITEM_SHOT, LOOK, WIDTH, count_of, look_renderer, seconds, size_of, width_of

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
    "shots": {"type": "array", "items": {"type": "string"}, "minItems": 1, "description": "Shot ids or names, one row each in this order. Default: every shot."},
    "item": ITEM_SHOT["item"],
    **COUNT,
    **WIDTH,
    "quality": LOOK["quality"], "renderer": LOOK["renderer"]}})
def look_shots(ctx, args):
    """One row per shot (`shots`): compare a cut or a sequence."""
    doc = ctx.document(args.get("item"))
    ids = chosen(ctx, doc, args.get("shots"))
    infos = [dict(shot_info(doc.data, i)) for i in ids]
    names = {s["id"]: s.get("name") or s["id"] for s in doc.data["shots"]}
    for i in infos:
        if not i.get("camera"):
            raise RostrumError(codes.NOT_FOUND, ctx.tool, f'shot "{i["id"]}"', "has no camera, so there is nothing to look through",
                               hint="Add a camera item and set it as the shot's camera.")
    asked = count_of(ctx, args, 4, 1, 8)
    count = min([asked] + [len(frames_of(i, asked)) for i in infos])
    renderer, tile_w, engine = look_renderer(args, doc, infos), width_of(ctx, args, 320, 640), draw.engine_of(ctx)
    dest = look_path(f'{doc.item_id or "doc"}_shots_{renderer}', project=doc.folder)

    def job_fn(job):
        done, rows, per, found = 0, [], {}, []
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
                found += shot_faults.check(doc.data, info, frames, {f: Path(tmp) / f'{info["id"]}_f{f}.png' for f in frames}, ctx.app.folder)
                row = Path(tmp) / f'row_{info["id"]}.png'
                sheet.contact_sheet(tiles, tile_w, len(tiles), row)
                rows.append(row)
                per[info["id"]] = {"name": names[info["id"]], "frames": frames, "times": [round(seconds(info, f), 4) for f in frames], "camera": info["camera"]}
            sw, sh = stack(rows, dest)
        said = "; ".join(f'{names[i]} ({len(per[i]["frames"])} frames, {per[i]["times"][0]:g}–{per[i]["times"][-1]:g} s)' for i in ids)
        return Reply(f"Contact sheet of {len(ids)} shots, one row each, top to bottom: {said}. {renderer}, {sw}×{sh}.",
                     {"shots": per, "rows": ids, "width": sw, "height": sh, "renderer": renderer}, [dest], [dest], engine.take_notices(),
                     faults=list({x["id"]: x for x in reversed(found)}.values())[::-1])        # one per id (a shot's faults name the shot)

    return ctx.long(f"look_shots {', '.join(ids)}", job_fn)
