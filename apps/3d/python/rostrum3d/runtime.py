"""Where Rostrum3D's libraries live and how the engine program is told about them.

One folder, laid out by `apps/3d/libs/lay_out.py`:  ~/.rostrum/libs/3d/<VERSION>   (or ROSTRUM3D_LIBS)
    runtime/bin           the DLLs the engine loads
    runtime/usd/lib       usd_ms.dll (its plug-ins are in usd/lib/usd, found next to it)
    runtime/hydra/cycles  Cycles' Hydra plug-in  (hydra/ is the plug-in folder, lib/ holds the GPU kernels)
    runtime/hydra/rostrum our stylized plug-in
"""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
VERSION = "5.2.2-cycles-a456b76-r1"                       # same name as in apps/3d/libs/lay_out.py


class LibsMissing(RuntimeError):
    pass


def libs_root() -> Path:
    """ROSTRUM3D_LIBS, else the version folder under ~/.rostrum/libs/3d."""
    if os.environ.get("ROSTRUM3D_LIBS"):
        return Path(os.environ["ROSTRUM3D_LIBS"])
    return Path.home() / ".rostrum" / "libs" / "3d" / VERSION


LIBS_ROOT = libs_root()


def find_exe() -> Path:
    """ROSTRUM3D_CORE, else this checkout's install."""
    if os.environ.get("ROSTRUM3D_CORE"):
        return Path(os.environ["ROSTRUM3D_CORE"])
    return REPO / "apps" / "3d" / "core" / ".build" / "install" / "rostrum3d-core.exe"


def runtime_env(base: dict | None = None) -> dict:
    """The child's environment: DLL folders on PATH, where Hydra finds the Cycles and stylized plug-ins, the GPU choice."""
    rt = libs_root() / "runtime"
    dirs = [rt / "bin", rt / "usd" / "lib"]
    plugins = [rt / "hydra" / "cycles" / "hydra", rt / "hydra" / "rostrum"]
    for d in (*dirs, *plugins):
        if not d.is_dir():
            raise LibsMissing(f"3D libraries missing: {d} not found. Run: python -I apps\\3d\\libs\\lay_out.py "
                              "(or set ROSTRUM3D_LIBS to a folder it made)")
    env = dict(os.environ if base is None else base)
    env["PATH"] = os.pathsep.join([str(d) for d in dirs] + [env.get("PATH", "")])
    env["PXR_PLUGINPATH_NAME"] = os.pathsep.join(str(p) for p in plugins)
    env.setdefault("CYCLES_DEVICE", "OPTIX")
    return env
