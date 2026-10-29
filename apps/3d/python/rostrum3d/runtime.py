"""Where Rostrum3D's libraries live and how the engine program is told about them.

One folder, laid out by `apps/3d/libs/lay_out.py`:  ~/.rostrum/libs/3d/<VERSION>   (or ROSTRUM3D_LIBS)
    runtime/bin           the DLLs the engine loads
    runtime/usd/lib       usd_ms.dll (its plug-ins are in usd/lib/usd, found next to it)
    runtime/hydra/cycles  Cycles' Hydra plug-in  (hydra/ is the plug-in folder, lib/ holds the GPU kernels)

Our stylized plug-in (hdRostrum, the Stylized look) is not in that folder: it is built from this checkout by
apps/3d/stylized/build.bat into apps/3d/stylized/.build/install (hdRostrum.dll, plugInfo.json, hdRostrum/resources),
or ROSTRUM3D_STYLIZED names another such folder. Without it the engine runs without the Stylized look (its `info`
leaves "stylized" out of `renderers`), and asking for it fails with StylizedMissing, which names build.bat.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
VERSION = "5.2.2-cycles-a456b76-r5"                       # same name as in apps/3d/libs/lay_out.py


class LibsMissing(RuntimeError):
    pass


class StylizedMissing(LibsMissing):
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


def run_exe() -> Path:
    """The engine program to start: ROSTRUM3D_CORE as given, else a run copy of this checkout's build
    (engine_copy.py: a rebuild never collides with a running engine)."""
    if os.environ.get("ROSTRUM3D_CORE"):
        return find_exe()
    from .engine_copy import copy_of
    exe = find_exe()
    return copy_of(exe.parent, "3d-core", only=(exe.name,)) / exe.name


def stylized_dir() -> Path:
    """ROSTRUM3D_STYLIZED, else this checkout's build of the stylized plug-in (apps/3d/stylized/build.bat)."""
    if os.environ.get("ROSTRUM3D_STYLIZED"):
        return Path(os.environ["ROSTRUM3D_STYLIZED"])
    return REPO / "apps" / "3d" / "stylized" / ".build" / "install"


def stylized_found() -> bool:
    return (stylized_dir() / "plugInfo.json").is_file()


def need_stylized(where: str = "Stylized look"):
    """Loud when the stylized plug-in isn't built: what to run."""
    if not stylized_found():
        raise StylizedMissing(f"{where}: the stylized renderer isn't built: {stylized_dir() / 'plugInfo.json'} not found. "
                              "Run: apps\\3d\\stylized\\build.bat (or set ROSTRUM3D_STYLIZED to a folder it made)")


def runtime_env(base: dict | None = None) -> dict:
    """The child's environment: DLL folders on PATH, where Hydra finds the Cycles and stylized plug-ins (the stylized one
    only when built: stylized_dir), the GPU choice."""
    rt = libs_root() / "runtime"
    dirs = [rt / "bin", rt / "usd" / "lib"]
    plugins = [rt / "hydra" / "cycles" / "hydra"]
    for d in (*dirs, *plugins):
        if not d.is_dir():
            raise LibsMissing(f"3D libraries missing: {d} not found. Run: python -I apps\\3d\\libs\\lay_out.py "
                              "(or set ROSTRUM3D_LIBS to a folder it made)")
    if stylized_found():                              # a run copy (engine_copy.py) unless named by ROSTRUM3D_STYLIZED
        from .engine_copy import copy_of
        plugins.append(stylized_dir() if os.environ.get("ROSTRUM3D_STYLIZED") else copy_of(stylized_dir(), "3d-stylized"))
    env = dict(os.environ if base is None else base)
    env["PATH"] = os.pathsep.join([str(d) for d in dirs] + [env.get("PATH", "")])
    ours = [str(p) for p in plugins]                  # ours first, then whatever the person already set (no duplicates)
    theirs = [p for p in env.get("PXR_PLUGINPATH_NAME", "").split(os.pathsep) if p and p not in ours]
    env["PXR_PLUGINPATH_NAME"] = os.pathsep.join(ours + theirs)
    # the Rostrum MaterialX block library (a material's blocks, ENGINE_CONTRACT § Blocks): USD's MaterialX reader and
    # Storm's MaterialX code find our nodedefs there
    libs = [str(REPO / "apps" / "3d" / "core" / "mtlx"), str(REPO / "apps" / "3d" / "stylized" / "mtlx")]
    theirs = [p for p in env.get("PXR_MTLX_PLUGIN_SEARCH_PATHS", "").split(os.pathsep) if p and p not in libs]
    env["PXR_MTLX_PLUGIN_SEARCH_PATHS"] = os.pathsep.join(libs + theirs)
    env.setdefault("CYCLES_DEVICE", "OPTIX")
    return env
