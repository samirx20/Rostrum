"""What a render is delivered as: the file format, the sample rate, trimming the silent end, and the names of the files.

The engine renders 32-bit float WAV files (the mix and one stem per track and bus, named by id) at the sample rate
the schedule asks for. `deliver` turns those into the chosen files in the same folder: `Song.wav`, `pad.wav`,
`drums.wav`, `<group>.wav`, in the format asked for, all cut to the same length so the stems still line up with
the mix. The choices are plain data (`FORMATS`, `RATES`) so the screen and the MCP tool list the same ones, each with
its words; `Options.read` checks a request and says in words what is wrong (MP3 has no 96 kHz, say).

    opts = deliver.Options.read({"format": "wav24", "sampleRate": 48000, "trim": True})
    r = deliver.deliver(folder, r, names, opts)        # r: the engine's answer; returns it with the new files and lengths
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rostrum_core import RostrumError, codes

# id, words on screen, what it is for, file ending, libsndfile format + subtype. 24-bit WAV is the default: it is what
# video editors take, with room for later gain changes.
FORMATS = [
    {"id": "wav24", "label": "WAV 24-bit", "detail": "for video editors", "ext": "wav", "format": "WAV", "subtype": "PCM_24"},
    {"id": "wav16", "label": "WAV 16-bit", "detail": "CD quality, dithered", "ext": "wav", "format": "WAV", "subtype": "PCM_16"},
    {"id": "wav32f", "label": "WAV 32-bit float", "detail": "no rounding, for further mixing", "ext": "wav", "format": "WAV", "subtype": "FLOAT"},
    {"id": "flac", "label": "FLAC 24-bit", "detail": "lossless, about half the size", "ext": "flac", "format": "FLAC", "subtype": "PCM_24"},
    {"id": "mp3", "label": "MP3 320 kbps", "detail": "small, to listen on any device", "ext": "mp3", "format": "MP3", "subtype": "MPEG_LAYER_III"},
]
RATES = [{"id": 44100, "label": "44.1 kHz", "detail": "music"},
         {"id": 48000, "label": "48 kHz", "detail": "video"},
         {"id": 96000, "label": "96 kHz", "detail": "high resolution"}]
RATE_LABELS = {r["id"]: f'{r["label"]} ({r["detail"]})' for r in RATES}   # one wording for Settings, the song and export
BY_FORMAT = {f["id"]: f for f in FORMATS}
MP3_RATES = (44100, 48000)              # the MP3 encoder inside libsndfile makes these two of ours
DEFAULT_FORMAT = "wav24"

AUDIBLE = 1e-4          # -80 dBFS: below this nothing is heard, even a reverb tail in a quiet room
TAIL = 0.25             # seconds kept after the last audible sound
MIN_SECONDS = 0.5       # never a shorter file than this
BLOCK = 1 << 18         # frames read and written at a time (2 MB of stereo float)


def rates_for(fmt: str) -> list[dict]:
    """The sample rates valid for a format (MP3 has no 96 kHz)."""
    return [r for r in RATES if fmt != "mp3" or r["id"] in MP3_RATES]


def choices() -> dict:
    return {"formats": [{k: f[k] for k in ("id", "label", "detail")} for f in FORMATS],
            "rates": {f["id"]: rates_for(f["id"]) for f in FORMATS}}


@dataclass(frozen=True)
class Options:
    format: str = DEFAULT_FORMAT
    sample_rate: int = 48000
    trim: bool = True
    start: float | None = None       # a range of the song (seconds): `from` / `to` in a request; both or neither
    end: float | None = None

    @classmethod
    def read(cls, args: dict | None, doc_rate: int = 48000) -> Options:
        args = args or {}
        fmt = args.get("format") or DEFAULT_FORMAT
        if fmt not in BY_FORMAT:
            raise RostrumError(codes.BAD_ARGUMENT, "render", f'format "{fmt}"', "is not one we write",
                               hint="Use one of: " + ", ".join(BY_FORMAT) + ".")
        rate = args.get("sampleRate") or (doc_rate if doc_rate in [r["id"] for r in RATES] else 48000)
        if rate not in [r["id"] for r in rates_for(fmt)]:
            ok = ", ".join(str(r["id"]) for r in rates_for(fmt))
            raise RostrumError(codes.BAD_ARGUMENT, "render", f"sample rate {rate}", f"is not available for {BY_FORMAT[fmt]['label']}",
                               hint=f"Use one of: {ok}.")
        a, b = args.get("from"), args.get("to")
        if (a is None) != (b is None) or a is not None and not (isinstance(a, (int, float)) and isinstance(b, (int, float))
                                                              and 0 <= a < b):
            raise RostrumError(codes.BAD_ARGUMENT, "render", f"range from {a} to {b}", "is not a stretch of the song",
                               hint='Give both `from` and `to` in seconds, with 0 ≤ from < to (or neither for the whole song).')
        return cls(fmt, int(rate), bool(args.get("trim", True)), None if a is None else float(a), None if b is None else float(b))

    @property
    def spec(self) -> dict:
        return BY_FORMAT[self.format]

    def describe(self) -> dict:
        s = self.spec
        return {"id": self.format, "label": s["label"], "container": s["format"], "subtype": s["subtype"], "ext": s["ext"]}


# ---- file names ---------------------------------------------------------------------------------------------------

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def safe_name(name: str, taken: set[str], fallback: str = "track") -> str:
    """`name` made safe as a file name and unique among `taken` (compared without case; the winner is added to it)."""
    s = re.sub(r"\s+", " ", _ILLEGAL.sub("_", str(name))).strip(" .") or fallback
    s = s[:80].rstrip(" .")
    if s.split(".")[0].lower() in _RESERVED:
        s += "_"
    base, n = s, 2
    while s.lower() in taken:
        s, n = f"{base} {n}", n + 1
    taken.add(s.lower())
    return s


# ---- the work -----------------------------------------------------------------------------------------------------

def _soundfile():
    try:
        import soundfile
    except ImportError as e:      # the shipped Python must carry it; say so rather than ship the engine's raw float files
        raise RostrumError(codes.JOB_FAILED, "render", "soundfile", "is not installed, so the render cannot be written in the chosen format",
                           hint="Install the 'soundfile' package.") from e
    return soundfile


def last_audible(path: Path, sf) -> tuple[int, int, int]:
    """(frames in the file, index after the last frame above -80 dBFS (0 for silence), sample rate)."""
    import numpy as np
    last = at = 0
    with sf.SoundFile(str(path)) as f:
        for block in f.blocks(blocksize=1 << 20, dtype="float32"):
            loud = np.nonzero(np.abs(block).max(axis=1) > AUDIBLE)[0] if block.ndim > 1 else np.nonzero(np.abs(block) > AUDIBLE)[0]
            if loud.size:
                last = at + int(loud[-1]) + 1
            at += len(block)
        return f.frames, last, f.samplerate


def _tpdf(shape, rng):
    """Triangular noise of ±1 least-significant bit of 16 bits (two uniform ones added): it makes the rounding noise
    steady and independent of the music, so quiet tails fade out smoothly rather than into crackle."""
    return rng.random(shape, dtype="float32") - rng.random(shape, dtype="float32")


def _convert(block, spec, rng):
    """One block of float data (frames × channels, nominally ±1) as what the file takes; also how many samples of it
    went past full scale (they are clipped; the master's limiter normally keeps a mastered render under it)."""
    import numpy as np
    over = int(np.count_nonzero(np.abs(block) > 1.0)) if spec["subtype"] != "FLOAT" else 0
    if spec["subtype"] == "PCM_16":
        q = np.round(np.clip(block, -1.0, 1.0) * 32767 + _tpdf(block.shape, rng))
        block = np.clip(q, -32768, 32767).astype("int16")
    elif spec["subtype"] != "FLOAT":
        block = np.clip(block, -1.0, 1.0)
    return block, over


def write(path: Path, src: Path, keep: int, rate: int, spec: dict, sf, offset: int = 0) -> int:
    """Write `keep` frames of the engine's float file `src` (from frame `offset`) as `spec`, a block at a time (a stem is never
    held whole; one is much bigger than a block). A file shorter than `keep` is padded with silence so every file is
    the same length. Returns how many samples went past full scale."""
    import numpy as np
    rng = np.random.default_rng(16)
    kw = {"compression_level": 0.0, "bitrate_mode": "CONSTANT"} if spec["format"] == "MP3" else {}     # 0.0 = best quality (320 kbps)
    over = done = 0
    with sf.SoundFile(str(src)) as r, sf.SoundFile(str(path), "w", samplerate=rate, channels=r.channels,
                                                   format=spec["format"], subtype=spec["subtype"], **kw) as f:
        r.seek(offset)
        for block in r.blocks(blocksize=BLOCK, dtype="float32", always_2d=True, frames=keep):
            data, n = _convert(block, spec, rng)
            f.write(data); over += n; done += len(block)
        while done < keep:
            n = min(BLOCK, keep - done)
            f.write(_convert(np.zeros((n, r.channels), "float32"), spec, rng)[0]); done += n
    return over


def mix_name(item: str, ext: str = "wav") -> str:
    """The mix's file name in a render's version folder: the one name the writer uses and the Export sheet shows."""
    return f"{item}_mix.{ext}"


def deliver(folder: Path, r: dict, names: dict, opts: Options, item: str) -> dict:
    """Turn the engine's float files in `folder` into the delivered ones. `r` is the engine's answer (`file`,
    `stems` {track id: path}, `busStems` {bus id: path}); `names` maps a track or bus id to the name the screen shows.
    Returns `r` with the new paths (`range` [from, to] when only a part of the song was asked for: the engine renders
    that part itself, mastered and measured on its own; an older render of the whole song is cut here), `seconds` (the
    delivered length), `songSeconds` (the song's own), `files` (what
    each id became) and what was written (`format`, `sampleRate`, `trimmedTo`, `clippedSamples`)."""
    sf = _soundfile()
    spec = opts.spec
    mix = Path(mix_name(item)).stem
    jobs = [("mix", None, Path(r["file"]), mix)]
    taken = {mix.lower()}
    for tid, p in (r.get("stems") or {}).items():
        jobs.append(("track", tid, Path(p), safe_name(names.get(tid) or tid, taken)))
    for bid, p in (r.get("busStems") or {}).items():
        jobs.append(("bus", bid, Path(p), safe_name(names.get(bid) or bid, taken)))
    info = {j[2]: last_audible(j[2], sf) for j in jobs}
    frames, rate = max(i[0] for i in info.values()), next(iter(info.values()))[2]
    if any(i[2] != opts.sample_rate for i in info.values()):
        raise RostrumError(codes.JOB_FAILED, "render", str(folder), f"the engine wrote {rate} Hz, not the {opts.sample_rate} Hz asked for")
    heard = max(i[1] for i in info.values())
    keep, first = frames, 0
    ranged = opts.start is not None and r.get("range") is not None      # the engine rendered the range itself
    if ranged:
        first = 0
        keep = min(frames, round((opts.end - opts.start) * rate))     # exactly the stretch asked for: the engine's ring-out past it is cut
        if opts.trim and heard:        # its silent end goes, as a whole song's does
            keep = min(frames, max(heard + int(TAIL * rate), int(MIN_SECONDS * rate)))
    elif opts.start is not None:       # a whole-song render (a test's, an old engine's): the cut is made here
        first = int(opts.start * rate)
        if first >= frames:
            raise RostrumError(codes.BAD_ARGUMENT, "render", f"range from {opts.start:g} s",
                               f"starts after the song ends ({frames / rate:.1f} s)")
        keep = min(frames, int(opts.end * rate)) - first
    elif opts.trim and heard:
        keep = min(frames, max(heard + int(TAIL * rate), int(MIN_SECONDS * rate)))
    over, files = 0, {}
    for kind, key, src, stem in jobs:
        dest = folder / f"{stem}.{spec['ext']}"
        part = dest.with_name(dest.name + ".part")        # the engine's file may have the final name: write beside it, then swap
        over += write(part, src, keep, rate, spec, sf, first)
        if dest != src:
            src.unlink()
        part.replace(dest)
        files[(kind, key)] = dest
    mix = files[("mix", None)]
    start = r["range"][0] if ranged else first / rate
    song = (r.get("seconds") or frames / rate) if ranged else frames / rate
    return {**{k: v for k, v in r.items() if k != "range"}, "file": str(mix), "seconds": keep / rate, "songSeconds": song,
            "stems": {k: str(files[("track", k)]) for k in (r.get("stems") or {})},
            "busStems": {k: str(files[("bus", k)]) for k in (r.get("busStems") or {})},
            "format": opts.describe(), "sampleRate": rate, "trimmed": bool(opts.trim and keep < frames and (ranged or opts.start is None)),
            **({"range": [start, start + keep / rate]} if opts.start is not None else {}),
            "clippedSamples": over}
