"""Programs the bundle carries that are not Python packages or our own builds: 2D's LGPL FFmpeg and the Visual C++
runtime the engines need. Each is checked and fails loudly; nothing here is looked for on PATH.

    ffmpeg(stage)         <stage>/apps/2d/ffmpeg: ffmpeg.exe, ffprobe.exe, their DLLs and LICENSE.txt, from BtbN's LGPL
                          shared build (the zip in the release cache, sha256 checked; no GPL, no non-free parts)
    crt(stage, engines)   msvcp140.dll, vcruntime140.dll, vcruntime140_1.dll beside each engine (Microsoft allows these
                          app-local copies, from Visual Studio's redist folder), so a Windows without the "Visual C++
                          Redistributable" still starts them
"""
from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path

CACHE = Path.home() / ".rostrum" / "release-cache" / "downloads"
FFMPEG_ZIP = CACHE / "ffmpeg" / "ffmpeg-n8.1-latest-win64-lgpl-shared-8.1.zip"   # github.com/BtbN/FFmpeg-Builds
FFMPEG_SHA256 = "0a6aef473350e9ff4c34302fa0cb1286d409b56c8f228367a4819ebb3ac19e9f"
FFMPEG_FILES = ["ffmpeg.exe", "ffprobe.exe", "avcodec-62.dll", "avdevice-62.dll", "avfilter-11.dll", "avformat-62.dll",
                "avutil-60.dll", "swresample-6.dll", "swscale-9.dll"]
CRT_FILES = ["msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"]
REDIST = "Microsoft Visual Studio/2022/*/VC/Redist/MSVC/*/x64/Microsoft.VC143.CRT"


class Missing(RuntimeError):
    pass


def ffmpeg(stage: Path) -> Path:
    if not FFMPEG_ZIP.is_file():
        raise Missing(f"2D's FFmpeg is missing: {FFMPEG_ZIP} (BtbN ffmpeg-n8.1-latest-win64-lgpl-shared-8.1.zip)")
    digest = hashlib.sha256(FFMPEG_ZIP.read_bytes()).hexdigest()
    if digest != FFMPEG_SHA256:
        raise Missing(f"{FFMPEG_ZIP} is not the checked build (sha256 {digest}, want {FFMPEG_SHA256})")
    out = stage / "apps" / "2d" / "ffmpeg"
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(FFMPEG_ZIP) as z:
        names = {Path(n).name if "/bin/" in n else n.split("/", 1)[-1]: n for n in z.namelist()}
        for f in FFMPEG_FILES + ["LICENSE.txt"]:
            if f not in names:
                raise Missing(f"{f} is not in {FFMPEG_ZIP}")
            with z.open(names[f]) as src, open(out / f, "wb") as dst:
                shutil.copyfileobj(src, dst)
    return out


def crt(stage: Path, engine_dirs: list[Path]) -> Path:
    found = sorted(p for root in (Path("C:/Program Files"), Path("C:/Program Files (x86)")) for p in root.glob(REDIST))
    if not found:
        raise Missing(f"the Visual C++ runtime redist folder is missing (C:/Program Files*/{REDIST}): install the "
                      "Visual Studio 2022 Build Tools")
    src = found[-1]
    for d in engine_dirs:
        for f in CRT_FILES:
            if not (src / f).is_file():
                raise Missing(f"{src / f} is missing")
            shutil.copy2(src / f, stage / d / f)
    return src
