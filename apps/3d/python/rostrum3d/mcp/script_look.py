"""run_script `look` for 3D: after the merge, one contact sheet of the first shot through its camera (Storm, or Stylized for a
shot whose Quality is Stylized) and the shot's faults (shot_faults: too dark / blown out, a subject cut by the frame, floating
or sinking), the same reply. App.script_look calls `after_run`; the merge stands whatever happens to the look."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError
from rostrum_core.mcp import Reply, sheet
from rostrum_core.mcp.files import look_path
from rostrum3d.compile import shot_info

from . import draw, shot_faults
from .look import _settings
from .shot import look_renderer, seconds, size_of

SPREAD = 4            # look: true -> this many frames spread over the shot
TILE_W = 480


def frames_for(look, info: dict) -> tuple[list[int], list[str]]:
    """Shot frames for `look` (seconds from the shot's start, or true: SPREAD spread over it), and warnings for times past its end."""
    a, b = info["start"], info["end"]
    if look is True:
        return sorted({round(a + (b - a) * i / max(SPREAD - 1, 1)) for i in range(SPREAD)}), []
    past = [t for t in look if a + round(t * info["fps"]) > b]
    out = sorted({min(a + round(t * info["fps"]), b) for t in look if t not in past})
    return out or [a, b], ([f'look: {", ".join(f"{t:g}" for t in past)} s is past the end of the shot ({(b - a) / info["fps"]:g} s), left out'] if past else [])


def after_run(ctx, doc, look, reply: Reply) -> Reply:
    try:
        return _looked(ctx, doc, look, reply)
    except RostrumError as e:
        reply.summary += f"\nLook FAILED, no picture or faults: {e.line()} The script itself was merged; look_frame or look_sheet to look."
        reply.data["look"] = {"failed": e.line()}
        return reply


def _looked(ctx, doc, look, reply: Reply) -> Reply:
    shots = doc.data.get("shots", [])
    info = dict(shot_info(doc.data, shots[0]["id"])) if shots else None
    if not info or not info.get("camera"):
        reply.summary += "\nLook skipped: the scene has no shot with a camera yet (shot() and camera() in the script)."
        return reply
    frames, past = frames_for(look, info)
    reply.warnings += past
    renderer, engine = look_renderer({}, doc, [info]), draw.engine_of(ctx)
    w, h = size_of(info, {"width": TILE_W})
    scene = draw.scene_of(doc, info["id"])
    dest = look_path(f'{doc.item_id or "doc"}_{info["id"]}_script_{renderer}', project=doc.folder)
    with tempfile.TemporaryDirectory(prefix="rostrum3d_scriptlook_") as tmp:
        pngs = {}
        for f in frames:
            pngs[f] = Path(tmp) / f"f{f}.png"
            draw.render(ctx.tool, f"frame {f} of {info['id']}", engine, scene, camera=info["camera"], renderer=renderer, frame=f,
                        width=w, height=h, png=str(pngs[f]), **_settings(renderer))
        sw, sh = sheet.contact_sheet([(p, f"f{f}   {seconds(info, f):.2f} s") for f, p in pngs.items()], TILE_W, min(3, len(frames)), dest)
        found = shot_faults.check(doc.data, info, frames, pngs, ctx.app.folder)
    reply.summary += (f"\nLooked at {info['id']} through {info['camera']}: {len(frames)} frames, {frames[0]}–{frames[-1]} "
                      f"({seconds(info, frames[0]):.2f}–{seconds(info, frames[-1]):.2f} s), {renderer}, {sw}×{sh}.")
    reply.data["look"] = {"shot": info["id"], "frames": frames, "renderer": renderer, "width": sw, "height": sh}
    reply.files, reply.images, reply.faults = [*reply.files, dest], [*reply.images, dest], found
    reply.warnings += engine.take_notices()
    return reply
