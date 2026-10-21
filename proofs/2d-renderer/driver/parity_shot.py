"""One moment of the animated shot, rendered by the Rostrum renderer and by Chrome, side by side.

  python parity_shot.py <scratch dir> <results dir> <seconds>
"""
import sys
from pathlib import Path

import frames
import shot
import stills
from rostrum2d import Renderer

scratch, results, t = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
sh, stage = frames.shell(shot.CSS), shot.stage_at(t)
page = scratch / "shot.html"
page.write_text(frames.full_page(sh, stage), encoding="utf-8")
blitz, chrome = scratch / "shot-blitz.png", scratch / "shot-chromium.png"
with Renderer(scratch / "renderer-parity.log") as r:
    r.open(frames.W, frames.H, sh)
    r.still(stage, blitz)
stills.chrome_shot(page, chrome, scratch / "chrome-profile")
stills.side_by_side(blitz, chrome, results / f"shot-{t:.1f}s-blitz-vs-chromium.png")
print(f"SSIM {stills.ssim(blitz, chrome):.4f}")
