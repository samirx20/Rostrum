"""Small projects with sound for the layout check, pictures and hand tests (layout_states.py, the hand tests):
a short song with a tempo and the shared marker "drop", a scene with two layers, and a variant with a video that has
its own sound (the Video sound row, video_sound.py)."""
from __future__ import annotations

SONG = '''tempo(120); beats_per_bar(4); length(bar(3))
d = track("drums", kit="classic")
for b in range(8):
    d.hit("kick", at=beat(b))
d.hit("cymbal", at="#drop")
'''
FILM = '''comp("main", width=1280, height=720, fps=30, duration=4)
text("title", body="Drop", x=640, y=200, end=1.4)
shape("logo", x=640, y=360, start=0.5, end=3.0)
'''


def sound_project(folder) -> list[str]:
    """Start args for a project with sound (the layout check's Sound states): a short song with a tempo and the
    shared marker "drop" at 2 s, and a scene "film" (item) with two layers."""
    from pathlib import Path

    from rostrum_core import Document, Who, markers
    from rostrum_core.storage import save
    from rostrum_sound import KIND, run_source
    from rostrum_sound.doc import markers as sound_markers
    folder = Path(folder)
    (folder / "docs").mkdir(parents=True, exist_ok=True)
    markers.edit(folder, [{"op": "marker.add", "args": {"name": "drop", "at": 2.0}}], Who.agent("layout"))
    with sound_markers.project(folder):
        song = Document.new(KIND, folder, "song")
        song.run_script("song.py", run_source(SONG, "song.py"), Who.agent("layout"))
        save(song)
    script = folder.parent / f"{folder.name}-film.py"
    script.write_text(FILM, encoding="utf-8")
    return ["--doc", str(folder), "film", "--script", str(script)]


def video_sound_project(folder) -> list[str]:
    """The sound project plus a short video that has its own sound (a 3 s tone, made by ffmpeg) placed 0.5 s in, Clip
    starts at 0.5 s: the layout check's Video sound row (video_sound.py)."""
    import subprocess
    from pathlib import Path

    from rostrum2d import settings
    args = sound_project(folder)
    clip = Path(folder) / "talk.mp4"
    subprocess.run([settings.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x2a4d6e:s=320x180:r=30:d=3",
                    "-f", "lavfi", "-i", "sine=frequency=330:duration=3", "-af", "volume=6,tremolo=f=3:d=0.9",
                    "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(clip)], check=True, timeout=60,
                   creationflags=settings.NO_WINDOW)
    script = Path(args[args.index("--script") + 1])
    script.write_text(FILM + f'video("talk", src={str(clip)!r}, x=640, y=360, w=320, h=180, start=0.5, end=3.2, '
                      'offset=0.5)\n', encoding="utf-8")
    return args

