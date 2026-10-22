"""Make the notices of one installed Rostrum app: what it ships, under which licence, and what each asks of us.

    python notices.py --app 2d|sound --attributions ATTRIBUTIONS.md --site-packages <dir>
                      [--engine-deps <crate list .md>]... --out notices.json [--text NOTICES.txt]

Shipped = every distribution installed in --site-packages (Python), the engine's crate list, and the ATTRIBUTIONS rows
(fonts, models, data) that ship with this app. A shipped item with a GPL / AGPL licence (not LGPL) stops the run
(exit 1). Standard library only.
"""
from __future__ import annotations

import argparse
import datetime
import email.parser
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

OWN = {"rostrum-core", "rostrum-gui", "rostrum-paint", "rostrum2d", "rostrum-sound", "rostrum3d"}
OWN_LICENCE = "MIT, HireMyLens Media"
APP_WORDS = {"2d": ("2d", "rostrum2d"), "sound": ("sound", "rostrumsound")}
SKIP_TOKENS = {"python", "rust", "cpu", "pip", "dev", "qt 6", "venv", "current"}
GPL = re.compile(r"(?<![A-Za-z])(A?GPL|GNU General Public)", re.I)     # GPL / AGPL, never LGPL
TEXT_CAP = 100_000


def norm(s: str) -> str:
    return re.sub(r"[-_.\s]+", "-", s.lower().strip())


def name_tokens(row_name: str) -> set[str]:
    """Names a row stands for: its leading name, every comma / bracket / '+' part, and the first word."""
    parts = [p.strip(" `") for p in re.split(r"[,()/+]| with | and ", row_name)]
    parts = [re.sub(r"^pip\s+`?", "", p).strip("` ") for p in parts]
    first = row_name.split()[0] if row_name.split() else ""
    toks = {norm(p) for p in parts + [first] if p and len(p) > 1}
    return {t for t in toks if t not in SKIP_TOKENS}


def parse_rows(md: Path) -> list[dict]:
    rows = []
    for line in md.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) != 8 or c[0] in ("Name", "") or set(c[0]) <= {"-"}:
            continue
        rows.append(dict(zip(("name", "version", "licence", "used", "linked", "ships", "asks", "source"), c)) | {"tokens": name_tokens(c[0])})
    return rows


def row_for(dist_name: str, rows: list[dict], app: str) -> dict | None:
    """The best ATTRIBUTIONS row for a distribution: prefers one that ships and names this app."""
    n = norm(dist_name)
    hits = [r for r in rows if any(n == t or n.startswith(t + "-") for t in r["tokens"])]
    shipped = lambda r: r["ships"].lower().startswith(("ship", "yes"))        # noqa: E731
    mine = lambda r: any(w in r["used"].lower() for w in APP_WORDS[app])      # noqa: E731
    return max(hits, key=lambda r: (shipped(r), mine(r))) if hits else None


def meta_licence(meta) -> str:
    expr = (meta.get("License-Expression") or "").strip()
    if expr:
        return expr
    lic = (meta.get("License") or "").strip()
    if lic and "\n" not in lic and len(lic) <= 100:
        return lic
    cls = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    cls = [m.group(1) if (m := re.search(r"\(([^)]+)\)", c)) else c for c in cls if c != "OSI Approved"]
    return " / ".join(cls) or "licence not stated in the package"


def licence_files(info: Path, meta) -> list[Path]:
    found = {p for p in (info / "licenses").rglob("*") if p.is_file()} if (info / "licenses").is_dir() else set()
    found |= {p for p in info.iterdir() if p.is_file() and re.match(r"(LICEN[CS]E|COPYING|NOTICE)", p.name, re.I)}
    found |= {info / f for f in meta.get_all("License-File") or [] if (info / f).is_file()}
    return sorted(found)


def read_texts(files: list[Path]) -> list[str]:
    seen, out = set(), []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")[:TEXT_CAP].strip()
        if text and (h := hashlib.sha1(text.encode()).hexdigest()) not in seen:
            seen.add(h)
            out.append(text)
    return out


def distributions(site: Path):
    for info in sorted(site.glob("*.dist-info")):
        mf = info / "METADATA"
        if mf.is_file():
            yield info, email.parser.Parser().parsestr(mf.read_text(encoding="utf-8", errors="replace"), headersonly=True)


