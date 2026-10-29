"""look_motion `path`: one part's path on the picture over a time range, through the shot camera or a `view` (look.VIEW):
per sample its place (0–1 picture units), on-screen speed, the travel and ranges, read from the document (no engine);
and, unless `picture: false`, one fast look frame at the middle time with the trail drawn on it."""
from __future__ import annotations

from PIL import Image, ImageDraw

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply
from rostrum_core.mcp.files import look_path

from .. import view_look
from ..motion_track import Camera, track_of
from . import draw, motion_sim
from .shot import check_frame, look_renderer

PATH = {
    "path": {"type": "string", "description": "Measure this part's path on the picture instead: an item id or a clay joint \"<clay>.<joint>\" (e.g. buddy.hand.L)."},
    "from_s": {"type": "number", "minimum": 0, "description": "path: seconds from the shot's start. Default 0."},
    "to_s": {"type": "number", "minimum": 0, "description": "path: seconds from the shot's start. Default the shot's end."},
    "step_s": {"type": "number", "exclusiveMinimum": 0, "description": "path: seconds between samples. Default one frame."},
    "picture": {"type": "boolean", "description": "path: a fast frame at the middle time with the trail drawn on it (default true)."},
}
LISTED = 12                     # samples written in the reply's text; all of them are in the data
TRAIL, DOT, EDGE = (255, 64, 160), (255, 230, 60), (20, 20, 20)


def _frames(ctx, info: dict, args: dict) -> list[int]:
    fps, s0 = info["fps"], info["start"]
    a = s0 + round(args.get("from_s", 0.0) * fps)
    b = info["end"] if "to_s" not in args else s0 + round(args["to_s"] * fps)
    check_frame(ctx, info, a), check_frame(ctx, info, b)
    if b <= a:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"from_s–to_s (frames {a}–{b})", "must run forward inside the shot")
    step = max(1, round(args.get("step_s", 1 / fps) * fps))
    return sorted({*range(a, b + 1, step), b})


def measure(ctx, doc, info: dict, args: dict):
    from .look import _add_camera, view_of
    frames = _frames(ctx, info, args)
    track, _ = track_of(doc, info, range(frames[0], frames[-1] + 1), ctx.app.folder, lambda: motion_sim.moves(doc.data, info, ctx.app.folder))
    try:
        at = view_look.part_point(track.fr, args["path"])
    except ValueError as e:
        raise RostrumError(codes.NOT_FOUND, ctx.tool, f'path "{args["path"]}"', str(e)) from None
    mid = frames[len(frames) // 2]
    w, h = info["width"], info["height"]
    view = view_of(ctx, doc, info, args["view"], mid) if args.get("view") else None
    if view:
        still = view_look.projector(view, w, h)
        cam_of = lambda f: still                                                      # noqa: E731
    else:
        cam_of = lambda f: track.cams.get(f) or Camera(track.fr, info["camera"], f, w, h)   # noqa: E731
    p = view_look.path(at, frames, cam_of, info["fps"], info["start"], w, h)
    seen = f"a view {view_look.words(view)} (placed at {(mid - info['start']) / info['fps']:.2f} s, held still)" if view else f'camera {info["camera"]}'
    rows = p["samples"]
    pick = rows if len(rows) <= LISTED else [rows[round(i * (len(rows) - 1) / (LISTED - 1))] for i in range(LISTED)]
    pts = "; ".join(f'{r["t"]:g} s ({r["x"]:.3f}, {r["y"]:.3f})' if r["x"] is not None else f'{r["t"]:g} s behind the camera' for r in pick)
    text = (f'Path of {args["path"]} through {seen}, {rows[0]["t"]:g}–{rows[-1]["t"]:g} s, {len(rows)} samples (x, y: 0–1 of the picture, '
            f'0, 0 top left): travels {p["travel"]:.3f} picture heights, peak {p["peak_speed"]:.2f} heights/s'
            + (f'; x {p["x"][0]:.3f}–{p["x"][1]:.3f}, y {p["y"][0]:.3f}–{p["y"][1]:.3f}' if p["x"] else "; never in front of the camera")
            + (f'; outside the picture at {len(p["outside"])} samples' if p["outside"] else "")
            + (f'; behind the camera at {len(p["behind"])}' if p["behind"] else "") + f'. Samples: {pts}.'
            + (f' ({len(rows) - LISTED} more in data.samples.)' if len(rows) > LISTED else "") + " Renderer: none (read from the document).")
    data = {"shot": info["id"], "part": args["path"], "camera": info["camera"] if not view else None, **p,
            **({"view": {k: [round(c, 4) for c in view[k]] if k in ("eye", "target") else round(view[k], 3) for k in view}} if view else {})}
    if args.get("picture") is False:
        return Reply(text, data)
    renderer, engine = look_renderer({}, doc, [info]), draw.engine_of(ctx)
    pw, ph = 960, max(1, round(960 * h / w))
    scene = draw.scene_of(doc, info["id"])
    camera = info["camera"]
    if view:
        scene = {**scene, "items": list(scene["items"])}               # the document's compiled scene stays as it was
        camera = _add_camera(ctx, scene, view_look.as_camera(view))
    dest = look_path(f'{doc.item_id or "doc"}_{info["id"]}_path_{args["path"].replace(".", "_")}', project=doc.folder)

    def job_fn(job):
        draw.render(ctx.tool, f"frame {mid} of {info['id']}", engine, scene, camera=camera, renderer=renderer, frame=mid, width=pw, height=ph, png=str(dest))
        _trail(dest, rows, mid)
        return Reply(text + f" Picture: frame {mid} with the trail drawn on it (dots every sample, the bigger dot is this frame).",
                     {**data, "picture": {"frame": mid, "width": pw, "height": ph}}, [dest], [dest], engine.take_notices())

    return ctx.long(f'look_motion path {args["path"]}', job_fn)


def _trail(png, rows: list[dict], mid: int):
    im = Image.open(png).convert("RGB")
    d, (w, h) = ImageDraw.Draw(im), im.size
    runs, run = [], []
    for r in rows:                                     # a gap where the part is behind the camera
        if r["x"] is None:
            runs, run = runs + [run], []
        else:
            run.append((r["x"] * w, r["y"] * h, r["frame"]))
    for run in [*runs, run]:
        if len(run) > 1:
            d.line([(x, y) for x, y, _ in run], fill=EDGE, width=4)     # a dark edge: it reads on a bright picture too
            d.line([(x, y) for x, y, _ in run], fill=TRAIL, width=2)
        for x, y, f in run:
            k = 5 if f == mid else 2
            d.ellipse((x - k, y - k, x + k, y + k), fill=DOT if f == mid else TRAIL, outline=EDGE)
    im.save(png)
