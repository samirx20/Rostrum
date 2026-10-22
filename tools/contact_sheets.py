"""Contact sheets: every screen state of an app at one window size, tiled into one labelled picture (or a few pages).

    python tools/contact_sheets.py <out folder>                      # 2D and Sound at 1646x900 (Sam's screen)
    python tools/contact_sheets.py <out folder> --apps sound --size 1920x1080 --repo C:/path/to/checkout

It runs each app's own layout check states (apps/<app>/screen/*/layout_states.py, rostrum_gui/layout_run.py) at the
one size, so the pictures are the same ones the check makes (any fault it finds is boxed and numbered on the
picture), then writes <out>/contact-<app>.png (contact-<app>-2.png, ... when there are more states than one page
holds) and <out>/shots-<app>/ with a folder per state and faults.txt. Three states run at once. Use the venv the apps run in (tools/rostrum.ps1).
Fails loudly: a state that did not run is named on the sheet and the exit code is nonzero.
"""
from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

APPS = {   # app: (screen folder, layout_states module, engine env var, engine paths in the checkout)
    "2d": ("apps/2d/screen", "screen2d.layout_states", "ROSTRUM2D_ENGINE",
           ["apps/2d/engine/target/release/rostrum2d-render.exe", "apps/2d/engine/target/agent/rostrum2d-render.exe"]),
    "sound": ("apps/sound/screen", "screensound.layout_states", "ROSTRUM_SOUND_ENGINE",
              ["apps/sound/engine/target/release/rostrum-sound.exe", "apps/sound/engine/target/agent/rostrum-sound.exe"]),
}
COLS, ROWS, TILE_W, LABEL = 4, 5, 640, 34          # a page: 4 x 5 pictures, each 640 px wide under its state's name
WORKERS = 3                                         # states run at once (AGENTS.md: at most 3 workers per agent)


def child(size: str, main_py: str, argv: list[str]):
    """One state, in this process: the app's main.py with the layout sweep limited to the one size."""
    sys.path.insert(0, str(Path(main_py).parent))
    from rostrum_gui import layout_run
    w, h = (int(n) for n in size.split("x"))
    layout_run.sweep.__defaults__ = ((), [(w, h)])
    sys.argv = [main_py, *argv]
    runpy.run_path(main_py, run_name="__main__")


def shoot(repo: Path, app: str, size: str, out: Path) -> list[tuple[str, Path | None, str]]:
    """Run every state; [(state name, picture or None, fault / failure note)]."""
    screen, module, env_var, engines = APPS[app]
    screen_dir = repo / screen
    sys.path.insert(0, str(screen_dir))
    states = __import__(module, fromlist=["states"]).states()
    engine = next((repo / e for e in engines if (repo / e).is_file()), None)
    if engine is None:
        raise SystemExit(f"{app}: no engine built in {repo} (looked for {', '.join(engines)})")
    env = {**os.environ, env_var: str(engine), "QT_QPA_PLATFORM": "offscreen", "QT_QPA_FONTDIR": "C:/Windows/Fonts"}
    out.mkdir(parents=True, exist_ok=True)

    def one(n, state):
        name, start, steps = state
        folder = out / name                     # a folder per state: the runs write their faults.json side by side
        cmd = [sys.executable, __file__, "--child", size, str(screen_dir / "main.py"), *start,
               *sum((["--step", s] for s in steps), []), "--check-layout", str(folder), "--check-name", name]
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
        shot = folder / f"{name}-{size}.png"
        found = folder / "faults.json"
        faults = sum(json.loads(found.read_text(encoding="utf-8")).get(name, {}).values(), []) if found.is_file() else []
        note = (f"did not run (exit {r.returncode}): {r.stderr.strip()[-300:]}" if r.returncode not in (0, 5)
                else f"{len(faults)} fault(s) boxed" if faults else "")
        print(f"{app} {n}/{len(states)} {name}: {note or 'ok'}", flush=True)
        return name, (shot if shot.is_file() else None), note, faults

    with ThreadPoolExecutor(WORKERS) as pool:
        got = list(pool.map(one, range(1, len(states) + 1), states))
    lines = [f"{name}: {note}" for name, _, note, _ in got if note.startswith("did not run")]
    lines += [f"{name}: {line}" for name, _, _, faults in got for line in faults]
    (out / "faults.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [(name, shot, note) for name, shot, note, _ in got]


def tile(shots, app: str, size: str, out_dir: Path) -> list[Path]:
    """Pages of COLS x ROWS labelled pictures: contact-<app>.png, contact-<app>-2.png, ..."""
    from PIL import Image, ImageDraw, ImageFont
    w, h = (int(n) for n in size.split("x"))
    th = round(TILE_W * h / w)
    font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 20)
    per = COLS * ROWS
    pages = []
    for p in range(0, len(shots), per):
        part = shots[p:p + per]
        rows = (len(part) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * TILE_W + (COLS + 1) * 8, rows * (th + LABEL + 8) + 8), (230, 230, 230))
        draw = ImageDraw.Draw(sheet)
        for i, (name, shot, note) in enumerate(part):
            x, y = 8 + (i % COLS) * (TILE_W + 8), 8 + (i // COLS) * (th + LABEL + 8)
            draw.text((x, y + 4), f"{p + i + 1}. {name}" + (f"  — {note}" if note else ""), font=font,
                      fill=(170, 20, 20) if note else (20, 20, 20))
            if shot:
                sheet.paste(Image.open(shot).convert("RGB").resize((TILE_W, th), Image.LANCZOS), (x, y + LABEL))
            else:
                draw.rectangle((x, y + LABEL, x + TILE_W, y + LABEL + th), outline=(170, 20, 20), width=3)
        page = out_dir / (f"contact-{app}.png" if not p else f"contact-{app}-{p // per + 1}.png")
        sheet.save(page)
        pages.append(page)
    return pages


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        return child(sys.argv[2], sys.argv[3], sys.argv[4:])
    a = argparse.ArgumentParser()
    a.add_argument("out")
    a.add_argument("--apps", nargs="+", default=list(APPS), choices=list(APPS))
    a.add_argument("--size", default="1646x900")
    a.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    args = a.parse_args()
    out, failed = Path(args.out), 0
    for app in args.apps:
        shots = shoot(Path(args.repo), app, args.size, out / f"shots-{app}")
        failed += sum(1 for _, _, note in shots if note.startswith("did not run"))
        for page in tile(shots, app, args.size, out):
            print(f"sheet: {page}")
    if failed:
        sys.exit(f"FAIL: {failed} state(s) did not run; they are marked in red on the sheets")


if __name__ == "__main__":
    main()
