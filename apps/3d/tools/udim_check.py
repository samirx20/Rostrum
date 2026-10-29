# PR6 check: UDIM sets (pictures in tiles) in the Quick view and in Cycles. Through the lock:
#   heavy.ps1 run "<team>: udim check" gpu <venv python> apps\3d\tools\udim_check.py <out folder>
# A card 2 m wide whose surface runs over two tiles (u 0..2), from an OBJ whose .mtl names tile 1001 only
# (t.1001.png, red "1001"; t.1002.png beside it, blue "1002"). Left: the import with the file's own material; middle:
# a USD file (referenced as it is) whose texture is written t.<UDIM>.png; right: the OBJ wearing a Rostrum material
# whose picture is t.1001.png. Each must show red 1001 | blue 1002, in both renderers (udim-quick-vs-cycles.png):
# along the cards' middle row the coloured stretches go red, blue three times. Then a material naming a set with no
# tile must be refused, loudly.
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(WT / "apps" / "3d" / "python"), str(WT / "shared" / "core")]
import numpy as np                                           # noqa: E402
from PIL import Image, ImageDraw, ImageFont                  # noqa: E402
from rostrum_core import Document                            # noqa: E402
from rostrum3d import KIND, run_source                       # noqa: E402
from rostrum3d.compile import describe                       # noqa: E402
from rostrum3d.engine import Engine                          # noqa: E402

OUT = Path(sys.argv[1])
W, H = 960, 400
FAILS = []


def tile(path: Path, text: str, colour: str):
    im = Image.new("RGB", (512, 512), colour)
    d = ImageDraw.Draw(im)
    d.text((256, 256), text, fill="white", font=ImageFont.load_default(size=150), anchor="mm")
    d.rectangle((0, 0, 511, 511), outline="white", width=12)
    im.save(path)


def files(folder: Path) -> Path:
    tile(folder / "t.1001.png", "1001", "#c0392b")
    tile(folder / "t.1002.png", "1002", "#2457b5")
    (folder / "card.mtl").write_text("newmtl card\nKd 1 1 1\nmap_Kd t.1001.png\n", encoding="utf-8")
    (folder / "card.obj").write_text(
        "mtllib card.mtl\nv -1 0 0\nv 1 0 0\nv 1 1 0\nv -1 1 0\nvt 0 0\nvt 2 0\nvt 2 1\nvt 0 1\nvn 0 0 1\n"
        "usemtl card\nf 1/1/1 2/2/1 3/3/1 4/4/1\n", encoding="utf-8")
    (folder / "card.usda").write_text(USDA, encoding="utf-8")
    return folder / "card.obj"


USDA = """#usda 1.0
(
    defaultPrim = "Card"
    metersPerUnit = 1
    upAxis = "Y"
)
def Xform "Card"
{
    def Mesh "Mesh" (prepend apiSchemas = ["MaterialBindingAPI"])
    {
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [(-1, 0, 0), (1, 0, 0), (1, 1, 0), (-1, 1, 0)]
        texCoord2f[] primvars:st = [(0, 0), (2, 0), (2, 1), (0, 1)] (interpolation = "vertex")
        rel material:binding = </Card/Mat>
    }
    def Material "Mat"
    {
        token outputs:surface.connect = </Card/Mat/S.outputs:surface>
        def Shader "S"
        {
            uniform token info:id = "UsdPreviewSurface"
            color3f inputs:diffuseColor.connect = </Card/Mat/T.outputs:rgb>
            token outputs:surface
        }
        def Shader "T"
        {
            uniform token info:id = "UsdUVTexture"
            asset inputs:file = @./t.<UDIM>.png@
            float2 inputs:st.connect = </Card/Mat/R.outputs:result>
            token inputs:sourceColorSpace = "sRGB"
            float3 outputs:rgb
        }
        def Shader "R"
        {
            uniform token info:id = "UsdPrimvarReader_float2"
            string inputs:varname = "st"
            float2 outputs:result
        }
    }
}
"""


