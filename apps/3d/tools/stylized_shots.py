# Brief 22 pictures: the stylized blocks through the real look path (look_frame, as an agent calls it), side by side.
# Through the lock:
#   heavy.ps1 run "<team>: 3d-22 shots" gpu C:\Users\Sam\.rostrum\venv\Scripts\python.exe -I apps\3d\tools\stylized_shots.py [out]
# Builds a scratch project (SCRATCH): a case with its lid on a plinth under a softbox and a dim sky. The case's material
# uses Light to colour + Lines, the lid Halftone; two balls wear the starting points "Painted (ramp)" and "Ink & flat".
# Writes into OUT: light-to-colour-quick-final-stylized.png (one shot, three looks), halftone.png, starts.png
# (each start in Final and Stylized) and the single frames.
import shutil, sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
from PIL import Image, ImageDraw, ImageFont                   # noqa: E402
from rostrum_core import Document, Who                        # noqa: E402
from rostrum_core.mcp import Runtime                          # noqa: E402
from rostrum3d import KIND, run_source                        # noqa: E402
from rostrum3d.mcp.server import app_tools, make_app          # noqa: E402

SCRATCH = Path(r"C:\Users\Sam\.rostrum\waves\scratch\sam-3d22-lead\shots")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-22")
ITEM = "stylized"

SCENE = '''
shell = material("shell", baseColor="#d9603b", roughness=0.45, lightToColor=True, litColor="#ffffff",
                 midColor="#c7b7c9", shadowColor="#5b4f7a", lines=True, linesWidth=2.0)
top = material("top", baseColor="#e8e2d4", roughness=0.4, halftone=True, halftoneSize=7, lines=True)
floor = material("floor", baseColor="#7d8088", roughness=0.8)
mesh("plinth", shape="box", width=1.2, height=0.02, depth=0.9, y=-0.01, z=-0.1, material=floor)
mesh("case", name="Case", shape="box", width=0.24, height=0.08, depth=0.16, bevel=0.01, segments=4, y=0.04, material=shell)
mesh("lid", name="Lid", shape="box", width=0.25, height=0.03, depth=0.17, bevel=0.006, segments=3, y=0.095, material=top)
painted = material("painted", start="painted (ramp)")
ink = material("ink", start="ink & flat")
mesh("ball_painted", shape="sphere", radius=0.05, segments=48, x=-0.22, y=0.05, z=0.12, material=painted)
mesh("ball_ink", shape="sphere", radius=0.05, segments=48, x=0.22, y=0.05, z=0.12, material=ink)
dots = material("dots", baseColor="#f2efe6", roughness=0.5, halftone=True, halftoneSize=6, halftoneColor="#23304a")
mesh("ball_dots", shape="sphere", radius=0.045, segments=48, x=0, y=0.045, z=0.2, material=dots)
light("key", kind="rect", width=0.6, height=0.4, intensity=25, x=-0.4, y=0.7, z=0.6).aim((0, 0.05, 0))
light("sky", kind="dome", color="#b8c4d6", intensity=0.3)
cam = camera("cam", focalLength=35, y=0.32, z=0.62).aim((0, 0.05, 0))
shot("hero", camera=cam, fps=24, start=0, end=1, width=1280, height=720)
'''


def build() -> Document:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)                                 # our own scratch project, rebuilt every run
    SCRATCH.mkdir(parents=True)
    (SCRATCH / "project.json").write_text('{"items": []}', encoding="utf-8")
    doc = Document.new(KIND, str(SCRATCH), ITEM)
    doc.run_script("scene.py", run_source(SCENE, "scene.py"))
    doc.save()
    return doc


def look(rt, who, **args) -> Path:
    reply, _ = rt.call("look_frame", {"item": ITEM, "shot": "hero", "width": 960, **args}, who)
    while reply["ok"] and reply["data"].get("status") not in (None, "done"):
        reply, _ = rt.call("inspect_job", {"job_id": reply["data"]["job_id"], "wait_s": 25}, who)
    if not reply["ok"]:
        raise SystemExit(f"look_frame {args} failed: {reply['summary']}")
    print(reply["summary"], flush=True)
    return next(Path(f) for f in reply["files"] if f.lower().endswith(".png"))


def side_by_side(name: str, tiles: list[tuple[Path, str]], crop=None) -> Path:
    imgs = [Image.open(p).convert("RGB") for p, _ in tiles]
    if crop:
        imgs = [im.crop(tuple(int(c * s) for c, s in zip(crop, (*im.size, *im.size)))) for im in imgs]
    h = min(im.height for im in imgs)
    imgs = [im.resize((round(im.width * h / im.height), h)) for im in imgs]
    out = Image.new("RGB", (sum(im.width for im in imgs) + 8 * (len(imgs) - 1), h + 40), (24, 24, 26))
    font, x = ImageFont.load_default(size=22), 0
    for im, (_, label) in zip(imgs, tiles):
        out.paste(im, (x, 40))
        ImageDraw.Draw(out).text((x + 10, 8), label, fill=(235, 235, 235), font=font)
        x += im.width + 8
    dest = OUT / name
    out.save(dest)
    print(dest)
    return dest


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    doc = build()
    app = make_app(str(SCRATCH), documents={ITEM: doc})
    rt, who = Runtime(app, app_tools()), Who.agent("stylized_shots")
    try:
        frames = {}
        for key, args in {"quick": {"quality": "fast"}, "final": {"quality": "final"},
                          "stylized": {"renderer": "stylized"}}.items():
            src = look(rt, who, **args)
            frames[key] = OUT / f"case-{key}.png"
            shutil.copyfile(src, frames[key])
        side_by_side("light-to-colour-quick-final-stylized.png",
                     [(frames["quick"], "Quick (Storm)"), (frames["final"], "Final (Cycles)"),
                      (frames["stylized"], "Stylized")])
        side_by_side("halftone.png", [(frames["stylized"], "Halftone on the front ball (Stylized), zoomed")],
                     crop=(0.35, 0.55, 0.65, 0.95))
        side_by_side("starts.png", [(frames["final"], "Final"), (frames["stylized"], "Stylized")],
                     crop=(0.15, 0.35, 0.85, 0.85))
    finally:
        app.state.engine.close()
