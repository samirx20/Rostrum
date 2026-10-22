"""Builds the folder the installer packs: a self-contained Rostrum with no system Python, uv or dev venv needed.

    python tools/release/bundle.py --out <folder> [--apps 2d sound] [--engines <checkout with built engines>]

The installed folder mirrors this repo's layout (shared/core/rostrum_core, apps/2d/python/rostrum2d,
apps/2d/engine/target/agent/rostrum2d-render.exe, apps/2d/guides …), so every "where is my engine / guides / fonts"
lookup in the code works unchanged. Python is python.org's embeddable build (runtime/python); its ._pth file puts our
packages on the path. Third-party wheels are split: what every app needs (Qt, the shared packages' needs) goes to
runtime/python/Lib/site-packages, what only one app needs to apps/<app>/site-packages. Each top folder is one
installer component: runtime (shared, always), apps/2d, apps/sound.
Build-time tools only: uv (installs the wheels) and this checkout. Fails loudly on any missing piece.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import extras
import icons
from qt_trim import trim

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CACHE = Path.home() / ".rostrum" / "release-cache"
EMBED = CACHE / "downloads" / "python-embed" / "python-3.12.10-embed-amd64.zip"
SAMPLES = Path.home() / ".rostrum" / "samples"
OURS = {"rostrum-core", "rostrum-gui", "rostrum-paint", "rostrum2d", "rostrum-sound"}
SKIP = shutil.ignore_patterns("__pycache__", "tests", "*.egg-info", "*.pyc", ".pytest_cache")

# One row per piece: (installer component, wheel specs from this repo, folders copied as they are).
SHARED = ("runtime", ["shared/core[mcp]", "shared/gui-kit", "shared/painting-kit"],
          ["shared/core/rostrum_core", "shared/gui-kit/rostrum_gui", "shared/gui-kit/qml",
           "shared/painting-kit/rostrum_paint", "LICENSE", "ATTRIBUTIONS.md"])
APPS = {
    "2d": ("apps/2d", ["apps/2d/python[mcp,io,render3d]"],
           ["apps/2d/python/rostrum2d", "apps/2d/screen/main.py", "apps/2d/screen/screen2d", "apps/2d/screen/qml",
            "apps/2d/guides", "apps/2d/engine/fonts", "apps/2d/engine/DEPENDENCIES.md"],
           ["apps/2d/engine/target/agent/rostrum2d-render.exe", "apps/2d/engine/target/agent/rostrum2d_stamp.dll"]),
    "sound": ("apps/sound", ["apps/sound/python[listen,cleanup,mcp]"],
              ["apps/sound/python/rostrum_sound", "apps/sound/screen/main.py", "apps/sound/screen/screensound",
               "apps/sound/screen/qml", "apps/sound/guides", "apps/sound/MODELS.md"],
              ["apps/sound/engine/target/agent/rostrum-sound.exe"]),
}
PTH = ["python312.zip", ".", "Lib\\site-packages", "..\\..\\shared\\core", "..\\..\\shared\\gui-kit",
       "..\\..\\shared\\painting-kit", "..\\..\\apps\\2d\\python", "..\\..\\apps\\2d\\site-packages",
       "..\\..\\apps\\sound\\python", "..\\..\\apps\\sound\\site-packages", "import site"]


def fail(msg: str):
    sys.exit(f"FAIL: bundle: {msg}")


def copy(rel: str, src_root: Path, dst_root: Path):
    src, dst = src_root / rel, dst_root / rel
    if not src.exists():
        fail(f"{src} is missing")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=SKIP, dirs_exist_ok=True) if src.is_dir() else shutil.copy2(src, dst)


def wheels(specs: list[str], target: Path):
    """Install the specs (and everything they need, from the shared uv cache) into target, then drop our own packages:
    those ship as source in the repo layout."""
    local = [str(REPO / s) for s in ("shared/core", "shared/gui-kit", "shared/painting-kit")]
    cmd = ["uv", "pip", "install", "--quiet", "--target", str(target), "--python", sys.executable,
           *[str(REPO / s.split("[")[0]) + ("[" + s.split("[")[1] if "[" in s else "") for s in specs], *local]
    if subprocess.run(cmd).returncode:
        fail(f"installing {specs} failed (uv's lines above say why)")
    for name, files in dists(target).items():
        if name in OURS:
            remove(target, files)
    shutil.rmtree(target / "bin", ignore_errors=True)


def dists(site: Path) -> dict[str, list[str]]:
    """Every installed distribution in a folder -> its files (from its RECORD)."""
    out = {}
    for rec in site.glob("*.dist-info/RECORD"):
        meta = (rec.parent / "METADATA").read_text(encoding="utf-8", errors="replace")
        name = next(l.split(":", 1)[1].strip() for l in meta.splitlines() if l.startswith("Name:"))
        out[name.lower().replace("_", "-").replace(".", "-")] = [l.split(",")[0] for l in rec.read_text(
            encoding="utf-8").splitlines() if l.strip()]
    return out


def remove(site: Path, files: list[str]):
    for f in files:
        (site / f).unlink(missing_ok=True)
    for d in sorted({(site / f).parent for f in files}, key=lambda p: -len(p.parts)):
        if d != site and d.is_dir() and not any(d.iterdir()):
            d.rmdir()


def move(src: Path, dst: Path, files: list[str]):
    for f in files:
        if (src / f).exists():
            (dst / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src / f, dst / f)
    remove(src, files)


def notices(app: str, stage: Path, site: Path):
    """apps/<app>/notices.json (the About / Licences screen) and NOTICES.txt (full texts) for what this app ships."""
    folder = stage / APPS[app][0]
    deps = [str(REPO / APPS[app][0] / "engine" / "DEPENDENCIES.md")]
    cmd = [sys.executable, str(HERE / "notices.py"), "--app", app, "--attributions", str(REPO / "ATTRIBUTIONS.md"),
           "--site-packages", str(site), "--site-packages", str(folder / "site-packages"),
           *[x for d in deps for x in ("--engine-deps", d)], "--out", str(folder / "notices.json"),
           "--text", str(folder / "NOTICES.txt")]
    if subprocess.run(cmd).returncode:
        fail(f"the notices for {app} could not be made (a GPL item, or the lines above)")


def size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--out", required=True, type=Path)
    a.add_argument("--apps", nargs="+", default=list(APPS), choices=list(APPS))
    a.add_argument("--engines", type=Path, default=REPO, help="checkout whose apps/*/engine/target holds built engines")
    args = a.parse_args()
    stage, work = args.out / "stage", args.out / "work"
    for d in (stage, work):
        shutil.rmtree(d, ignore_errors=True)
    if not EMBED.is_file():
        fail(f"the embeddable Python is missing: {EMBED} (python.org, python-3.12.10-embed-amd64.zip)")

    py = stage / "runtime" / "python"
    zipfile.ZipFile(EMBED).extractall(py)
    (py / "python312._pth").write_text("\n".join(PTH) + "\n", encoding="utf-8")
    site = py / "Lib" / "site-packages"
    wheels(SHARED[1], site)
    saved = trim(site / "PySide6")
    shared = set(dists(site))
    per_app = {}
    for app in args.apps:
        wheels(APPS[app][1], work / app)
        per_app[app] = {n: f for n, f in dists(work / app).items() if n not in shared}
    for name in set.intersection(*(set(d) for d in per_app.values())) if len(per_app) > 1 else ():
        for app, d in per_app.items():          # needed by every chosen app: install once, in the runtime
            move(work / app, site, d.pop(name)) if app == args.apps[0] else remove(work / app, d.pop(name))
    for app, d in per_app.items():
        for files in d.values():
            move(work / app, stage / APPS[app][0] / "site-packages", files)

    for rel in SHARED[2]:
        copy(rel, REPO, stage)
    for app in args.apps:
        for rel in APPS[app][2]:
            copy(rel, REPO, stage)
        for rel in APPS[app][3]:
            copy(rel, args.engines, stage)
    try:                                         # 2D's LGPL FFmpeg; the C++ runtime beside every engine
        if "2d" in args.apps:
            extras.ffmpeg(stage)
        extras.crt(stage, sorted({Path(rel).parent for app in args.apps for rel in APPS[app][3]}))
    except extras.Missing as e:
        fail(str(e))
    copy("tools/release/rostrum.pyw", REPO, stage)
    shutil.move(stage / "tools" / "release" / "rostrum.pyw", py.parent / "rostrum.pyw")
    shutil.rmtree(stage / "tools")
    icons.main(stage / "runtime" / "icons")
    if (SAMPLES / "lull").is_dir():
        shutil.copytree(SAMPLES / "lull", stage / "runtime" / "samples" / "lull", ignore=SKIP)
    else:
        fail(f"the sample project is missing: {SAMPLES / 'lull'}")
    shutil.rmtree(work)
    for app in args.apps:
        notices(app, stage, site)

    report = {"runtime": size(stage / "runtime"), **{app: size(stage / APPS[app][0]) for app in args.apps},
              "total": size(stage), "python_site_packages": size(site), "qt_trimmed": saved,
              "shared_dists": sorted(dists(site)), **{f"{app}_dists": sorted(per_app[app]) for app in args.apps}}
    (args.out / "bundle-report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    mb = lambda n: f"{n / 2**20:,.0f} MB"  # noqa: E731
    print("bundle ready:", stage, "| runtime", mb(report["runtime"]),
          *[f"| {app} {mb(report[app])}" for app in args.apps], "| total", mb(report["total"]))


if __name__ == "__main__":
    main()
