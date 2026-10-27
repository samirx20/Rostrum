"""sherpa-onnx (the program that runs the speech model for render_voice what: "words"), installed on demand. The app's
Python does not ship it, so the first call that needs it downloads the two pinned wheels from PyPI (sherpa-onnx and
sherpa-onnx-core 1.13.8, Apache-2.0; the core bundles ONNX Runtime, MIT; ~19 MB on Windows), checks size and sha256
(cleanup/fetch.py, the models' own download), and unpacks them into the models folder, the same way as OpenCV
(sfx/opencv.py). A Python that already has sherpa_onnx (the development environment) uses its own. Before this an
agent got "not installed in the app's Python" and a pip command for a Python it can't reach (2D final critic F5-3).
`python -m rostrum_sound.sherpa` installs it ahead of time.
"""
from __future__ import annotations

import importlib
import shutil
import sys
import zipfile
from pathlib import Path

from rostrum_core import RostrumError, codes

from .cleanup import fetch
from .cleanup.models import Model

VERSION = "1.13.8"
_PYPI = "https://files.pythonhosted.org/packages/"
WHEELS = {   # platform -> [(path under _PYPI, size, sha256)]; from https://pypi.org/pypi/sherpa-onnx(-core)/1.13.8/json
    "win_amd64": [("24/af/33e9dcaa527bbc0c2526959713626607a46da2d7b19871b7773d8607d356/"
                   "sherpa_onnx-1.13.8-cp312-cp312-win_amd64.whl", 2287856,
                   "566e49ad3fb2aa8ceb723a52f9809aa6c2ee0a5eb3b0946c3fd2374af807a5c6"),
                  ("94/38/64356ad97f68fffcf01fe7545407ad18a2ea86c1ffae5b0950f7fac73638/"
                   "sherpa_onnx_core-1.13.8-py3-none-win_amd64.whl", 16903581,
                   "5579e80196d516e6dae23c8f629292ce3142ab8869925d32b94612fd86f93733")],
    "macosx_arm64": [("78/6e/8d9b92e95896ec500084e706529f5637eff797246e74c498922f6aa13a53/"
                      "sherpa_onnx-1.13.8-cp312-cp312-macosx_11_0_arm64.whl", 2146858,
                      "04b9268c348e9f4bd61315754ad06b02a3c185d3d7770acd8e2dcee9c2e039f9"),
                     ("8c/2a/2a47b423fe009bbbcb6d7eed7bcba755d6f9ae923b5664c7208128c32d06/"
                      "sherpa_onnx_core-1.13.8-py3-none-macosx_11_0_arm64.whl", 9552498,
                      "9312bbd46c93e31cecd3abda9cc8e71881d86cc3da3c35c7445ab04025b9fc3e")],
}
COMMAND = "python -m rostrum_sound.sherpa"


def _platform() -> str:
    from .sfx.opencv import _platform as plat
    return plat()


def wheels() -> list[Model]:
    plat = _platform()
    if plat not in WHEELS or sys.version_info[:2] != (3, 12):
        raise RostrumError(codes.MODEL_MISSING, "voice words", f"sherpa-onnx for {plat}, Python "
                           f"{sys.version_info[0]}.{sys.version_info[1]}", "has no pinned download",
                           hint=f'Install it into this Python yourself: "{sys.executable}" -m pip install '
                                f"sherpa-onnx=={VERSION} (Apache-2.0).")
    return [Model(f"sherpa-onnx-{VERSION}", path.rsplit("/", 1)[1], size, sha, "Apache-2.0 (sherpa-onnx, k2-fsa; "
                  "the core bundles ONNX Runtime, MIT)", f"sherpa-onnx@{VERSION}", 0.0, _PYPI + path)
            for path, size, sha in WHEELS[plat]]


def site() -> Path:
    """Where the unpacked wheels live (next to the .whl files in the models folder)."""
    return fetch.target(wheels()[0]).parent / "site"


def module(where: str = "voice words"):
    """The sherpa_onnx module: this Python's own, else the unpacked one, else installed now (a download, said on
    stderr). A failed download is a plain error naming what to do."""
    try:
        return importlib.import_module("sherpa_onnx")
    except ImportError:
        pass
    folder = site()
    if not (folder / "sherpa_onnx").is_dir():
        print(f"rostrum: installing sherpa-onnx {VERSION} for the speech model (about "
              f"{sum(m.size for m in wheels()) / 1e6:.0f} MB, once)…", file=sys.stderr, flush=True)
        try:
            install()
        except RostrumError as e:
            raise RostrumError(codes.MODEL_MISSING, where, "sherpa-onnx (the program that runs the speech model)",
                               f"could not be installed: {e.problem}", hint=f"Check the connection and try again, or "
                               f"run: {COMMAND}") from e
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    return importlib.import_module("sherpa_onnx")


def install(progress=None) -> Path:
    """Download (hash checked) and unpack both wheels into one folder; returns the folder put on the path."""
    out = site()
    tmp = out.with_name("site.partial")
    shutil.rmtree(tmp, ignore_errors=True)
    for m in wheels():
        whl = fetch.install(m, progress)
        with zipfile.ZipFile(whl) as z:
            z.extractall(tmp)
        whl.unlink()                                 # unpacked: the wheel itself is not needed again
    shutil.rmtree(out, ignore_errors=True)
    tmp.replace(out)
    return out


def main() -> int:
    try:
        print(f"sherpa-onnx {VERSION}: installed at {install(lambda d, t: print(f'{100 * d // max(t, 1)}%', end='\r'))}")
    except RostrumError as e:
        print(e.line(), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
