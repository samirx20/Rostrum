"""Makes our own small SVG, PDF and PSD (coloured shapes, a curved path, a group, a line of text; PSD: pixel layers with
names, one at 50 %, one multiply, one in a group) plus a flat PNG of each where we can render it here.
Usage: python make_sources.py [out folder]   (default: the results/stage2/2d-io/sources folder under .rostrum/waves)"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\stage2\2d-io\sources")

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
  <rect id="sky" x="0" y="0" width="800" height="600" fill="#1d2b53"/>
  <circle id="sun" cx="620" cy="140" r="70" fill="#ffcc33"/>
  <rect id="card" x="80" y="320" width="300" height="180" rx="24" fill="#ff6b6b" stroke="#ffffff" stroke-width="6"/>
  <path id="wave" d="M 60 260 C 160 160 260 360 360 260 S 560 160 700 260" fill="none" stroke="#7bdff2" stroke-width="10" stroke-linecap="round"/>
  <g id="badge">
    <ellipse cx="560" cy="440" rx="90" ry="60" fill="#b8f2e6"/>
    <rect x="520" y="420" width="80" height="40" fill="#5e6472" fill-opacity="0.8"/>
  </g>
  <text id="title" x="80" y="100" font-family="Roboto Flex" font-size="64" fill="#ffffff">Hello Rostrum</text>
</svg>
"""


def make_pdf(path: Path):
    """A one-page PDF written by hand: a rect, a curved filled shape, a stroked curve, a form XObject (group), text."""
    k = 0.5523
    cx, cy, rx, ry = 560, 160, 90, 60                   # PDF is y-up: this ellipse is near the page's lower middle
    ell = (f"{cx + rx} {cy} m {cx + rx} {cy + ry * k} {cx + rx * k} {cy + ry} {cx} {cy + ry} c "
           f"{cx - rx * k} {cy + ry} {cx - rx} {cy + ry * k} {cx - rx} {cy} c "
           f"{cx - rx} {cy - ry * k} {cx - rx * k} {cy - ry} {cx} {cy - ry} c "
           f"{cx + rx * k} {cy - ry} {cx + rx} {cy - ry * k} {cx + rx} {cy} c h f")
    form = "0.7 0.95 0.9 rg 480 380 120 60 re f 0.37 0.39 0.45 rg 500 395 60 30 re f"
    content = f"""0.11 0.17 0.33 rg 0 0 800 600 re f
1 0.42 0.42 rg 80 100 300 180 re f
0.97 0.8 0.2 rg {ell}
0.48 0.87 0.95 RG 10 w 1 J 60 340 m 160 440 260 240 360 340 c S
/Fm1 Do
1 1 1 rg BT /F1 64 Tf 80 500 Td (Hello Rostrum) Tj ET
"""
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 800 600] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> /XObject << /Fm1 6 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}endstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Type /XObject /Subtype /Form /BBox [0 0 800 600] /Length {len(form)} >>\nstream\n{form}\nendstream",
    ]
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


def _swatch(size, colour, draw):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw(ImageDraw.Draw(img), colour)
    return img


def make_psd(path: Path):
    from psd_tools import PSDImage
    from psd_tools.api.layers import Group, PixelLayer
    from psd_tools.constants import BlendMode

    psd = PSDImage.new("RGBA", (800, 600), color=(0, 0, 0, 0))   # RGBA: layer alpha is the real transparency channel
    def add(parent, name, size, pos, colour, shape, opacity=255, blend=None):
        img = _swatch(size, colour, lambda d, c: getattr(d, shape)([0, 0, size[0] - 1, size[1] - 1], fill=c))
        layer = PixelLayer.frompil(img, parent, name=name, top=pos[1], left=pos[0])
        layer.opacity = opacity
        if blend:
            layer.blend_mode = blend
        return layer                                     # frompil already put it in `parent`

    add(psd, "Background", (800, 600), (0, 0), (29, 43, 83, 255), "rectangle")   # a real layer, as a painter's file has
    add(psd, "Sun", (140, 140), (550, 70), (255, 204, 51, 255), "ellipse")
    add(psd, "Card", (300, 180), (80, 320), (255, 107, 107, 255), "rectangle")
    add(psd, "Ghost", (260, 160), (200, 250), (123, 223, 242, 255), "rectangle", opacity=128)
    add(psd, "Shade", (300, 200), (400, 380), (200, 120, 255, 255), "ellipse", blend=BlendMode.MULTIPLY)
    group = Group.new(psd, name="Badge group")
    add(group, "Badge", (180, 120), (470, 380), (184, 242, 230, 255), "ellipse")
    add(group, "Badge dot", (60, 60), (530, 410), (94, 100, 114, 255), "rectangle")
    psd.save(path)
    psd = PSDImage.open(path)
    psd.composite().convert("RGB").save(path.with_suffix(".psd.png"))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sample.svg").write_text(SVG, encoding="utf-8")
    make_pdf(OUT / "sample.pdf")
    import pypdfium2 as pdfium
    pdfium.PdfDocument(str(OUT / "sample.pdf"))[0].render(scale=1).to_pil().save(OUT / "sample.pdf.png")
    make_psd(OUT / "sample.psd")
    print("wrote", *sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
