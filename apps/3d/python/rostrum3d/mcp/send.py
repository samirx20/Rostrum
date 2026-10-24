"""render_send_shot (SPEC §13.2 "send_shot"; a hand-off, so the `render` verb, CONVENTIONS § 1): a shot into a 2D scene as
a live-linked 3D render layer (rostrum3d/send.py). Always a job: when the shot has no render of the scene as it is now,
the job renders it first through render_video's own work (EXR frames kept), then makes the link."""
from __future__ import annotations

from pathlib import Path

from rostrum_core import project
from rostrum_core.mcp import Reply, Tools

from rostrum3d import send
from .render import QUALITY_ARG, SETTINGS, video_job
from .shot import ITEM_SHOT, doc_and_shot

tools = Tools()


def _words(out: dict, shot: str) -> str:
    l, r = out["link"], out["render"]
    did = "added as a new 3D render layer" if l["made"] else ("set to follow the newest render" if l["changed"] else "already linked, nothing to change")
    return (f'Sent {shot} to 2D scene "{l["scene"]}" ({l["item"]}/{l["comp"]}): layer {l["layer"]} {did}; it shows render v{r["version"]:03d} '
            f'(scene hash {r["scene_hash"]}), and 2D says "out of date" once the 3D scene changes.')


@tools.tool("render_send_shot", {"properties": {**ITEM_SHOT,
                                                 "target": {"enum": list(send.TARGETS), "default": "2d", "description": "2d = a 3D render layer in a 2D scene. editor: not built yet (fails)."},
                                                 "scene": {"type": "string", "description": "The 2D scene: \"<2D item>/<scene id>\" or a scene id. Default: the scene this shot was sent to before, else the project's only 2D scene."},
                                                 "quality": {**QUALITY_ARG, "default": "final"}, **{k: SETTINGS[k] for k in ("width", "samples")}}})
def render_send_shot(ctx, args):
    """Send a shot to 2D: its render of the scene as it is now becomes a 3D render layer in a 2D scene (one step in that 2D
    document's history, seen live by an open 2D window), linked by content: 2D marks it "out of date" when this 3D
    document changes, and a re-send (a new render) clears it. Sending again keeps the same layer and what a person did to it
    in 2D. With no current render the job renders the shot first (render_video with EXR frames; the shot's own render settings
    unless quality / width / samples are given). Always a job: ask with inspect_job. Returns the link (2D item, scene,
    layer) and the render used."""
    doc, info = doc_and_shot(ctx, args)
    folder, shot = ctx.app.folder, next(s for s in doc.data["shots"] if s["id"] == info["id"])
    try:                                            # target, folder and scene are checked here, loudly, before any render
        out = send.send_shot(folder, doc, info["id"], args.get("target", "2d"), args.get("scene"), ctx.who)
        return ctx.job(f"render_send_shot {info['id']}", lambda job: Reply(_words(out, info["id"]), out))
    except send.NeedsRender:
        pass
    scene = send.pick(folder, doc.item_id, info["id"], args.get("scene"))
    rargs = {k: args[k] for k in ("item", "quality", "width", "samples") if k in args}
    label, render_fn, key = video_job(ctx, {**rargs, "shot": info["id"], "exr": True})

    def job_fn(job):
        made = render_fn(job)
        link = send.link_2d(folder, doc.item_id, shot, scene, ctx.who)
        r = next(r for r in project.renders(folder, doc.item_id) if Path(r["path"]).name == Path(made.data["folder"]).name)
        out = {"link": link, "render": {"version": r["version"], "path": r["path"], "scene_hash": r["manifest"]["source"].get("scene_hash")}}
        return Reply(f'{made.summary} {_words(out, info["id"])}', {**out, "rendered": made.data}, made.files, warnings=made.warnings)

    return ctx.job(f"render_send_shot {info['id']} ({label})", job_fn, key=f"send|{key}|{scene['value']}")
