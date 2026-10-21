"""Four still frames of our own, aimed at the level of a phone launch film: big tight display type, heavy soft
blur and glass, multi-stop gradients (also inside text), masks and clip reveals, glow, depth.
Each frame is a page shell (fonts + styles) and the stage's markup, the two pieces the renderer takes.
"""
import base64
from functools import lru_cache
from pathlib import Path

W, H = 1920, 1080
FONT = Path(r"C:\Users\Sam\Documents\CODE\OLD-EXPERIMENT\public\fonts\variable\RobotoFlex.ttf")  # SIL OFL, variable


@lru_cache(maxsize=1)
def _font_url() -> str:
    return "data:font/ttf;base64," + base64.b64encode(FONT.read_bytes()).decode("ascii")


BASE_CSS = """
html, body { margin: 0; background: #000; }
#rostrum-stage { position: relative; width: 1920px; height: 1080px; overflow: hidden; background: #000;
  font-family: "Flex"; color: #f5f5f7; }
.abs { position: absolute; }
.metal { background: linear-gradient(100deg, #55555a 0%, #f2f2f4 20%, #8e8e93 36%, #ffffff 50%, #6e6e73 66%,
  #e4ddd6 84%, #45454a 100%); -webkit-background-clip: text; background-clip: text; color: transparent; }
"""

