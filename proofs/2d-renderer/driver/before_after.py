"""Before / after / Chrome for each frame: three pictures side by side and the SSIM of each against Chrome.

  python before_after.py <before dir> <after dir> <out dir> [frame,frame,...]

`before dir` and `after dir` hold `<frame>-blitz.png` and `<frame>-chromium.png` as `stills.py` writes them
(before = P-2D's run, after = a run with the current renderer). Writes `<frame>-before-after-vs-chromium.png`.
"""
import sys
from pathlib import Path

import frames
from stills import LABEL_FONT, ffmpeg, ssim


def three_up(before: Path, after: Path, chrome: Path, out: Path, scores: tuple[float, float]):
    label = "pad=iw:ih+64:0:64:color=0x1c1c1e,drawtext=fontfile='%s':text='%s':x=24:y=14:fontsize=34:fontcolor=white"
    names = (f"Before (SSIM {scores[0]:.3f})", f"After (SSIM {scores[1]:.3f})", "Chromium (Chrome headless)")
    parts = ";".join(f"[{i}]{label % (LABEL_FONT, n)},pad=iw+16:ih:0:0:color=0x1c1c1e[p{i}]" for i, n in enumerate(names))
    ffmpeg("-i", str(before), "-i", str(after), "-i", str(chrome), "-filter_complex",
           f"{parts};[p0][p1][p2]hstack=inputs=3,scale=iw/2:-2", "-frames:v", "1", str(out))


def main(before: Path, after: Path, out: Path, names: list[str]):
    out.mkdir(parents=True, exist_ok=True)
    for name in names:
        chrome = after / f"{name}-chromium.png"
        b, a = before / f"{name}-blitz.png", after / f"{name}-blitz.png"
        for p in (b, a, chrome):
            if not p.exists():
                raise FileNotFoundError(p)
        scores = (ssim(b, chrome), ssim(a, chrome))
        three_up(b, a, chrome, out / f"{name}-before-after-vs-chromium.png", scores)
        print(f"{name}: SSIM before {scores[0]:.4f}, after {scores[1]:.4f}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]),
         sys.argv[4].split(",") if len(sys.argv) > 4 else frames.NAMES)
