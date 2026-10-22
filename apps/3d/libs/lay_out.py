"""Lay out Rostrum3D's one runtime library folder from the libraries already downloaded for the proofs.

    python -I apps\\3d\\libs\\lay_out.py [--dest DIR] [--bundle DIR] [--cycles DIR] [--stylized DIR] [--check]

Nothing is downloaded. Files are copied only when missing or different (size / time), so a re-run takes seconds.
`--check` lists what would be copied and the size, and copies nothing. Any missing file or folder stops with exit 1.

The folder (VERSION below is also the folder name; rostrum3d/runtime.py has the same name):

    runtime\\bin\\            the DLLs the engine really loads (measured), plus a small fallback list
    runtime\\usd\\lib\\       usd_ms.dll + usd\\ (plugInfo.json and resources of every USD / Hydra plug-in)
    runtime\\usd\\plugin\\usd\\ Storm, image readers, preview-surface shaders (usd_ms.dll finds ..\\plugin\\usd too)
    runtime\\hydra\\cycles\\  Cycles' install root: hydra\\ (hdCycles.dll + plugInfo), lib\\ (GPU kernels), source\\, license\\
    runtime\\hydra\\rostrum\\ our stylized plug-in (hdRostrum.dll, plugInfo.json, shaders)
    sdk\\                    what apps\\3d\\core needs to build, same layout as the bundle (CMake's BUNDLE = sdk)
    VERSION.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

VERSION = "5.2.2-cycles-a456b76-r1"   # r1 (H22): Cycles' Hydra plug-in with cycles-rostrum-lights.patch
BUNDLE_TAG, BUNDLE_COMMIT, CYCLES_COMMIT = "v5.2.2", "60d6e96", "a456b76"
CYCLES_INSTALL = "install-r1"         # made by build_cycles.bat (the proof's unpatched build is install\)
CYCLES_PATCH = "cycles-rostrum-lights.patch"
REPO = Path(__file__).resolve().parents[3]
DEFAULT_DEST = Path.home() / ".rostrum" / "libs" / "3d" / VERSION
DEFAULT_BUNDLE = REPO / "proofs" / "3d-product" / ".build" / "cycles" / "lib" / "windows_x64"
DEFAULT_CYCLES = REPO / "proofs" / "3d-product" / ".build" / "cycles"
DEFAULT_STYLIZED = REPO / "proofs" / "3d-stylized" / ".build" / "install"

# DLLs measured as loaded by rostrum3d-core (Storm, Cycles on OptiX, stylized, pick): "bundle folder\bin" -> names.
LOADED = {
    "MaterialX": ["MaterialXCore", "MaterialXFormat", "MaterialXGenGlsl", "MaterialXGenMsl", "MaterialXGenShader", "MaterialXRender"],
    "OpenImageIO": ["OpenImageIO", "OpenImageIO_Util"],
    "aom": ["aom"],
    "dpcpp": ["sycl8", "ur_loader", "ur_win_proxy_loader"],
    "embree": ["embree4"],
    "epoxy": ["epoxy-0"],
    "imath": ["Imath"],
    "opencolorio": ["OpenColorIO_2_5"],
    "openexr": ["Iex", "IlmThread", "OpenEXR", "OpenEXRCore"],
    "openimagedenoise": ["OpenImageDenoise", "OpenImageDenoise_core", "OpenImageDenoise_device_cuda"],
    "openjph": ["openjph.0.25"],
    "openvdb": ["openvdb"],
    "tbb": ["tbb12", "tbbmalloc"],
}
# Fallbacks that were not loaded on this laptop but would be on others, taken from Cycles' install folder (small):
#  - OpenImageDenoise_device_cpu: denoising on a machine without an NVIDIA card (the CUDA one is only loaded with one).
#  - the Visual C++ runtime: a clean Windows without the redistributable would otherwise fail to start.
# python313.dll is needed (usd_ms.dll links it) and is also taken from there. Anything with "ffmpeg" never comes in.
FROM_CYCLES = ["python313", "OpenImageDenoise_device_cpu", "vcruntime140", "vcruntime140_1", "msvcp140", "msvcp140_1",
               "msvcp140_2", "msvcp140_atomic_wait", "msvcp140_codecvt_ids", "concrt140"]

# What apps\3d\core\CMakeLists.txt names (include folders and .lib files), relative to the bundle.
SDK_DIRS = ["usd/include", "tbb/include", "epoxy/include", "python/313/include", "python/313/libs", "OpenImageIO/include",
            "imath/include", "openexr/include", "fmt/include", "opencolorio/include"]
SDK_FILES = ["usd/lib/usd_ms.lib", "tbb/lib/tbb.lib", "tbb/lib/tbb12.lib", "epoxy/lib/epoxy.lib", "OpenImageIO/lib/OpenImageIO.lib",
             "OpenImageIO/lib/OpenImageIO_Util.lib", "opencolorio/lib/OpenColorIO.lib"]

SKIP_DIRS = {"python", "__pycache__"}
SKIP_SUFFIX = {".pyc", ".h", ".hpp"}


class Missing(Exception):
    pass


def need(path: Path) -> Path:
    if not path.exists():
        raise Missing(f"missing: {path}")
    return path


def walk(src: Path, dst: Path, skip_dirs=(), skip_suffix=()):
    """(source, destination) for every file under src."""
    need(src)
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() not in skip_suffix and "ffmpeg" not in f.lower():
                yield p, dst / p.relative_to(src)


def plan(bundle: Path, cycles: Path, stylized: Path, dest: Path) -> list[tuple[Path, Path]]:
    jobs: list[tuple[Path, Path]] = []
    rt, install = dest / "runtime", cycles / CYCLES_INSTALL
    for folder, names in LOADED.items():
        jobs += [(need(bundle / folder / "bin" / f"{n}.dll"), rt / "bin" / f"{n}.dll") for n in names]
    jobs += [(need(install / f"{n}.dll"), rt / "bin" / f"{n}.dll") for n in FROM_CYCLES]
    # usd_ms.dll finds its plug-ins in a folder called "usd" right next to itself (usd\lib\usd_ms.dll + usd\lib\usd\),
    # so that relative layout is kept and no PXR_PLUGINPATH_NAME entry is needed for the USD / Hydra / Storm plug-ins.
    jobs.append((need(bundle / "usd" / "lib" / "usd_ms.dll"), rt / "usd" / "lib" / "usd_ms.dll"))
    jobs += walk(bundle / "usd" / "lib" / "usd", rt / "usd" / "lib" / "usd", SKIP_DIRS, SKIP_SUFFIX)
    # ...and in ..\plugin\usd: Storm (hdStorm), the image readers (hioOiio, hioOpenEXR, hioAvif), the preview
    # surface's shader definitions (usdShaders) and sdrGlslfx. Without them Storm is "not installed".
    jobs += walk(need(bundle / "usd" / "plugin" / "usd"), rt / "usd" / "plugin" / "usd", SKIP_DIRS, SKIP_SUFFIX)
    # Cycles looks for lib\ (GPU kernels) and source\ next to hydra\ (its plugInfo resource path is "../../" from Root).
    # The standalone cycles.exe, examples, python, usd headers and the copies of dlls in install\ stay out.
    cy = rt / "hydra" / "cycles"
    jobs += walk(need(install / "hydra"), cy / "hydra")
    for sub in ("lib", "source", "license"):
        jobs += walk(install / sub, cy / sub)
    jobs += walk(stylized, rt / "hydra" / "rostrum")
    for d in SDK_DIRS:
        jobs += walk(bundle / d, dest / "sdk" / d)
    jobs += [(need(bundle / f), dest / "sdk" / f) for f in SDK_FILES]
    return jobs


def differs(src: Path, dst: Path) -> bool:
    if not dst.exists():
        return True
    a, b = src.stat(), dst.stat()
    return a.st_size != b.st_size or int(a.st_mtime) != int(b.st_mtime)


# --- a small reader of a DLL's import table, to prove no DLL needs one we left out ---
def imports(path: Path) -> list[str]:
    data = path.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec, optsize = struct.unpack_from("<H", data, pe + 6)[0], struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    plus = struct.unpack_from("<H", data, opt)[0] == 0x20B
    import_rva = struct.unpack_from("<I", data, opt + (120 if plus else 104))[0]
    secs = [struct.unpack_from("<IIII", data, opt + optsize + 40 * i + 8) for i in range(nsec)]   # vsize, vaddr, rawsize, rawptr

    def off(rva):
        for vsize, vaddr, _, raw in secs:
            if vaddr <= rva < vaddr + max(vsize, 1):
                return raw + rva - vaddr
        return None

    out, at = [], off(import_rva) if import_rva else None
    while at is not None:
        name_rva = struct.unpack_from("<I", data, at + 12)[0]
        if not name_rva:
            break
        o = off(name_rva)
        out.append(data[o:data.index(b"\0", o)].decode("ascii"))
        at += 20
    return out


def import_gaps(dest: Path) -> list[str]:
    """Every DLL in runtime\\ whose imports are neither in the set nor in Windows."""
    rt = dest / "runtime"
    have = {p.name.lower() for p in rt.rglob("*.dll")}
    system = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    gaps = []
    for dll in sorted(rt.rglob("*.dll")):
        for name in imports(dll):
            n = name.lower()
            if n not in have and not n.startswith(("api-ms-", "ext-ms-")) and not (system / name).exists():
                gaps.append(f"{dll.name} needs {name}")
    return gaps


def git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    ap.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE, help="Blender lib\\windows_x64 folder")
    ap.add_argument("--cycles", type=Path, default=DEFAULT_CYCLES, help="Cycles folder that has install\\")
    ap.add_argument("--stylized", type=Path, default=DEFAULT_STYLIZED, help="our stylized plug-in install folder")
    ap.add_argument("--check", action="store_true", help="list what would be copied, copy nothing")
    a = ap.parse_args()
    try:
        jobs = plan(a.bundle, a.cycles, a.stylized, a.dest)
    except Missing as e:
        print(f"lay_out: {e}", file=sys.stderr)
        return 1
    total = sum(s.stat().st_size for s, _ in jobs)
    todo = [(s, d) for s, d in jobs if differs(s, d)]
    todo_size = sum(s.stat().st_size for s, _ in todo)
    print(f"{len(jobs)} files, {total / 2**20:.0f} MB in all; {len(todo)} to copy ({todo_size / 2**20:.0f} MB) into {a.dest}")
    if a.check:
        for s, d in todo:
            print(f"  {d.relative_to(a.dest)}  ({s.stat().st_size / 2**20:.2f} MB)")
        return 0
    for s, d in todo:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
    meta = {
        "version": VERSION,
        "bundle": {"source": "Blender lib-windows_x64", "tag": BUNDLE_TAG, "commit": BUNDLE_COMMIT},
        "cycles": {"commit": CYCLES_COMMIT, "install": CYCLES_INSTALL, "patch": CYCLES_PATCH},
        "stylized": {"source": str(REPO), "git_head": git_head()},
        "date": datetime.date.today().isoformat(),
        "files": len(jobs),
        "size_bytes": total,
    }
    (a.dest / "VERSION.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    gaps = import_gaps(a.dest)
    for g in gaps:
        print(f"lay_out: import gap: {g}", file=sys.stderr)
    print(f"done: {a.dest}")
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
