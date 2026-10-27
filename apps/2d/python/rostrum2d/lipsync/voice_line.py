"""A lip-sync source named by a RostrumSound voice line: `"voice:<line id>"` (or `"voice:<song item>/<line id>"` when two
songs of the project have that id). It stands for the line's made take (Sound's voice cache, rostrum_sound.voice_lines)
and its words, so a script never copies a cache path that changes when the words do. A WAV path passes through
unchanged. Every miss is a loud error naming what to do: no project folder, no such line, a take not made yet."""
from __future__ import annotations

PREFIX = "voice:"


def is_line(source) -> bool:
    return isinstance(source, str) and source.startswith(PREFIX)


def resolve(source, folder, where: str = "lipsync") -> tuple[str, str | None]:
    """(the WAV to hear, the line's words or None) for a lip-sync `source`."""
    if not is_line(source):
        return source, None
    ref = source[len(PREFIX):].strip()
    item, _, line_id = ref.rpartition("/")
    if not line_id:
        raise ValueError(f'{where}: source "{source}" names no line; write "voice:<line id>" (Sound\'s inspect_item lists them)')
    if not folder:
        raise ValueError(f'{where}: source "{source}" is a Sound voice line, which needs the project open (its folder); '
                         "with no project give the take's WAV path")
    from rostrum_core import project
    from rostrum_sound import voice_lines
    from ..project_sound import open_song
    songs = [s["id"] for s in project.items(folder, "sound")]
    if item and item not in songs:
        raise ValueError(f'{where}: source "{source}": the project has no Sound item "{item}" (it has: {", ".join(songs) or "none"})')
    found, known = [], []
    for song in [item] if item else songs:
        for track, line in voice_lines.lines(open_song(folder, song)):
            known.append(f"{song}/{line['id']}")
            if line["id"] == line_id:
                found.append((song, track, line))
    if not found:
        raise ValueError(f'{where}: source "{source}": no voice line "{line_id}" in the project\'s Sound items '
                         f'(lines: {", ".join(known[:20]) or "none"})')
    if len(found) > 1:
        raise ValueError(f'{where}: source "{source}": line "{line_id}" is in more than one song; write '
                         + " or ".join(f'"voice:{s}/{line_id}"' for s, _, _ in found))
    song, track, line = found[0]
    take = voice_lines.take_of(track, line)
    if take is None:
        raise ValueError(f'{where}: voice line "{line_id}" ({song}) is not made yet: run Sound\'s render_voice for it first')
    return take.file, line.get("text")
