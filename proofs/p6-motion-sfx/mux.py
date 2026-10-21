"""Mux a silent video and a WAV: copy the picture, AAC 256k audio. Fails loudly.

    python mux.py <video> <wav> <out.mp4>
"""
import subprocess
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    video, wav, out = (Path(a) for a in sys.argv[1:])
    for p in (video, wav):
        if not p.is_file():
            raise SystemExit(f"missing input: {p}")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(wav), "-map", "0:v:0",
                        "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        raise SystemExit(f"ffmpeg failed ({r.returncode}): {r.stderr.strip()}")
    print("muxed", out)


if __name__ == "__main__":
    main()
