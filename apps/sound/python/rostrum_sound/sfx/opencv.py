"""OpenCV (reading video, optical flow for the motion look), loaded on demand. It is ~110 MB installed and only the
video looks (`look_video`, `motion`) use it, so the app does not ship it: the first video look asks for it, and
`python -m rostrum_sound.sfx.opencv` downloads the pinned opencv-python-headless wheel from PyPI (Apache-2.0, ~40 MB),
checks its size and sha256, and unpacks it into the models folder (settings.models_dir()). A Python that already has
cv2 (the development environment) uses its own.
"""
from __future__ import annotations

import importlib
import platform
import shutil
import sys
import zipfile
from pathlib import Path

from rostrum_core import RostrumError, codes

from ..cleanup import fetch
from ..cleanup.models import Model

VERSION = "5.0.0.93"
_PYPI = "https://files.pythonhosted.org/packages/"
WHEELS = {   # platform -> (path under _PYPI, size, sha256); from https://pypi.org/pypi/opencv-python-headless/5.0.0.93/json
    "win_amd64": ("b8/88/763b967f7efd7226b82c9fae16d560cba049b1f0c036647e65c610fd636e/"
                  "opencv_python_headless-5.0.0.93-cp37-abi3-win_amd64.whl", 43825962,
                  "829717b6a95554f273e49e357cee3b3a2a26b6f4842fbc1bed2b45bdd8f87e0e"),
    "macosx_arm64": ("53/7c/8c8097891c509d98cd128493835c95631c80be6a8f37ed9d25716c2e16f1/"
                     "opencv_python_headless-5.0.0.93-cp37-abi3-macosx_13_0_arm64.whl", 48322581,
                     "030ca5e0837a2963ab36ef896baa9767eb8d2b83353fb28af5a521e40dd8756f"),
    "macosx_x86_64": ("90/8c/eab2ad388c3cbab2a350c10c2ef19ce6bd099240afc31789032c996bab52/"
                      "opencv_python_headless-5.0.0.93-cp37-abi3-macosx_14_0_x86_64.whl", 34782894,
                      "1e55af3abfb462eeeabe5c775f12bdb36216d8a93a3583d69e6bd6e1d6ba7d00"),
}
COMMAND = "python -m rostrum_sound.sfx.opencv"


def _platform() -> str:
    if sys.platform == "win32":
        return "win_amd64"
    if sys.platform == "darwin":
        return "macosx_arm64" if platform.machine() == "arm64" else "macosx_x86_64"
    return f"{sys.platform}_{platform.machine()}"


def wheel() -> Model:
    plat = _platform()
    if plat not in WHEELS:
        raise RostrumError(codes.BAD_ARGUMENT, "video", plat, "has no pinned OpenCV download", accepted=list(WHEELS))
    path, size, sha = WHEELS[plat]
    return Model(f"opencv-{VERSION}", path.rsplit("/", 1)[1], size, sha, "Apache-2.0 (OpenCV; the wheel bundles FFmpeg, LGPL)",
                 f"opencv@{VERSION}", 0.0, _PYPI + path)


def site() -> Path:
    """Where the unpacked wheel lives (next to its .whl in the models folder)."""
    return fetch.target(wheel()).parent / "site"


def cv2():
    """The cv2 module. Raises a plain RostrumError naming the download when it is not there."""
    try:
        return importlib.import_module("cv2")
    except ImportError:
        pass
    folder = site()
    if not (folder / "cv2").is_dir():
        raise RostrumError(codes.MODEL_MISSING, "video", "OpenCV", "is not installed; the video looks need it to read video",
                           hint=f"Download it once with: {COMMAND} (about {wheel().size / 1e6:.0f} MB, into {folder.parent}).")
    sys.path.insert(0, str(folder))
    return importlib.import_module("cv2")


def install(progress=None) -> Path:
    """Download (hash checked) and unpack the wheel; returns the folder put on the path."""
    whl = fetch.install(wheel(), progress)
    out = site()
    tmp = out.with_name("site.partial")
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(whl) as z:
        z.extractall(tmp)
    shutil.rmtree(out, ignore_errors=True)
    tmp.replace(out)
    whl.unlink()                                     # unpacked: the wheel itself is not needed again
    return out


def main() -> int:
    try:
        print(f"OpenCV {VERSION}: installed at {install(lambda d, t: print(f'{100 * d // max(t, 1)}%', end='\r'))}")
    except RostrumError as e:
        print(e.line(), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