def engine_item(md: Path, app: str) -> tuple[dict, list[str]]:
    crates = []
    for line in md.read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(c) == 3 and c[0] != "Crate" and not set(c[0]) <= {"-"}:
            crates.append(c)
    counts = Counter(c[2] for c in crates)
    top = ", ".join(f"{k} ×{v}" for k, v in counts.most_common(5)) + (", …" if len(counts) > 5 else "")
    label = {"2d": "Rostrum2D", "sound": "RostrumSound"}[app]
    item = {"name": f"{label} engine: {len(crates)} Rust crates", "version": "", "licence": top,
            "asks": "Keep the notices; the full crate list is in the notices text file", "source": str(md.name)}
    return item, [f"  {n} {v}: {lic}" for n, v, lic in crates]


def build(a) -> int:
    attr = Path(a.attributions)
    rows, items, texts, warnings, missing = parse_rows(attr), [], [], [], []
    repo_licence = (attr.parent / "LICENSE").read_text(encoding="utf-8").strip() if (attr.parent / "LICENSE").is_file() else ""
    own, engine_loaded = [], False
    for info, meta in (d for site in a.site_packages for d in distributions(Path(site))):
        name, version = meta["Name"], meta["Version"] or ""
        if norm(name) in OWN:
            own.append(name)
            continue
        row, texts_here = row_for(name, rows, a.app), read_texts(licence_files(info, meta))
        item = {"name": name, "version": version, "licence": row["licence"] if row else meta_licence(meta),
                "asks": row["asks"] if row else "Keep the notice", "source": row["source"] if row else (meta["Home-page"] or ""),
                "missing_row": row is None}
        items.append((item, texts_here))
        if row is None:
            missing.append(name)
    # Always listed: installed, our packages ship as source (no dist-info); in a dev venv they show as packages.
    items.insert(0, ({"name": "Rostrum", "version": "0.1.0-dev", "licence": OWN_LICENCE,
                      "asks": "Our own code" + (": " + ", ".join(sorted(own)) if own else ""),
                      "source": "https://github.com/samirx20/Rostrum", "missing_row": False},
                     [repo_licence] if repo_licence else []))
    for md in a.engine_deps:
        if not Path(md).is_file():
            warnings.append(f"engine crate list not found, engine licences NOT listed: {md}")
            continue
        item, lines = engine_item(Path(md), a.app)
        engine_loaded = True
        items.append(({**item, "missing_row": False}, ["Crates:\n" + "\n".join(lines)]))
    for r in rows:   # fonts, models, data and engine parts that ship with this app and are not Python packages
        ships = r["ships"].lower().startswith(("ship", "yes"))
        mine = any(w in r["used"].lower() for w in APP_WORDS[a.app]) or "shared" in r["used"].lower()
        crate = engine_loaded and "/engine" in r["used"] and r["linked"].lower().startswith(("static", "vendored"))
        if ships and mine and "python package" not in r["linked"].lower() and not crate:
            note = " (downloaded on demand)" if "download" in r["ships"].lower() else ""
            items.append(({"name": r["name"], "version": r["version"], "licence": r["licence"], "asks": r["asks"] + note,
                           "source": r["source"], "missing_row": False}, []))
    bad = []
    for item, _ in items:
        if GPL.search(item["licence"]):
            bad.append(f'{item["name"]} ({item["licence"]})')
        if re.search(r"\bL?GPL", item["licence"]) and re.search(r"LGPL", item["licence"]):
            item["asks"] += "; dynamically linked; source offered"
    if bad:
        print("FAIL: GPL / AGPL item ships: " + "; ".join(bad), file=sys.stderr)
        return 1
    Path(a.out).write_text(json.dumps({"app": a.app, "generated": datetime.date.today().isoformat(), "items": [i for i, _ in items],
                                       "warnings": warnings}, indent=1), encoding="utf-8")
    if a.text:
        out = [f"Notices for Rostrum ({a.app}), generated {datetime.date.today().isoformat()}\n"]
        for item, t in items:
            out.append("=" * 78 + f'\n{item["name"]} {item["version"]}\nLicence: {item["licence"]}\nAsks: {item["asks"]}\n'
                       + "\n\n".join(t or [f'(licence text: see {item["source"] or "the licence named above"})']) + "\n")
        Path(a.text).write_text("\n".join(out), encoding="utf-8")
    print(f"{a.app}: {len(items)} items, {len(missing)} without an ATTRIBUTIONS row, {len(warnings)} warnings")
    for w in warnings:
        print("WARNING:", w)
    if missing:
        print("missing rows:", ", ".join(missing))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--app", required=True, choices=["2d", "sound"])
    p.add_argument("--attributions", required=True)
    p.add_argument("--site-packages", required=True, action="append", help="repeat: the shared and the app's own folder")
    p.add_argument("--engine-deps", action="append", default=[])
    p.add_argument("--out", required=True)
    p.add_argument("--text")
    return build(p.parse_args())


if __name__ == "__main__":
    sys.exit(main())