def scene(obj: Path, picture: str) -> dict:
    src = f'''
tiles = material("tiles", baseColor="#ffffff", roughness=0.9, baseColorTexture={str(picture)!r})
import_usd("own", file={str(obj)!r}, x=-2.3)
import_usd("usd", file={str(obj.with_suffix(".usda"))!r}, x=0)
import_usd("mine", file={str(obj)!r}, x=2.3, material="tiles")
light("sky", kind="dome", color="#ffffff", intensity=1)
cam = camera("cam", focalLength=35, y=0.5, z=6.8).aim((0, 0.5, 0))
shot("s", camera=cam, fps=24, start=0, end=1)
'''
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(src, "s.py"))
    return describe(doc.data, "s")


def quick(eng) -> Image.Image:
    v, w, h, stride, _ = eng.view(camera="cam", frame=0, width=W, height=H, renderer="storm")
    try:
        px = np.frombuffer(v, np.uint8).reshape(h, stride)[:, :w * 4].reshape(h, w, 4).copy()
    finally:
        v.release()
    return Image.fromarray(px).convert("RGB")


def halves(pic: Image.Image, label: str):
    """Along the cards' middle row, the coloured stretches (wider than 8 px) go red, blue three times: each card's
    tile 1001 then 1002 (wherever the renderer framed them; a tile's white digits don't split it)."""
    a = np.asarray(pic, np.float32)
    rows = np.nonzero((a.max(2) - a.min(2) > 40).any(1))[0]
    row = a[(rows.min() + rows.max()) // 2] if len(rows) else a[H // 2]
    colour = np.where(row.max(1) - row.min(1) <= 40, -1, np.argmax(row, 1))   # 0 red, 2 blue, -1 grey or white
    runs, start = [], 0
    for x in range(1, W + 1):
        if x == W or colour[x] != colour[start]:
            if colour[start] >= 0 and x - start > 8 and (not runs or runs[-1] != ("red" if colour[start] == 0 else "blue" if colour[start] == 2 else "other")):
                runs.append("red" if colour[start] == 0 else "blue" if colour[start] == 2 else "other")
            start = x
    ok = runs == ["red", "blue"] * 3
    print(("ok  " if ok else "FAIL"), label, "cards read", " ".join(runs) or "nothing",
          "(file's own material | USD by reference | Rostrum material)")
    if not ok:
        FAILS.append(f"{label}: {' '.join(runs)}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    folder = OUT / "files"
    folder.mkdir(exist_ok=True)
    obj = files(folder)
    font = ImageFont.load_default(size=18)
    with Engine() as eng:
        eng.load(scene(obj, str(folder / "t.1001.png")))
        q = quick(eng)
        png = OUT / "udim-cycles.png"
        eng.render(camera="cam", renderer="cycles", frame=0, width=W, height=H, samples=32, png=str(png))
        c = Image.open(png).convert("RGB")
        halves(q, "Quick")
        halves(c, "Cycles")
        out = Image.new("RGB", (W, 2 * H + 60), "white")
        d = ImageDraw.Draw(out)
        for i, (p, t) in enumerate([(q, "Quick view"), (c, "Cycles (Final)")]):
            out.paste(p, (0, 30 + i * (H + 30)))
            d.text((8, 5 + i * (H + 30)), t + "  (left: OBJ, its own material; middle: USD, by reference; right: a Rostrum material)",
                   fill="black", font=font)
        out.save(OUT / "udim-quick-vs-cycles.png")
        print("picture", OUT / "udim-quick-vs-cycles.png")
        try:
            eng.load(scene(obj, str(folder / "nope.<UDIM>.png")))
            FAILS.append("a set with no tile was accepted")
            print("FAIL a set with no tile was accepted")
        except Exception as e:                                     # noqa: BLE001 (the refusal is the check)
            print("ok   a set with no tile is refused:", str(e)[:160])
    if FAILS:
        print(f"\n{len(FAILS)} check(s) failed: " + " | ".join(FAILS))
        sys.exit(1)
    print("\nevery check passed")


if __name__ == "__main__":
    main()
