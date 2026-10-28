"""Install, list and verify the sample packs (recorded instruments, drum kits, sound effects).

    python -m rostrum_sound.packs list
    python -m rostrum_sound.packs install <pack | all-instruments | all>
    python -m rostrum_sound.packs verify <pack | all-instruments | all>

A pack installs into `<assets>/sounds/<pack>/` (settings.assets_dir; ROSTRUM_ASSETS_DIR moves it). Each download is checked
against its pinned fingerprint before it is extracted or kept (a mismatch deletes it and fails loudly); only the files
the library needs are extracted; each installed file's sha256 and size go into `<assets>/assets.json`, the shape the
experiment used. The same install is the `run_model_install` tool (pack names are accepted there) and the Library's
"missing pack" message. Packs already on the machine are never downloaded again.
"""
from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rostrum_core import RostrumError, codes
from rostrum_core.storage import write_atomic

from . import packs_catalog as cat
from . import packs_fetch as fetch
from . import settings

WORKERS = 4
Note = Callable[[str], None]


def sounds_dir() -> Path:
    return settings.assets_dir() / "sounds"


def _record_path() -> Path:
    return settings.assets_dir() / "assets.json"


def _records() -> dict:
    p = _record_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _short(licence: str) -> str:
    return licence.split(":")[0].split(" (")[0].strip()


def next_step(name: str) -> str:
    """The exact next step for a missing pack, the same words everywhere."""
    return f'Install it: python -m rostrum_sound.packs install {name} (an agent: run_model_install with "{name}")'


def state(name: str) -> tuple[str, int]:
    """("installed" | "incomplete" | "missing", bytes on disk) from assets.json and a look at each file's size."""
    rec = _records().get(f"sounds:{name}")
    if not rec:
        return "missing", 0
    root, total, whole = sounds_dir() / name, 0, True
    for f in rec["files"]:
        p = root / f["path"]
        ok = p.is_file() and p.stat().st_size == f["size"]
        whole &= ok
        total += f["size"] if ok else 0
    gen_ok = all((root / rel).is_file() for _, rel in cat.generated(name))
    return ("installed" if whole and gen_ok else "incomplete"), total


def listing() -> list[dict]:
    rows = []
    for name, p in cat.catalog().items():
        st, size = state(name)
        rows.append({"pack": name, "group": p["group"], "state": st, "bytes": size, "licence": _short(p["license"]),
                     "title": p["title"], "credit": p.get("credit"), "install": None if st == "installed" else next_step(name)})
    return rows


def _expand(what: str, where: str) -> list[str]:
    if what == "all":
        return cat.names()
    if what == "all-instruments":
        return cat.names("instruments")
    cat.pack(what, where)
    return [what]


def _items(p: dict) -> list[dict]:
    return p.get("direct") or (cat.files(p["id"]) if p.get("files") else [])


def _lfs(path: Path, what: str) -> None:
    if path.stat().st_size < 512 and path.read_bytes().startswith(b"version https://git-lfs"):
        path.unlink()
        raise fetch.fail(what, "came back as a Git LFS pointer, not the recording; it was deleted and nothing was installed")


def _fetch_item(item: dict, dest: Path, work: Path, i: int, note: Note | None) -> None:
    if dest.is_file() and (("gitSha1" in item and fetch.git_sha1_of(dest) == item["gitSha1"])
                           or ("sha256" in item and fetch.sha256_of(dest) == item["sha256"])):
        return                                                  # an interrupted install resumes: this one is whole
    tmp = work / f"f{i}"
    fetch.download(item["url"], tmp, item["path"], note)
    _lfs(tmp, item["path"])
    fetch.check(tmp, item, item["path"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp), dest)


def _install_one(p: dict, work: Path, note: Note | None) -> list[str]:
    """Download, verify and place pack `p`'s files; returns their paths inside the pack folder."""
    root = sounds_dir() / p["id"]
    root.mkdir(parents=True, exist_ok=True)
    src = p.get("zip") or p.get("archive")
    if src:
        kind = "zip" if p.get("zip") else ("7z" if src["url"].endswith(".7z") else "tar")
        archive = work / "archive"
        if note:
            note(f"{p['id']}: downloading ({src['bytes'] / 1e6:.0f} MB)")
        fetch.download(src["url"], archive, p["id"], note)
        fetch.check(archive, {"sha256": src["sha256"]}, p["id"])       # BEFORE anything is extracted
        out = work / "out"
        out.mkdir()
        got = fetch.extract(archive, kind, src.get("extract", fetch.AUDIO), out)
        if not got:
            raise fetch.fail(p["id"], "was checked but holds none of the files the library needs")
        for rel in got:
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(out / rel), dest)
        return got
    items = _items(p)
    done = [0]

    def one(ix):
        i, item = ix
        _fetch_item(item, root / item["path"], work, i, note)
        done[0] += 1
        if note and done[0] % 25 == 0:
            note(f"{p['id']}: {done[0]} of {len(items)} files")
        return item["path"]
    with ThreadPoolExecutor(WORKERS) as pool:
        return list(pool.map(one, enumerate(items)))


