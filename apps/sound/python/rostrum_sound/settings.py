"""RostrumSound's one settings module: the person's settings (field data in settings_fields.py, kept as JSON at
<settings dir>/sound.json) and every place the app finds things on this machine (the engine program, the models,
the sound library, the cache, projects). Nothing else in the app assumes a folder.

Environment variables still win over the saved settings (agents and tests set them):
ROSTRUM_SETTINGS_DIR, ROSTRUM_SOUND_ENGINE, ROSTRUM_HOME, ROSTRUM_MODELS_DIR, ROSTRUM_ASSETS_DIR, ROSTRUM_CACHE_DIR,
ROSTRUM_PROJECTS_DIR, ROSTRUM_AUDIO_OUTPUT / _INPUT / _PERIOD_MS.

    settings.set("loudness", -16)            # checked like any field; a bad value is a loud RostrumError
    settings.engine_path(), settings.models_dir(), settings.audio_env()
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from rostrum_core import RostrumError, builds, codes, did_you_mean, userhome
from rostrum_core.cache import default_root
from rostrum_core.storage import write_atomic

from .settings_fields import DEFAULTS, FIELDS, MODELS, PROJECTS

FILE = "sound.json"
EXE = "rostrum-sound.exe" if os.name == "nt" else "rostrum-sound"
DEV_BUILD = Path(__file__).resolve().parents[2] / "engine" / "target"
AUDIO_ENV = {"output": "ROSTRUM_AUDIO_OUTPUT", "input": "ROSTRUM_AUDIO_INPUT", "buffer": "ROSTRUM_AUDIO_PERIOD_MS"}
_devices: dict | None = None
device_error = ""                    # why the last device list is empty (the page shows it)


def _env_path(var: str) -> Path | None:
    return Path(os.environ[var]) if os.environ.get(var) else None


def settings_dir() -> Path:
    """Every Rostrum settings file lives here (userlib/folders.py too). ROSTRUM_SETTINGS_DIR moves it; else
    userhome.home()/settings (~/.rostrum, or a scratch home for a scripted run)."""
    return _env_path("ROSTRUM_SETTINGS_DIR") or userhome.home() / "settings"


def _param(name: str):
    p = FIELDS.param(name)
    if p is None:
        names = [q.name for q in FIELDS.params]
        raise RostrumError(codes.BAD_ARGUMENT, "settings", name, "is not a setting", names, did_you_mean(name, names))
    return p


def load() -> dict:
    """The settings, each checked, with defaults for the ones never set."""
    f = settings_dir() / FILE
    if not f.is_file():
        return dict(DEFAULTS)
    try:
        saved = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, "settings", str(f), f"is not readable JSON ({e})",
                           hint="Fix or delete the file; deleting it puts every setting back to its default.") from e
    return {**DEFAULTS, **{k: _param(k).check(v, f"settings ({f})") for k, v in saved.items() if k in DEFAULTS}}


def save(values: dict):
    """Write all the settings at once (each checked first; written under a temporary name, then renamed)."""
    clean = {k: _param(k).check(v, "settings") for k, v in values.items()}
    with userhome.locked(settings_dir() / FILE):
        _write({**DEFAULTS, **clean})


def _write(values: dict):
    write_atomic(settings_dir() / FILE, json.dumps(values, indent=1))


def set(name: str, value):  # noqa: A001 (the API's name)
    """Change one setting: read, change and write under one lock, so two windows never undo each other."""
    new = _param(name).check(value, "settings")
    with userhome.locked(settings_dir() / FILE):
        _write({**load(), name: new})


def choices(name: str) -> list[dict]:
    """[{value, label}] a setting may take: the machine's devices for output / input, else its own choices."""
    if name in ("output", "input"):
        return [{"value": d, "label": d} for d in devices()[name + "s"]]
    return _param(name).choices() if _param(name).type == "choice" else []


def devices(refresh: bool = False) -> dict:
    """{"outputs": [...], "inputs": [...]} from `rostrum-sound midi`, asked once per process. Never raises: with
    no engine or a failed listing the lists are empty and `device_error` says why."""
    global _devices, device_error
    if _devices is None or refresh:
        try:
            r = subprocess.run([str(engine_path()), "midi"], capture_output=True, text=True, encoding="utf-8",
                               timeout=20)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip() or f"the engine ended with code {r.returncode}")
            got = json.loads(r.stdout)
            _devices, device_error = {"outputs": got.get("outputs", []), "inputs": got.get("inputs", [])}, ""
        except (RostrumError, OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as e:
            _devices, device_error = {"outputs": [], "inputs": []}, f"could not list the sound devices: {e}"
    return _devices


def install_root() -> Path | None:
    """Where the installed app lives: ROSTRUM_HOME, else the folder of a packaged app's program."""
    if os.environ.get("ROSTRUM_HOME"):
        return Path(os.environ["ROSTRUM_HOME"])
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else None


def engine_candidates() -> list[Path]:
    """Every place the engine program is looked for, in order. The one list: Team Sam's installer (S20) must put
    the engine at <install root>/engines/rostrum-sound.exe."""
    if os.environ.get("ROSTRUM_SOUND_ENGINE"):
        return [Path(os.environ["ROSTRUM_SOUND_ENGINE"])]
    chosen = load()["engine"]
    found = [Path(chosen)] if chosen else []
    if install_root():
        found.append(install_root() / "engines" / EXE)
    return found + [DEV_BUILD / p / EXE for p in ("release", "agent")]


def engine_path() -> Path:
    found = engine_candidates()
    dev = [p for p in found if DEV_BUILD in p.parents]        # a chosen or installed engine wins; the dev builds: newest
    if (p := next((p for p in found if p.is_file() and p not in dev), None)) or (
            p := builds.newest(dev, "the Sound engine")):
        return p
    raise RostrumError(codes.INTERNAL, "sound engine", "rostrum-sound", "is not installed", [str(p) for p in found],
                       "Reinstall RostrumSound, pick the program under Settings › Files › Sound engine program, or "
                       "(developers) build it: cargo build --profile agent -j 4 in apps/sound/engine.")


def _folder(var: str, name: str, default: Path) -> Path:
    return _env_path(var) or Path(load()[name] or default)


def models_dir() -> Path:
    return _folder("ROSTRUM_MODELS_DIR", "models", MODELS)


def projects_dir() -> Path:
    return _env_path("ROSTRUM_PROJECTS_DIR") or Path(load()["projects"] or userhome.output_dir("projects", PROJECTS))


def assets_dir() -> Path:
    return _env_path("ROSTRUM_ASSETS_DIR") or Path.home() / ".rostrum" / "assets"


def cache_dir() -> Path:
    return default_root()


def audio_env() -> dict:
    """The live player's device settings as the engine reads them (only those set; the environment's own win).
    The buffer is pinned only when the player takes over the speakers (exclusive); shared mode ignores it."""
    s = load()
    mine = {"output": s["output"], "input": s["input"], "buffer": s["buffer"] if s["exclusive"] else 0}
    return {var: os.environ.get(var) or str(mine[k]) for k, var in AUDIO_ENV.items() if os.environ.get(var) or mine[k]}


def engine_env() -> dict:
    """The environment to start an engine process with: this one plus the audio settings."""
    return {**os.environ, **audio_env()}


def models_disk_use() -> int:
    """Bytes the sound models take in the models folder (the clean-up models and the voice model)."""
    from .cleanup import models
    from .voice import model_dir
    folders = [models_dir() / m.id for m in (models.DFN3, models.UMXHQ)] + [model_dir()]
    return sum(f.stat().st_size for d in folders if d.is_dir() for f in d.rglob("*") if f.is_file())
