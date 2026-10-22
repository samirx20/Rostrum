"""Where Rostrum2D finds its parts: every setup assumption in one place, for the checkout and the installed app alike.

Each lookup is an ordered list, first hit wins:
    engine        ROSTRUM2D_ENGINE  ·  <app>/engine/rostrum*.exe  ·  checkout apps/2d/engine/target/{release,agent}/
    ffmpeg        ROSTRUM_FFMPEG_DIR/<name>  ·  <app>/ffmpeg/<name>  ·  <app>/<name>  ·  PATH   (ffmpeg, ffprobe; LGPL)
    fonts         ROSTRUM2D_FONTS  ·  fonts/ beside the engine  ·  checkout apps/2d/engine/fonts   (the engine's own order)
    Rostrum3D     ROSTRUM3D_CORE (only it, when set)  ·  <suite>/Rostrum3D/engine/rostrum3d-core.exe  ·  checkout apps/3d/core/.build/install/
<app> is the installed app's folder: ROSTRUM2D_HOME, else the folder of the frozen program (the installer's bundle);
none in a checkout. <suite> is the folder holding the installed apps (<app>'s parent).

Folders for the person's things:
    projects      ROSTRUM2D_PROJECTS, else Documents/Rostrum2D (made on first use)
    user data     ROSTRUM_DATA, else ~/.rostrum: logs/, cache/, models/
    settings      <user data>/2d/settings.json (plain JSON: recent projects …)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[2]                     # apps/2d (also inside the installed bundle)
REPO = CHECKOUT.parents[1]
EXE = ".exe" if os.name == "nt" else ""


def _env_path(name: str) -> Path | None:
    v = os.environ.get(name)
    return Path(v) if v else None


def app_dir() -> Path | None:
    """The installed app's folder, or None when running from a checkout."""
    if _env_path("ROSTRUM2D_HOME"):
        return _env_path("ROSTRUM2D_HOME")
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None


def _first(candidates) -> Path | None:
    return next((p for p in candidates if p is not None and p.is_file()), None)


# ---- the engine ---------------------------------------------------------------------------------------------------
def engine_candidates() -> list[Path]:
    out = [_env_path("ROSTRUM2D_ENGINE")] if _env_path("ROSTRUM2D_ENGINE") else []
    if app_dir():
        out += sorted((app_dir() / "engine").glob(f"rostrum*{EXE}"))
    for profile in ("release", "agent"):
        out += sorted((CHECKOUT / "engine" / "target" / profile).glob(f"rostrum*{EXE}"))
    return out


def engine_exe() -> Path | None:
    """The 2D engine program (ROSTRUM2D_ENGINE as given, else the first that exists); None = not built or installed."""
    if _env_path("ROSTRUM2D_ENGINE"):
        return _env_path("ROSTRUM2D_ENGINE")
    return _first(engine_candidates())


# ---- ffmpeg -------------------------------------------------------------------------------------------------------
def ffmpeg(name: str = "ffmpeg") -> str:
    """The ffmpeg (or ffprobe) program to run: the bundled LGPL build beside the app first, then PATH. Fails loudly."""
    places = [_env_path("ROSTRUM_FFMPEG_DIR")]
    if app_dir():
        places += [app_dir() / "ffmpeg", app_dir()]
    hit = _first(p / f"{name}{EXE}" for p in places if p is not None)
    found = str(hit) if hit else shutil.which(name)
    if not found:
        raise RuntimeError(f"{name} was not found: put it in the app's ffmpeg folder, on PATH, or set ROSTRUM_FFMPEG_DIR")
    return found


# ---- fonts --------------------------------------------------------------------------------------------------------
def fonts_dir() -> Path | None:
    """The app's fonts folder (the families a 2D layer can name), in the engine's own order; None when there is none."""
    exe = engine_exe()
    for d in (_env_path("ROSTRUM2D_FONTS"), exe.parent / "fonts" if exe else None, CHECKOUT / "engine" / "fonts"):
        if d is not None and d.is_dir():
            return d
    return None


# ---- folders ------------------------------------------------------------------------------------------------------
def documents_dir() -> Path:
    """The person's Documents folder where Windows keeps it (it may be moved, e.g. into OneDrive); else ~/Documents."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:   # 5 = CSIDL_PERSONAL
            return Path(buf.value)
    return Path.home() / "Documents"


def projects_dir() -> Path:
    """Where New puts projects: ROSTRUM2D_PROJECTS, else <Documents>/Rostrum2D."""
    d = _env_path("ROSTRUM2D_PROJECTS") or documents_dir() / "Rostrum2D"
    d.mkdir(parents=True, exist_ok=True)
    return d


def data_dir() -> Path:
    """The person's Rostrum data (logs, caches, models): ROSTRUM_DATA, else ~/.rostrum."""
    return _env_path("ROSTRUM_DATA") or Path.home() / ".rostrum"


def logs_dir() -> Path:
    return data_dir() / "logs"


def cache_dir(name: str) -> Path:
    return data_dir() / "cache" / name


def models_dir() -> Path:
    return data_dir() / "models"


# ---- the user settings file ---------------------------------------------------------------------------------------
def settings_path() -> Path:
    return data_dir() / "2d" / "settings.json"


def read_settings() -> dict:
    """The settings file as a dict ({} when there is none). A damaged file fails loudly: it is not overwritten."""
    p = settings_path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RuntimeError(f"the settings file {p} can't be read ({e}); fix or delete it") from e


def write_settings(data: dict) -> None:
    from rostrum_core.storage import write_atomic
    write_atomic(settings_path(), json.dumps(data, indent=1, ensure_ascii=False))


# ---- the other apps -----------------------------------------------------------------------------------------------
def rostrum3d_exe() -> Path | None:
    """ROSTRUM3D_CORE when set (only that: a path that isn't there = not installed), else the installed suite's, else the
    checkout's build."""
    if _env_path("ROSTRUM3D_CORE"):
        return _first([_env_path("ROSTRUM3D_CORE")])
    suite = app_dir().parent if app_dir() else None
    return _first([
                   suite / "Rostrum3D" / "engine" / f"rostrum3d-core{EXE}" if suite else None,
                   REPO / "apps" / "3d" / "core" / ".build" / "install" / f"rostrum3d-core{EXE}"])


def has_rostrum3d() -> bool:
    """Rostrum3D is installed here (its engine is found): 3D render layers are offered only then."""
    return rostrum3d_exe() is not None
