# Materials turntable (H22): the product-material controls side by side under strip lights, through the real render
# path (the render_still / render_video tools, as an agent calls them). Through the lock:
#   heavy.ps1 run "<team>: materials still" gpu <worktree>\.venv\Scripts\python.exe -I apps\3d\tools\materials_turntable.py still
#   heavy.ps1 run "<team>: materials video" gpu <worktree>\.venv\Scripts\python.exe -I apps\3d\tools\materials_turntable.py video
# Builds a scratch project (SCRATCH): a 3D document with a row of samples (spun brushed metal, clear-coated paint, a
# sheen fabric ring, frosted glass in front of a small ball, a screen) and a 2D item "screen2d" whose render plays on
# the screen. The 2D render is a stand-in PNG sequence (each frame shows its own number and a sweeping bar, so a
# frame of the video can be checked against the 2D frame it should show), written as a real project render
# (begin_render / finish_render, manifest like Rostrum2D's PNG export). Results: OUT (materials.png, materials.mp4).
import shutil, sys, time
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
from rostrum_core import Document, Who, project               # noqa: E402
from rostrum_core.mcp import Runtime                          # noqa: E402
from rostrum3d import KIND, run_source                        # noqa: E402
from rostrum3d.mcp.server import app_tools, make_app          # noqa: E402

SCRATCH = Path(r"C:\Users\Sam\.rostrum\waves\scratch\hem-h22-materials\project")
OUT = Path(r"C:\Users\Sam\.rostrum\waves\results\stage2\h22")
ITEM, SCREEN, FPS, SECONDS = "materials", "screen2d", 24, 4
STILL = {"width": 1600, "samples": 256, "at": 1.0}
VIDEO = {"width": 1280, "samples": 64}

SCENE = f'''
brushed = material("m_brushed", baseColor="#c9ccd1", metallic=1, roughness=0.32, anisotropy=0.85, brushDirection="around y")
paint = material("m_paint", baseColor="#8c0f14", roughness=0.45, coat=1, coatRoughness=0.03, coatTint="#ffd9d0", coatIor=1.6)
fabric = material("m_fabric", baseColor="#24325a", roughness=0.9, sheen=1, sheenRoughness=0.35, sheenTint="#c8d4ff")
frosted = material("m_frosted", baseColor="#ffffff", transmission=1, roughness=0.3, ior=1.5)
orange = material("m_orange", baseColor="#e8701a", roughness=0.4)
screen = material("m_screen", baseColor="#050505", roughness=0.15, emissionStrength=1.0, emissionRender="{SCREEN}")
floor = material("m_floor", baseColor="#1c1d20", roughness=0.35)

mesh("floor", shape="plane", width=8, depth=4, material=floor)
spin = {{0: 0, {SECONDS}: 180}}
mesh("disc", shape="cylinder", radius=0.22, height=0.03, bevel=0.004, segments=96, x=-1.1, y=0.3, rx=70,
     material=brushed).key("ry", spin, ease="linear")
mesh("blob", shape="box", width=0.36, height=0.36, depth=0.36, bevel=0.09, segments=12, x=-0.55, y=0.18,
     material=paint).key("ry", spin, ease="linear")
mesh("ring", shape="torus", radius=0.16, tube=0.07, segments=64, x=0, y=0.3, rx=60, material=fabric).key("ry", spin, ease="linear")
mesh("glass", shape="box", width=0.34, height=0.44, depth=0.06, bevel=0.01, x=0.55, y=0.22, material=frosted)
mesh("behind", shape="sphere", radius=0.07, x=0.55, y=0.2, z=-0.22, material=orange)
bezel = material("m_bezel", baseColor="#0b0b0c", roughness=0.25)
mesh("device", shape="box", width=0.5, height=0.32, depth=0.02, bevel=0.004, x=1.1, y=0.25, material=bezel)
mesh("screen", shape="plane", width=0.47, depth=0.29, x=1.1, y=0.25, z=0.0105, rx=90, material=screen)

light("left", kind="strip", length=1.6, width=0.18, intensity=30, x=-1.8, y=1.2, z=1.0).aim((-0.3, 0.25, 0))
light("right", kind="strip", length=1.6, width=0.18, intensity=24, x=1.8, y=1.0, z=0.8).aim((0.3, 0.25, 0))
light("top", kind="rect", width=2.5, height=0.8, intensity=6, y=2.2, z=0.3).aim((0, 0, 0))
light("sky", kind="dome", color="#8a96a8", intensity=0.12)
cam = camera("cam", focalLength=40, y=0.75, z=3.3).aim((0, 0.25, 0))
shot("turn", camera=cam, fps={FPS}, start=0, end={SECONDS}, width=1600, height=900)
'''


