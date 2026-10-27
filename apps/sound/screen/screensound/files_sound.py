"""RostrumSound's thin adapter to the kit's one file model (shared/gui-kit/FILES.md): a song is one Sound document in a
project folder (`<folder>/docs/<item>.trk`); a new one is "Untitled song" (then 2, 3 …) in the projects folder with the
person's defaults for new songs. Every window is live, so there is no Save and no question on closing: the kit's
ProjectFiles does New, Open, Open recent, Duplicate, Save a version, Show folder and the start screen. No Qt here.
"""
from __future__ import annotations

from pathlib import Path

from rostrum_core import Document, RostrumError, codes, project
from rostrum_gui.docfiles import AppFiles
from rostrum_sound import KIND, opening, settings

ITEM = "song"                      # a new song's item id inside its project folder
GUIDES = Path(__file__).resolve().parents[2] / "guides"


def blank(folder: Path | None) -> Document:
    """A new, empty song with the person's defaults (Preferences: sample rate, loudness target, true-peak ceiling),
    saved in `folder` (None: in memory)."""
    s = settings.load()
    data = Document.new(KIND).data
    data["sampleRate"] = int(s["sampleRate"])
    master = data["master"][0]
    master["loudness"], master["truePeak"] = float(s["loudness"]), float(s["truePeak"])
    doc = Document(KIND, data, folder=folder, item=ITEM if folder else None)
    if folder:
        doc.save()
    return doc


def song_item(folder) -> str:
    """The Sound document in a project folder: the only one, else the one changed most recently."""
    found = project.items(folder, "sound")
    if not found:
        raise RostrumError(codes.NOT_FOUND, "open", str(folder), "has no RostrumSound song in it",
                           hint="Pick a song file (.trk) or a project folder that has one in its docs folder. "
                                "Nothing was changed.")
    return max(found, key=lambda it: (Path(folder) / it["file"]).stat().st_mtime)["id"]


def resolve(path) -> tuple[Path, str]:
    """A song file (`…/docs/<item>.trk`) or a project folder -> (project folder, item)."""
    p = Path(path)
    if p.is_file() and p.suffix == KIND.ext and p.parent.name == "docs":
        return p.parent.parent, p.stem
    if p.is_file():
        raise RostrumError(codes.BAD_ARGUMENT, "open", str(p), f"is not a RostrumSound song (a {KIND.ext} file in a "
                           "project's docs folder)", hint="Nothing was changed.")
    return p, song_item(p)


def title(folder, item) -> str:
    """The name a person sees: the project folder's name (its song item named too when there are several)."""
    many = Path(folder, "docs").is_dir() and len(project.items(folder, "sound")) > 1
    return f"{Path(folder).name} · {item}" if many else Path(folder).name


FILES_SOUND = AppFiles(
    app="sound", title="RostrumSound", noun="song", ext=KIND.ext, untitled="Untitled song", folder=settings.projects_dir,
    blank=blank, open=opening.open_whole, resolve=resolve, sample="lull",
    guides=[(GUIDES / "first-song.md", "Making your first song"), (GUIDES / "recording.md", "Recording"),
            (GUIDES / "exporting.md", "Exporting")],
    # a rename reopens the song: the Editor, its track, the selection, the playhead come back (song_slots.place); the
    # imports wait for the call (no Qt here, and song_slots needs the bridge first)
    place=lambda b: __import__("screensound.song_slots", fromlist=["place"]).place(b),
    restore_place=lambda b, p: __import__("screensound.song_slots", fromlist=["restore_place"]).restore_place(b, p))
