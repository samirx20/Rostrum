"""Writes DEPENDENCIES.md: every crate the Sound engine builds with on Windows (name, version, licence), from Cargo.

    python apps/sound/engine/deps.py            # rewrite DEPENDENCIES.md
    python apps/sound/engine/deps.py --check    # only check: exit 1 on a GPL / AGPL / LGPL crate or a crate with no licence

Reads `cargo metadata` (no build). Dev-only crates are left out; build-time crates (cc, bindgen …) stay listed, as in
2D's list. A crate is refused when every choice its licence offers is GPL-family (Rust crates link statically, so LGPL
is refused too); "MIT OR GPL-2.0" is fine because we take MIT. The Licences screen reads the table (tools/release/notices.py).
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = "x86_64-pc-windows-msvc"
COPYLEFT = re.compile(r"\b(A?GPL|LGPL)", re.I)


def metadata() -> dict:
    out = subprocess.run(["cargo", "metadata", "--format-version", "1", "--locked", "--filter-platform", TARGET],
                         cwd=HERE, capture_output=True, text=True, encoding="utf-8")
    if out.returncode:
        sys.exit(f"cargo metadata failed:\n{out.stderr}")
    return json.loads(out.stdout)


def shipped(meta: dict) -> list[dict]:
    """The packages reachable from the engine through normal and build dependencies (not dev)."""
    pkgs = {p["id"]: p for p in meta["packages"]}
    nodes = {n["id"]: n for n in meta["resolve"]["nodes"]}
    seen, todo = set(), [meta["resolve"]["root"]]
    while todo:
        pid = todo.pop()
        if pid in seen:
            continue
        seen.add(pid)
        for d in nodes[pid]["deps"]:
            if any(k["kind"] != "dev" for k in d["dep_kinds"]):
                todo.append(d["pkg"])
    return sorted((pkgs[i] for i in seen), key=lambda p: (p["name"], p["version"]))


def refused(licence: str | None) -> bool:
    """True when no choice of the licence expression is permissive (or there is no licence at all)."""
    if not licence:
        return True
    choices = re.split(r"\s+OR\s+|/", licence.replace("(", "").replace(")", ""))
    return all(COPYLEFT.search(c) for c in choices)


def table(pkgs: list[dict]) -> str:
    local = [p for p in pkgs if p["source"] is None]
    rows = [p for p in pkgs if p["source"] is not None]
    lines = [
        "# RostrumSound engine: every crate it builds with (Windows target)",
        "",
        f"Made with `python apps/sound/engine/deps.py` (`cargo metadata --filter-platform {TARGET}`) on "
        f"{datetime.date.today().isoformat()}. No GPL / AGPL / LGPL crate (the script refuses one). MPL-2.0: Symphonia "
        "(file-level copyleft: changes to those files stay MPL; we ship them unmodified). Vendored C++: Signalsmith "
        "Stretch (MIT), compiled in by build.rs.",
        "",
        "Our own and vendored (patched) crates: " + ", ".join(f"{p['name']} {p['version']} ({p['license']})" for p in local) + ".",
        "",
        "| Crate | Version | Licence |",
        "|---|---|---|",
        *[f"| {p['name']} | {p['version']} | {p['license']} |" for p in rows],
        "",
    ]
    return "\n".join(lines)


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--check", action="store_true")
    args = a.parse_args()
    pkgs = shipped(metadata())
    bad = [f"{p['name']} {p['version']}: {p['license'] or 'no licence given'}" for p in pkgs if refused(p["license"])]
    if bad:
        sys.exit("crates that must not ship:\n  " + "\n  ".join(bad))
    print(f"{len(pkgs)} crates, none GPL / AGPL / LGPL")
    if not args.check:
        (HERE / "DEPENDENCIES.md").write_text(table(pkgs), encoding="utf-8")


if __name__ == "__main__":
    main()
