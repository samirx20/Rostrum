"""Where Rostrum2D finds its parts: every setup assumption in one place.

One root, <root>: this checkout, or the installed Rostrum folder, which has the same layout (tools/release/bundle.py
copies the repo's own paths: apps\\2d\\python, apps\\2d\\engine\\target\\agent\\rostrum2d-render.exe, runtime\\python …).
So every place below is the same in both; an environment variable, when set, is the only place looked at.
    engine        ROSTRUM2D_ENGINE  ·  <root>/apps/2d/engine/target/release/, then …/agent/   rostrum2d-render.exe
    ffmpeg        ROSTRUM_FFMPEG_DIR  ·  <root>/apps/2d/ffmpeg/   ffmpeg.exe, ffprobe.exe and their DLLs (LGPL build;
                  WebM, ProRes, video import). Never from PATH: the app runs only the FFmpeg it ships. MP4 needs none.
    fonts         ROSTRUM2D_FONTS  ·  <root>/apps/2d/engine/fonts
    Rostrum3D     ROSTRUM3D_CORE  ·  <root>/apps/3d/core/.build/install/rostrum3d-core.exe

Folders for the person's things:
    projects      ROSTRUM2D_PROJECTS, else Documents/Rostrum2D (made on first use)
    user data     ROSTRUM_DATA, else ~/.rostrum: logs/, cache/, models/
    settings      <user data>/2d/settings.json (plain JSON: recent projects …); with no ROSTRUM_DATA, in
                  rostrum_core.userhome.home(): ~/.rostrum, or a scratch home for a scripted run (never the person's)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[2]                          # <root>/apps/2d
ROOT = APP.parents[1]
EXE = ".exe" if os.name == "nt" else ""
# Every helper program (engine, ffmpeg, ffprobe) starts with this: the installed app runs under pythonw, which has no
# console, so without it each one would open its own black console window.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _env_path(name: str) -> Path | None:
    v = os.environ.get(name)
    return Path(v) if v else None


# ---- the engine ---------------------------------------------------------------------------------------------------
def engine_candidates() -> list[Path]:
    """Where the engine is looked for, in order: ROSTRUM2D_ENGINE alone when set, else the release then agent build."""
    if _env_path("ROSTRUM2D_ENGINE"):
        return [_env_path("ROSTRUM2D_ENGINE")]
    return [APP / "engine" / "target" / profile / f"rostrum2d-render{EXE}" for profile in ("release", "agent")]


def engine_exe() -> Path | None:
    """The 2D engine program (ROSTRUM2D_ENGINE as given, else the first that exists); None = not built or installed."""
    if _env_path("ROSTRUM2D_ENGINE"):
        return _env_path("ROSTRUM2D_ENGINE")
    return next((p for p in engine_candidates() if p.is_file()), None)


# ---- ffmpeg -------------------------------------------------------------------------------------------------------
def ffmpeg_dir() -> Path:
    """The folder holding the app's own LGPL FFmpeg: ROSTRUM_FFMPEG_DIR, else <root>/apps/2d/ffmpeg."""
    return _env_path("ROSTRUM_FFMPEG_DIR") or APP / "ffmpeg"


def ffmpeg(name: str = "ffmpeg") -> str:
    """The ffmpeg (or ffprobe) program to run, from ffmpeg_dir() only. Fails loudly, naming the missing file."""
    exe = ffmpeg_dir() / f"{name}{EXE}"
    if not exe.is_file():
        raise RuntimeError(f"{exe.name} is missing: it should be at {exe}. WebM and ProRes export and video import use "
                           "the FFmpeg that comes with Rostrum2D; reinstall Rostrum2D (in a checkout: put an LGPL FFmpeg "
                           "build there, or set ROSTRUM_FFMPEG_DIR). MP4, PNG and GIF export don't need it.")
    return str(exe)


# ---- fonts --------------------------------------------------------------------------------------------------------
def fonts_dir() -> Path | None:
    """The app's fonts folder (the families a 2D layer can name): ROSTRUM2D_FONTS, else <root>/apps/2d/engine/fonts;
    None when it isn't there."""
    d = _env_path("ROSTRUM2D_FONTS") or APP / "engine" / "fonts"
    return d if d.is_dir() else None


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
    """ROSTRUM_DATA's 2d/settings.json when set, else userhome.home()/2d/settings.json (scratch when scripted)."""
    if _env_path("ROSTRUM_DATA"):
        return data_dir() / "2d" / "settings.json"
    from rostrum_core import userhome
    return userhome.home() / "2d" / "settings.json"


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
    """ROSTRUM3D_CORE when set, else <root>/apps/3d/core/.build/install/rostrum3d-core.exe (the checkout's build, and
    where an installer carrying Rostrum3D puts it); None when that file isn't there."""
    exe = _env_path("ROSTRUM3D_CORE") or ROOT / "apps" / "3d" / "core" / ".build" / "install" / f"rostrum3d-core{EXE}"
    return exe if exe.is_file() else None


def has_rostrum3d() -> bool:
    """Rostrum3D is installed here (its engine is found): 3D render layers are offered only then."""
    return rostrum3d_exe() is not None
