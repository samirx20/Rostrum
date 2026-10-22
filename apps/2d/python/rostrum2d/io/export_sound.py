"""An MP4 export's sound: the project's mix, made by RostrumSound's engine (AGENTS.md rule 9; 2D never mixes), cut to
the export's time range and put beside the picture by the bundled LGPL FFmpeg (the picture is copied, not encoded
again; the sound is AAC). The export runner (mcp/exporting.py) calls `attach` on the finished .partial file before
it is renamed, so a failure here fails the whole export: never a silent MP4 when sound was asked (rule 6).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .. import settings

AUDIO_KBPS = 256


def mix(folder, song_id: str) -> Path:
    """The song's mix as a WAV, rendered by Sound's engine (cached by content: an unchanged song is not rendered twice)."""
    from rostrum_sound import soundtrack
    from rostrum_sound.engine import Engine
    root = soundtrack.read(folder, song_id)
    with Engine() as eng:
        return soundtrack.render(eng, folder, root)


def mux_command(video: Path, wav: Path, start: float, seconds: float, out: Path) -> list[str]:
    return [settings.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
            "-ss", f"{start:.6f}", "-t", f"{seconds:.6f}", "-i", str(wav),
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k", str(out)]


def has_sound(path: Path) -> bool:
    """Does the file hold a sound stream (ffprobe)?"""
    r = subprocess.run([settings.ffmpeg("ffprobe"), "-v", "error", "-select_streams", "a", "-show_entries",
                        "stream=codec_name", "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60,
                       creationflags=settings.NO_WINDOW)
    return r.returncode == 0 and bool(r.stdout.strip())


def attach(video, folder, song_id: str, start: float, end: float, wav: Path | None = None) -> dict:
    """Put the song's mix from `start` to `end` (seconds) under the picture in `video`, in place. `wav`: an already
    rendered mix (tests); else Sound's engine renders it. Any failure raises with the plain reason; `video` is left as
    it was (the runner then removes it)."""
    video = Path(video)
    wav = Path(wav) if wav is not None else mix(folder, song_id)
    if not wav.is_file():
        raise RuntimeError(f"the project's sound was not made: no mix at {wav}")
    out = video.with_name(video.stem + ".sound" + video.suffix)
    out.unlink(missing_ok=True)
    try:
        r = subprocess.run(mux_command(video, wav, start, end - start, out), capture_output=True, text=True,
                           timeout=1800, creationflags=settings.NO_WINDOW)
        if r.returncode or not out.is_file():
            said = (r.stderr or "").strip().splitlines()
            raise RuntimeError(f"FFmpeg could not put the sound under the picture (exit {r.returncode})"
                               + (f": {said[-1]}" if said else ""))
        if not has_sound(out):
            raise RuntimeError(f"the MP4 came out without sound: the mix may end before {start:g} s, where the "
                               "export starts")
        os.replace(out, video)
    finally:
        out.unlink(missing_ok=True)
    return {"song": song_id, "mix": str(wav), "kbps": AUDIO_KBPS}
