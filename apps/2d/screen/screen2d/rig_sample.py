"""A small character for checks and walks (layout_states.py, the F4 walk): a project with a 2D item "max" (a group
"max" of shapes named like a body, mouths and eyes, as a PSD's parts arrive) and a Sound item "voice" with one voice
line. Its words are a take already made on this laptop, so no voice model runs; on another machine the line simply
shows as not made yet. Made fresh in the folder given."""
from __future__ import annotations

from pathlib import Path

SKIN, SHIRT, PANTS, DARK = "#f2c9a0", "#3d7be0", "#2b3550", "#1d1d24"
PARTS = [  # name, x, y, w, h, fill, round
    ("thigh L", 610, 470, 40, 100, PANTS, 0), ("shin L", 610, 565, 34, 90, PANTS, 0), ("foot L", 598, 625, 60, 28, DARK, 0),
    ("thigh R", 670, 470, 40, 100, PANTS, 0), ("shin R", 670, 565, 34, 90, PANTS, 0), ("foot R", 682, 625, 60, 28, DARK, 0),
    ("torso", 640, 330, 130, 180, SHIRT, 0),
    ("upper arm L", 558, 290, 30, 100, SHIRT, 0), ("forearm L", 558, 385, 26, 90, SKIN, 0), ("hand L", 558, 450, 34, 40, SKIN, 1),
    ("upper arm R", 722, 290, 30, 100, SHIRT, 0), ("forearm R", 722, 385, 26, 90, SKIN, 0), ("hand R", 722, 450, 34, 40, SKIN, 1),
    ("head", 640, 180, 110, 120, SKIN, 1),
    ("eyes open", 640, 168, 64, 16, DARK, 0), ("eyes closed", 640, 172, 64, 5, DARK, 0),
    ("mouth rest", 640, 212, 40, 5, DARK, 0), ("mouth M B P", 640, 212, 44, 3, DARK, 0), ("mouth E", 640, 212, 44, 14, DARK, 0),
    ("mouth O", 640, 214, 24, 24, DARK, 1), ("mouth A", 640, 214, 40, 28, DARK, 1), ("mouth F V", 640, 212, 40, 9, DARK, 0),
]
LINE = "Welcome back to the show"


def source() -> str:
    lines = ['comp("scene", width=1280, height=720, fps=24, duration=4, background="#e9e4da")', 'with group("max", name="max"):']
    for name, x, y, w, h, fill, round_ in PARTS:
        lines.append(f'    shape("{name.replace(" ", "_")}", name="{name}", x={x}, y={y}, w={w}, h={h}, fill="{fill}"'
                     + (', shape="ellipse"' if round_ else ', radius=8') + ')')
    return "\n".join(lines) + "\n"


def character_project(folder: Path) -> list[str]:
    """Make the project in `folder`; returns the screen's start args (--doc folder max)."""
    from rostrum_core import Document, Who
    from rostrum2d import KIND, run_source
    from rostrum_sound.doc.kind import KIND as SOUND
    (folder / "docs").mkdir(parents=True, exist_ok=True)
    d = Document.new(KIND, folder=folder, item="max")
    d.run_script("max.py", run_source(source(), "max.py"))
    d.save()
    s, who = Document.new(SOUND, folder=folder, item="voice"), Who.person("check")
    s.apply({"op": "track.add", "args": {"id": "vo", "name": "Voice", "instrument": "voice", "voice": "ryan"}}, who)
    s.apply({"op": "line.add", "target": "vo", "args": {"id": "hello", "text": LINE, "at": 0.5}}, who)
    s.save()
    return ["--doc", str(folder), "max"]