CSS = {
    "type": """
.glow { left: 560px; top: 260px; width: 800px; height: 520px; border-radius: 50%;
  background: radial-gradient(closest-side, rgba(255,150,70,.75), rgba(255,90,40,.35) 55%, rgba(120,30,90,0) 100%);
  filter: blur(90px); }
.eyebrow { left: 0; right: 0; top: 250px; text-align: center; font-size: 22px; font-weight: 560;
  letter-spacing: .34em; color: #a1a1a6; }
.head { left: 0; right: 0; top: 300px; text-align: center; font-size: 230px; line-height: .92; font-weight: 780;
  font-stretch: 88%; letter-spacing: -.05em; }
.sub { left: 0; right: 0; top: 560px; text-align: center; font-size: 46px; font-weight: 280; letter-spacing: -.01em;
  color: #e8e8ed; }
.body { left: 660px; width: 600px; top: 680px; text-align: center; font-size: 19px; line-height: 1.5; font-weight: 420;
  color: #86868b; }
.rule { left: 860px; top: 650px; width: 200px; height: 1px;
  background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,.6), rgba(255,255,255,0)); }
""",
    "glass": """
#rostrum-stage { background: #05060c; }
.orb { border-radius: 50%; filter: blur(70px); }
.o1 { left: 300px; top: 120px; width: 620px; height: 620px; background: radial-gradient(circle at 35% 35%, #ff6a3d, #c2185b 60%, #4a148c); }
.o2 { left: 980px; top: 380px; width: 720px; height: 560px; background: linear-gradient(140deg, #00c6ff, #0072ff 50%, #7b2ff7); }
.o3 { left: 760px; top: 40px; width: 360px; height: 360px; background: radial-gradient(circle, #ffe259, #ffa751); }
.card { left: 520px; top: 250px; width: 880px; height: 540px; border-radius: 52px;
  background: linear-gradient(160deg, rgba(255,255,255,.16), rgba(255,255,255,.04));
  backdrop-filter: blur(44px) saturate(180%); -webkit-backdrop-filter: blur(44px) saturate(180%);
  border: 1px solid rgba(255,255,255,.22);
  box-shadow: 0 50px 140px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.35); }
.big { left: 90px; top: 40px; font-size: 300px; line-height: 1; font-weight: 170; letter-spacing: -.065em;
  background: linear-gradient(180deg, #ffffff 30%, rgba(255,255,255,.35)); -webkit-background-clip: text;
  background-clip: text; color: transparent; }
.unit { left: 520px; top: 120px; font-size: 96px; font-weight: 760; letter-spacing: -.03em; }
.cap { left: 96px; top: 380px; font-size: 34px; font-weight: 420; letter-spacing: -.005em; color: rgba(255,255,255,.86); }
.cap2 { left: 96px; top: 430px; font-size: 20px; font-weight: 450; letter-spacing: .02em; color: rgba(255,255,255,.55); }
.pill { left: 1240px; top: 190px; width: 300px; height: 96px; border-radius: 48px; background: rgba(20,20,30,.35);
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px); border: 1px solid rgba(255,255,255,.18);
  font-size: 30px; font-weight: 600; line-height: 96px; text-align: center; letter-spacing: .01em; }
""",
    "reveal": """
#rostrum-stage { background: radial-gradient(120% 90% at 50% 110%, #1a0b2e 0%, #07040d 55%, #000 100%); }
.ring { left: 660px; top: 140px; width: 600px; height: 600px; border-radius: 50%;
  background: conic-gradient(from 210deg, #ff2d55, #ff9f0a, #ffd60a, #30d158, #64d2ff, #bf5af2, #ff2d55);
  -webkit-mask-image: radial-gradient(closest-side, transparent 86%, #000 87%, #000 99%, transparent 100%);
  mask-image: radial-gradient(closest-side, transparent 86%, #000 87%, #000 99%, transparent 100%); }
.ringglow { left: 660px; top: 140px; width: 600px; height: 600px; border-radius: 50%;
  background: conic-gradient(from 210deg, #ff2d55, #ff9f0a, #ffd60a, #30d158, #64d2ff, #bf5af2, #ff2d55);
  filter: blur(80px); opacity: .55; }
.pro { left: 0; right: 0; top: 230px; text-align: center; font-size: 420px; line-height: 1; font-weight: 900;
  font-stretch: 120%; letter-spacing: -.06em;
  background: linear-gradient(180deg, #ffffff 0%, #ffd9a8 30%, #ff7a59 52%, #b03ad8 76%, #3a1d7a 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  -webkit-mask-image: linear-gradient(180deg, #000 55%, rgba(0,0,0,0) 92%);
  mask-image: linear-gradient(180deg, #000 55%, rgba(0,0,0,0) 92%); }
.wipe { left: 0; right: 0; top: 820px; text-align: center; font-size: 64px; font-weight: 300; letter-spacing: .14em;
  color: #fff; clip-path: inset(0 22% 0 22%); }
.outline { left: 0; right: 0; top: 910px; text-align: center; font-size: 96px; font-weight: 800; letter-spacing: -.02em;
  color: transparent; -webkit-text-stroke: 1.5px rgba(255,255,255,.7); }
""",
    "depth": """
#rostrum-stage { background: radial-gradient(90% 70% at 50% 40%, #1d2433 0%, #0a0c12 60%, #000 100%); }
.scene { left: 0; top: 0; width: 1920px; height: 1080px; perspective: 1500px; }
.slab { top: 190px; width: 360px; height: 720px; border-radius: 64px; transform-style: preserve-3d;
  background: linear-gradient(155deg, #3a3f4b 0%, #1b1e25 45%, #2a2f3a 70%, #0e1014 100%);
  box-shadow: 0 60px 120px rgba(0,0,0,.7), inset 0 0 0 2px rgba(255,255,255,.12); }
.s1 { left: 520px; transform: rotateY(32deg) translateZ(-420px); filter: blur(7px); opacity: .8; }
.s2 { left: 780px; transform: rotateY(24deg) translateZ(-160px); filter: blur(2.5px); }
.s3 { left: 1040px; transform: rotateY(16deg); }
.spec { left: 0; top: 0; width: 100%; height: 100%; border-radius: 64px; mix-blend-mode: screen;
  background: linear-gradient(115deg, rgba(255,255,255,0) 30%, rgba(170,200,255,.45) 46%, rgba(255,255,255,0) 60%); }
.lens { left: 110px; top: 70px; width: 140px; height: 140px; border-radius: 50%;
  background: radial-gradient(circle at 40% 35%, #6b7a99, #0b0d12 60%); box-shadow: 0 0 0 10px #2c313c, 0 0 40px rgba(120,160,255,.4); }
.head { left: 140px; top: 360px; font-size: 180px; font-weight: 720; letter-spacing: -.055em; line-height: 1;
  color: #fff; text-shadow: 0 0 40px rgba(110,170,255,.85), 0 0 120px rgba(80,120,255,.6); }
.kicker { left: 146px; top: 320px; font-size: 24px; font-weight: 600; letter-spacing: .28em; color: #8fb4ff; }
.floor { left: 0; top: 860px; width: 1920px; height: 220px;
  background: linear-gradient(180deg, rgba(120,150,220,.18), rgba(0,0,0,0)); filter: blur(20px); }
.vignette { left: 0; top: 0; width: 1920px; height: 1080px;
  background: radial-gradient(75% 75% at 50% 50%, rgba(0,0,0,0) 55%, rgba(0,0,0,.7) 100%); }
""",
}

