"""H9 proof: import our own SVG / PDF / PSD and render each through the engine beside its source; export one test scene
in every format (each read back) and as Lottie. Results → C:\\Users\\Sam\\.rostrum\\waves\\results\\stage2\\2d-io\\.
Usage: python run_proof.py   (after make_sources.py; needs the engine build and, for the SVG source picture, Edge)
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw
from rostrum_core import Document, Who

from rostrum2d import KIND
from rostrum2d.engine import Engine
from rostrum2d.io.export import export
from rostrum2d.io.lottie import write_lottie
from rostrum2d.io.pdf import pdf_tree
from rostrum2d.io.psd import psd_tree
from rostrum2d.io.svg import svg_tree
from rostrum2d.io.tree import import_into
from rostrum2d.scene import describe

sys.path.insert(0, str(Path(__file__).parent))
from scene import SCENE  # noqa: E402

RES = Path(r"C:\Users\Sam\.rostrum\waves\results\stage2\2d-io")
SRC = RES / "sources"
WORK = Path(r"C:\Users\Sam\.rostrum\waves\scratch\hem-H9-lead\proof")
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
ME = Who.agent("h9-proof")


def svg_source_png(svg: Path, out: Path):
    """The SVG as a browser draws it (Edge headless), the reference for the eye."""
    html = WORK / "svg.html"
    html.write_text(f'<html><body style="margin:0"><img src="{svg.as_uri()}"></body></html>', encoding="utf-8")
    subprocess.run([str(EDGE), "--headless", "--disable-gpu", f"--screenshot={out}", "--window-size=800,600",
                    "--hide-scrollbars", html.as_uri()], check=True, capture_output=True, timeout=60)


def side_by_side(a: Path, b: Path, out: Path, labels=("source", "imported, drawn by Rostrum2D")):
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    ib = ib.resize(ia.size)
    pic = Image.new("RGB", (ia.width * 2 + 20, ia.height + 40), "#202020")
    pic.paste(ia, (0, 40))
    pic.paste(ib, (ia.width + 20, 40))
    d = ImageDraw.Draw(pic)
    d.text((10, 12), labels[0], fill="white")
    d.text((ia.width + 30, 12), labels[1], fill="white")
    pic.save(out)


def import_one(eng, tree, kind: str, fonts: set) -> dict:
    folder = WORK / f"import-{kind}"
    shutil.rmtree(folder, ignore_errors=True)
    doc = Document.new(KIND, folder=str(folder), item=kind)
    doc.apply([{"op": "comp.add", "args": {"id": "c", "width": round(tree["width"]), "height": round(tree["height"]),
                                           "duration": 1.0, "background": "#ffffff"}}], ME)
    report = import_into(doc, tree, "c", ME, fonts=fonts)
    eng.load(describe(doc.data))
    out = RES / f"import-{kind}-render.png"
    eng.still(0.0, out)
    layers = doc.data["comps"][0]["layers"]
    return {"report": report, "render": str(out),
            "layers": [(l["id"], l["type"], len(l.get("layers", []))) for l in layers]}


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    facts = {}
    with Engine() as eng:
        fonts = set(eng._request({"scene": SCENE})["fonts"])
        svg_source_png(SRC / "sample.svg", SRC / "sample.svg.png")
        for kind, tree in (("svg", svg_tree(SRC / "sample.svg")), ("pdf", pdf_tree(SRC / "sample.pdf")),
                           ("psd", psd_tree(SRC / "sample.psd"))):
            facts[f"import-{kind}"] = import_one(eng, tree, kind, fonts)
            side_by_side(SRC / f"sample.{kind}.png", RES / f"import-{kind}-render.png", RES / f"import-{kind}-vs-source.png")
        eng.load(SCENE)
        eng.still(1.2, RES / "export-scene-1.2s.png")
        outs = {"mp4": "export.mp4", "prores4444": "export-prores4444-alpha.mov", "webm": "export-vp9-alpha.webm",
                "gif": "export.gif", "png": "png8/frame_{frame}.png"}
        for fmt, name in outs.items():
            t0 = time.perf_counter()
            facts[f"export-{fmt}"] = {**export(eng, fmt, RES / name), "seconds": round(time.perf_counter() - t0, 1)}
        t0 = time.perf_counter()
        facts["export-png16"] = {**export(eng, "png", RES / "png16/frame_{frame}.png", depth=16, start=1.0, end=1.5),
                                 "seconds": round(time.perf_counter() - t0, 1)}
    facts["lottie-report"] = write_lottie(SCENE, RES / "export-lottie.json")
    (RES / "facts.json").write_text(json.dumps(facts, indent=1, default=str), encoding="utf-8")
    print(json.dumps(facts, indent=1, default=str))


if __name__ == "__main__":
    main()
