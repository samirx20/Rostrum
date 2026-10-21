"""Rebuild the jug's texture set from the stroke scripts.

  uv run --with numpy --with pillow --with scipy python -I build.py [--scripts] [--check DIR] [--view OUT.png]

1. (--scripts) replay the stroke scripts 01_*.py, 02_*.py ... into a fresh jug.paint.json.
   Without it the saved jug.paint.json (which replays its own stroke record) is used.
2. Project every paint layer (all but `background`) through the shot camera onto Hem's jug.png,
   in layer order, Jug and JugHandle only -> textures/jug.png. Fails if a layer changes nothing.
3. textures/jug_height.png from the new paint (see height() below), textures/jug_rough.png.
4. (--view) a lit model view of the result, zoomed on the jug with the frame-pixel grid.
"""
import argparse, glob, os, shutil, subprocess, sys
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.normpath(os.path.join(HERE, "..", "model"))
KIT = os.path.normpath(os.path.join(HERE, "..", "kit"))
HEM = os.path.normpath(os.path.join(HERE, "..", "..", "3d-painterly", "paint", "textures"))
OUT = os.path.join(HERE, "textures")
DOC = os.path.join(HERE, "jug.paint.json")


def run(args):
    print(">", " ".join(os.path.basename(a) if os.sep in a else a for a in args), flush=True)
    r = subprocess.run([sys.executable, "-I"] + args, cwd=MODEL)
    if r.returncode:
        raise SystemExit(f"step failed (exit {r.returncode}): {' '.join(args)}")


def replay_scripts():
    sys.path.insert(0, KIT); sys.path.insert(0, HERE)
    from doc import Doc
    doc = Doc.new(1920, 1080)
    for s in sorted(glob.glob(os.path.join(HERE, "[0-9][0-9]_*.py"))):
        print("script", os.path.basename(s))
        exec(compile(open(s, encoding="utf-8").read(), s, "exec"), {"doc": doc, "__name__": "__script__"})
    doc.save(DOC)


def height(albedo, radius=2.0, gain=1.0, soften=1.0):
    """Gentle paint relief: only the brush-scale edges (high-pass at `radius` texels), at two-thirds
    of Hem's gain and a third of its radius, then softened, so strokes catch a little light without the plaster grain that the
    wide high-pass (radius 6, gain 1.5) gave. Enamel is glazed: a thin, smooth relief is right."""
    im = Image.open(albedo).convert("L")
    a = np.asarray(im, np.float32) / 255
    b = np.asarray(im.filter(ImageFilter.GaussianBlur(radius)), np.float32) / 255
    h = Image.fromarray(np.uint8(np.clip(0.5 + gain * (a - b), 0, 1) * 255 + 0.5))
    return h.filter(ImageFilter.GaussianBlur(soften))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scripts", action="store_true"); ap.add_argument("--check"); ap.add_argument("--view")
    a = ap.parse_args()
    if a.scripts:
        replay_scripts()
    sys.path.insert(0, KIT)
    from doc import Doc
    layers = [l["name"] for l in Doc.open(DOC).layers() if l["name"] != "background"]
    os.makedirs(OUT, exist_ok=True)
    jug = os.path.join(OUT, "jug.png")
    src = os.path.join(HEM, "jug.png")
    for i, name in enumerate(layers):
        args = ["project.py", "Jug", "--doc", DOC, "--layer", name, "--object", "Jug", "--object", "JugHandle"]
        run(args + ["--tex", src, "--out", jug])
        src = jug
        if a.check:
            # project.py's --check compares against the texture in paint/textures, not --tex, so a later
            # layer's check would count the earlier layers' changes as misses. Check each layer alone.
            d = os.path.join(a.check, name)
            run(args + ["--out", os.path.join(d, "alone.png"), "--check", d])
    height(jug).save(os.path.join(OUT, "jug_height.png"))
    shutil.copyfile(os.path.join(HEM, "jug_rough.png"), os.path.join(OUT, "jug_rough.png"))
    print("wrote", jug, os.path.join(OUT, "jug_height.png"), os.path.join(OUT, "jug_rough.png"))
    if a.view:
        run(["view.py", "--mode", "lit", "--tex", f"Jug={jug}", "--zoom", "180", "0", "660", "720",
             "--grid", "50", "--out", a.view])


if __name__ == "__main__":
    main()
