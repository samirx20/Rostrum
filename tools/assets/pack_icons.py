"""Packs an unpacked icon-set npm package into the zip Rostrum ships (shared/core/rostrum_core/byname/data/):
one `icons.json` {name: svg text, minified}, plus the set's LICENSE. Run once per version bump:

    python tools/assets/pack_icons.py lucide <unpacked lucide-static>/package 1.65.0
    python tools/assets/pack_icons.py tabler <unpacked @tabler/icons>/package 3.50.0
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "shared" / "core" / "rostrum_core" / "byname" / "data"


def minify(svg: str) -> str:
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    svg = re.sub(r'\s+class="[^"]*"', "", svg)
    svg = re.sub(r"\s+", " ", svg).replace("> <", "><").replace(" />", "/>").replace("<svg ", "<svg ", 1)
    return svg.replace(" >", ">").strip()


def icons(kind: str, pkg: Path) -> dict[str, str]:
    if kind == "lucide":
        return {p.stem: minify(p.read_text("utf-8")) for p in sorted((pkg / "icons").glob("*.svg"))}
    out = {p.stem: minify(p.read_text("utf-8")) for p in sorted((pkg / "icons" / "outline").glob("*.svg"))}
    out.update({f"{p.stem}-filled": minify(p.read_text("utf-8")) for p in sorted((pkg / "icons" / "filled").glob("*.svg"))})
    return out


def main(kind: str, pkg: str, version: str) -> None:
    pkg_dir = Path(pkg)
    for old in OUT.glob(f"{kind}-*.zip"):
        old.unlink()
    target = OUT / f"{kind}-{version}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("icons.json", json.dumps(icons(kind, pkg_dir), separators=(",", ":")))
        z.writestr("LICENSE", (pkg_dir / "LICENSE").read_text("utf-8"))
    print(target, target.stat().st_size)


if __name__ == "__main__":
    main(*sys.argv[1:4])
