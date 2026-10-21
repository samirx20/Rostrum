"""Render the four frames with the Rostrum renderer (Blitz + Skia) and with headless Chrome, then make
side-by-sides, a 4x-amplified difference picture, and an SSIM score for each.

  python stills.py <scratch dir> <results dir>
"""
import re
import subprocess
import sys
import time
from pathlib import Path

import frames
from rostrum2d import Renderer

CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
LABEL_FONT = "C\\:/Windows/Fonts/segoeui.ttf"


def chrome_shot(page: Path, png: Path, profile: Path) -> float:
    t0 = time.perf_counter()
    subprocess.run([str(CHROME), "--headless=new", "--disable-gpu-sandbox", "--hide-scrollbars",
                    "--force-device-scale-factor=1", "--window-size=1920,1080", "--virtual-time-budget=3000",
                    f"--user-data-dir={profile}", f"--screenshot={png}", page.as_uri()],
                   check=True, timeout=120, capture_output=True)
    if not png.exists():
        raise RuntimeError(f"Chrome wrote no screenshot for {page}")
    return (time.perf_counter() - t0) * 1000.0


def ffmpeg(*args: str) -> str:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-y", *args], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + r.stderr[-800:])
    return r.stderr


def side_by_side(blitz: Path, chrome: Path, out: Path):
    label = ("pad=iw:ih+64:0:64:color=0x1c1c1e,drawtext=fontfile='%s':text='%s':x=24:y=14:fontsize=34:fontcolor=white")
    ffmpeg("-i", str(blitz), "-i", str(chrome), "-filter_complex",
           f"[0]{label % (LABEL_FONT, 'Rostrum renderer (Blitz + Skia)')}[a];"
           f"[1]{label % (LABEL_FONT, 'Chromium (Chrome headless)')}[b];"
           "[a]pad=iw+16:ih:0:0:color=0x1c1c1e[a2];[a2][b]hstack", "-frames:v", "1", str(out))


def diff_picture(blitz: Path, chrome: Path, out: Path):
    ffmpeg("-i", str(blitz), "-i", str(chrome), "-filter_complex",
           "[0]format=rgb24[a];[1]format=rgb24[b];[a][b]blend=all_mode=difference,lutrgb=r='min(val*4,255)':g='min(val*4,255)':b='min(val*4,255)'",
           "-frames:v", "1", str(out))


def ssim(blitz: Path, chrome: Path) -> float:
    err = ffmpeg("-i", str(blitz), "-i", str(chrome), "-lavfi", "ssim", "-f", "null", "-")
    return float(re.search(r"All:([0-9.]+)", err).group(1))


def main(scratch: Path, results: Path):
    scratch.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    rows = []
    with Renderer(scratch / "renderer-stills.log") as r:
        print(f"renderer pid {r.pid}")
        for name in (sys.argv[3].split(",") if len(sys.argv) > 3 else frames.NAMES):
            sh, stage = frames.shell(frames.CSS[name]), frames.STAGE[name]
            page = scratch / f"{name}.html"
            page.write_text(frames.full_page(sh, stage), encoding="utf-8")
            blitz, chrome = results / f"{name}-blitz.png", results / f"{name}-chromium.png"
            opened = r.open(frames.W, frames.H, sh)
            r.still(stage, blitz)          # first paint of a new page (fonts, shaders)
            again = r.still(stage, blitz)  # the same frame painted again: the steady per-frame cost
            chrome_ms = chrome_shot(page, chrome, scratch / "chrome-profile")
            side_by_side(blitz, chrome, results / f"{name}-blitz-vs-chromium.png")
            diff_picture(blitz, chrome, scratch / f"{name}-diff.png")
            score = ssim(blitz, chrome)
            t = again.get("timing", {})
            rows.append((name, score, again["roundTripMs"], t, chrome_ms, opened.get("adapter")))
            print(f"{name}: SSIM {score:.4f}, renderer frame {again['roundTripMs']:.1f} ms (timing {t}), "
                  f"Chrome shot incl. start {chrome_ms:.0f} ms, gpu {opened.get('gpu')} {opened.get('adapter')}")
    return rows


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