STAGE = {
    "type": """
<div class="abs glow"></div>
<div class="abs eyebrow">INTRODUCING</div>
<div class="abs head metal">Forged in light.</div>
<div class="abs sub">Thinner. Brighter. Quietly faster.</div>
<div class="abs rule"></div>
<div class="abs body">A frame cut from one block, finished by hand, with a display that reaches 3000 nits in direct sun and drops to one at night.</div>
""",
    "glass": """
<div class="abs orb o1"></div><div class="abs orb o2"></div><div class="abs orb o3"></div>
<div class="abs card">
  <div class="abs big">48</div><div class="abs unit">MP</div>
  <div class="abs cap">Main camera. Quad-pixel sensor.</div>
  <div class="abs cap2">2× optical-quality zoom · f/1.78 · second-generation stabilisation</div>
</div>
<div class="abs pill">Night mode</div>
""",
    "reveal": """
<div class="abs ringglow"></div>
<div class="abs ring"></div>
<div class="abs pro">Pro</div>
<div class="abs wipe">BEYOND PRO</div>
<div class="abs outline">Made to be seen.</div>
""",
    "depth": """
<div class="abs scene">
  <div class="abs slab s1"><div class="abs spec"></div></div>
  <div class="abs slab s2"><div class="abs spec"></div></div>
  <div class="abs slab s3"><div class="abs lens"></div><div class="abs spec"></div></div>
</div>
<div class="abs floor"></div>
<div class="abs kicker">PRO CAMERA</div>
<div class="abs head">Depth.</div>
<div class="abs vignette"></div>
""",
}

NAMES = list(STAGE)


def shell(css: str) -> str:
    face = ('@font-face { font-family: "Flex"; src: url(%s) format("truetype"); font-weight: 100 1000; '
            'font-stretch: 25%% 151%%; }' % _font_url())
    return ("<!DOCTYPE html><html><head><meta charset=\"utf-8\"><style>" + face + BASE_CSS + css +
            "</style></head><body><div id=\"rostrum-stage\"></div></body></html>")


def full_page(shell_html: str, stage: str) -> str:
    """The same page as one standalone HTML file (what Chromium loads)."""
    return shell_html.replace('<div id="rostrum-stage"></div>', '<div id="rostrum-stage">' + stage + "</div>")


# Second try at the three gaps, with routes the archive's patches already support: gradient text as an inline
# SVG <text> (web fonts reach the SVG font database), the text outline as an inline style (the only place the
# patched painter reads it), and the 3D tilt as transform: perspective(...) on each card (no parent `perspective`).
def _svg_text(text, size, weight, stretch, spacing, stops, w, h, y, extra=""):
    st = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block">'
            f'<defs><linearGradient id="g{weight}" x1="0" y1="0" x2="1" y2="0.25">{st}</linearGradient></defs>'
            f'<text x="{w // 2}" y="{y}" text-anchor="middle" font-family="Flex" font-size="{size}" font-weight="{weight}" '
            f'font-stretch="{stretch}" letter-spacing="{spacing}" fill="url(#g{weight})" {extra}>{text}</text></svg>')


METAL = [(0, "#55555a"), (.2, "#f2f2f4"), (.36, "#8e8e93"), (.5, "#ffffff"), (.66, "#6e6e73"), (.84, "#e4ddd6"), (1, "#45454a")]
AURORA = [(0, "#ffffff"), (.3, "#ffd9a8"), (.52, "#ff7a59"), (.76, "#b03ad8"), (1, "#3a1d7a")]
for _n in ("type", "reveal", "depth"):
    CSS[_n + "-alt"] = CSS[_n]
STAGE["type-alt"] = STAGE["type"].replace(
    '<div class="abs head metal">Forged in light.</div>',
    '<div class="abs" style="left:0;top:300px">' + _svg_text("Forged in light.", 230, 780, "88%", -11.5, METAL, 1920, 260, 205) + "</div>")
STAGE["reveal-alt"] = STAGE["reveal"].replace(
    '<div class="abs pro">Pro</div>',
    '<div class="abs" style="left:0;top:230px">' + _svg_text("Pro", 420, 900, "120%", -25, [(o, c) for o, c in AURORA], 1920, 440, 340) + "</div>").replace(
    '<div class="abs outline">', '<div class="abs outline" style="-webkit-text-stroke: 1.5px rgba(255,255,255,.7)">')
CSS["depth-alt"] = CSS["depth"].replace("perspective: 1500px;", "").replace(
    "transform: rotateY(32deg) translateZ(-420px)", "transform: perspective(1500px) rotateY(32deg) translateZ(-420px)").replace(
    "transform: rotateY(24deg) translateZ(-160px)", "transform: perspective(1500px) rotateY(24deg) translateZ(-160px)").replace(
    "transform: rotateY(16deg)", "transform: perspective(1500px) rotateY(16deg)")
STAGE["depth-alt"] = STAGE["depth"]
NAMES = list(STAGE)