def screen_render(folder: Path, w=480, h=300):
    """A stand-in 2D render of SCREEN: one PNG per frame, numbered like Rostrum2D's PNG export (first = 1001)."""
    from PIL import Image, ImageDraw, ImageFont
    part = project.begin_render(folder, SCREEN)
    count, font = FPS * SECONDS, ImageFont.load_default(size=72)
    for i in range(count):
        img = Image.new("RGB", (w, h))
        d = ImageDraw.Draw(img)
        for y in range(h):                                     # a vertical gradient that warms over time
            t = y / h
            d.line([(0, y), (w, y)], fill=(int(20 + 60 * t + 120 * i / count), int(40 + 80 * (1 - t)), int(140 + 90 * t)))
        x = int((w - 40) * i / max(1, count - 1))
        d.rectangle([x, h - 46, x + 40, h - 16], fill=(255, 255, 255))
        d.text((24, 40), f"2D {1001 + i}", fill=(255, 255, 255), font=font)
        img.save(part / f"{SCREEN}_main.{1001 + i}.png")
    manifest = {"item": SCREEN, "version": int(part.name[1:].split(".")[0]), "kind": "pictures", "format": "png",
                "made_by": "tool:materials_turntable (stand-in for a Rostrum2D export)",
                "made_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": {"document": SCREEN, "comp": "main"},
                "engine": "stand-in", "frames": {"first": 1001, "last": 1000 + count, "fps": f"{FPS}/1", "start": 0.0, "end": float(SECONDS)},
                "size": [w, h], "files": sorted(p.name for p in part.iterdir()), "colour": {"space": "Rec.709 (bt709, display-referred)"},
                "checks": {"frame_count": "ok"}}
    return project.finish_render(part, manifest)


def build() -> Document:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)                                 # our own scratch project, rebuilt every run
    SCRATCH.mkdir(parents=True)
    (SCRATCH / "project.json").write_text('{"items": [{"id": "%s", "kind": "2d", "name": "Screen picture"}]}' % SCREEN,
                                          encoding="utf-8")
    screen_render(SCRATCH)
    doc = Document.new(KIND, str(SCRATCH), ITEM)
    doc.run_script("materials.py", run_source(SCENE, "materials.py"))
    doc.save()
    return doc


def run(tool: str, args: dict) -> dict:
    doc = build()
    app = make_app(str(SCRATCH), documents={ITEM: doc})
    rt, who = Runtime(app, app_tools()), Who.agent("materials_turntable")
    try:
        reply, _ = rt.call(tool, {"item": ITEM, "shot": "turn", "quality": "final", **args}, who)
        while reply["ok"] and reply["data"].get("status") not in (None, "done"):
            reply, _ = rt.call("inspect_job", {"job_id": reply["data"]["job_id"], "wait_s": 25}, who)
            print(reply["summary"], flush=True)
        if not reply["ok"]:
            raise SystemExit(f"{tool} failed: {reply['summary']}")
        return reply
    finally:
        app.state.engine.close()


def publish(reply: dict, ext: str, name: str) -> Path:
    src = next((Path(f) for f in reply["files"] if f.lower().endswith(ext)), None)
    if src is None or not src.is_file():
        raise SystemExit(f"no {ext} among the render's files: {reply['files']}")
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / name
    shutil.copyfile(src, dest)
    return dest


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "still":
        print(publish(run("render_still", {**STILL, "formats": ["png"]}), ".png", "materials.png"))
    elif what == "video":
        print(publish(run("render_video", VIDEO), ".mp4", "materials.mp4"))
    else:
        raise SystemExit("usage: materials_turntable.py still|video")