def install(name: str, note: Note | None = None) -> dict:
    """Install one pack; {pack, folder, files, installed: False when it was already whole}."""
    p = cat.pack(name, "pack install")
    root = sounds_dir() / name
    if state(name)[0] == "installed":
        return {"pack": name, "folder": str(root), "installed": False, "credit": p.get("credit")}
    work = settings.assets_dir() / f".install-{name}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    try:
        paths = _install_one(p, work, note)
        for repo_file, rel in cat.generated(name):                       # the SFZ files Rostrum made for this pack
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo_file, root / rel)
        files = [{"path": rel, "sha256": fetch.sha256_of(root / rel), "size": (root / rel).stat().st_size} for rel in sorted(paths)]
        rec = _records()
        rec[f"sounds:{name}"] = {"kind": "sound", "entry": f"sounds/{name}", "license": p["license"], "page": p["page"], "files": files}
        write_atomic(_record_path(), json.dumps(rec, indent=2))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {"pack": name, "folder": str(root), "installed": True, "files": len(files), "credit": p.get("credit")}


def refresh_generated() -> list[str]:
    """Bring Rostrum's own SFZ files in every installed pack up to the repo's copy (an update that changes a kit's map
    or pans reaches packs installed before it); the engine reads them on its next start. Returns what was rewritten."""
    done = []
    for name in _records():
        name = name.split(":", 1)[1] if name.startswith("sounds:") else None
        root = sounds_dir() / name if name else None
        for repo_file, rel in (cat.generated(name) if root and root.is_dir() else []):
            dst = root / rel
            if dst.is_file() and dst.read_bytes() != repo_file.read_bytes():
                shutil.copyfile(repo_file, dst)
                done.append(f"{name}/{rel}")
    return done


def install_many(what: str, note: Note | None = None) -> list[dict]:
    return [install(n, note) for n in _expand(what, "pack install")]


def verify(name: str) -> dict:
    """Check every installed file of a pack against the fingerprint recorded when it was installed."""
    cat.pack(name, "pack verify")
    rec = _records().get(f"sounds:{name}")
    if not rec:
        return {"pack": name, "ok": False, "problems": [f"not installed. {next_step(name)}"]}
    root, bad = sounds_dir() / name, []
    for f in rec["files"]:
        p = root / f["path"]
        if not p.is_file():
            bad.append(f"missing: {f['path']}")
        elif p.stat().st_size != f["size"] or fetch.sha256_of(p) != f["sha256"]:
            bad.append(f"changed: {f['path']}")
    for repo_file, rel in cat.generated(name):
        if not (root / rel).is_file() or (root / rel).read_bytes() != repo_file.read_bytes():
            bad.append(f"missing or changed: {rel} (Rostrum's own SFZ; install the pack again to restore it)")
    return {"pack": name, "ok": not bad, "files": len(rec["files"]), "problems": bad}


def credit_lines(report: dict) -> list[str]:
    """The credit lines of a render report (the engine's `credits`: a line, or {pack, credit}), once each, in order.
    CC-BY instruments need them wherever the sound goes; the manifest and the render reply carry them."""
    out = []
    for c in report.get("credits") or []:
        line = c if isinstance(c, str) else c.get("credit") or credit(c.get("pack", "")) or ""
        if line and line not in out:
            out.append(line)
    return out


def credit(pack: str) -> str | None:
    return cat.credit(pack)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in ("list", "install", "verify"):
        print(__doc__)
        return 0 if not argv or argv[0] in ("-h", "--help") else 2
    try:
        if argv[0] == "list":
            for r in listing():
                mb = f"{r['bytes'] / 1e6:.0f} MB" if r["bytes"] else "-"
                print(f"{r['pack']:20} {r['state']:11} {mb:>8}  {r['group']:12} {r['licence']}" + (f"  credit: {r['credit']}" if r["credit"] else ""))
            return 0
        if len(argv) < 2:
            print(f"Error: packs {argv[0]}: say which pack. Accepted: all-instruments, all, {', '.join(cat.names())}.", file=sys.stderr)
            return 2
        if argv[0] == "install":
            for r in install_many(argv[1], lambda s: print(s, flush=True)):
                print(f"{r['pack']}: " + (f"installed in {r['folder']} (fingerprints checked)" if r["installed"] else "already installed"))
            return 0
        failed = 0
        for n in _expand(argv[1], "pack verify"):
            r = verify(n)
            print(f"{n}: " + ("ok, " + f"{r['files']} files match" if r["ok"] else "; ".join(r["problems"][:5])))
            failed += not r["ok"]
        return 1 if failed else 0
    except RostrumError as e:
        print(e.line(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
