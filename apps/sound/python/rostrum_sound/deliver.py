"""What a render is delivered as: the file format, the sample rate, trimming the silent end, and the names of the files.

The engine renders 32-bit float WAV files (the mix and one stem per track and bus, named by id) at the sample rate
the schedule asks for. `deliver` turns those into the chosen files in the same folder: `Song.wav`, `pad.wav`,
`drums.wav`, `<group>.wav`, in the format asked for, all cut to the same length so the stems still line up with
the mix. The choices are plain data (`FORMATS`, `RATES`) so the screen and the MCP tool list the same ones, each with
its words; `Options.read` checks a request and says in words what is wrong (MP3 has no 96 kHz, say).

    opts = deliver.Options.read({"format": "wav24", "sampleRate": 48000, "trim": True})   # trim is opt-in
    r = deliver.deliver(folder, r, names, opts)        # r: the engine's answer; returns it with the new files and lengths
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from rostrum_core import RostrumError, codes

from .listen import ending

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
ALIASES = {"wav": "wav24"}     # what a person means by plain "wav": the default WAV

AUDIBLE = 1e-4          # -80 dBFS: below this nothing is heard, even a reverb tail in a quiet room
TAIL = 0.25             # seconds kept after the last audible sound
DECLICK_S = 0.01        # a file cut at its length while still sounding: only this short ramp, so the cut has no click
RING_WARNINGS = ("The song's length is", "The last sounds still ring")    # the engine's words for a file that ends after the length
RING_S = 2.0            # ring_past_length true: a ring-out may run this far past the length (the usual delivery allowance)
MOST_RING_S = 6.0       # the most a ring-out may run past the length
MIN_SECONDS = 0.5       # never a shorter file than this
BLOCK = 1 << 18         # frames read and written at a time (2 MB of stereo float)
WRITERS = 4             # files converted at once (reading, converting and writing a file leave Python's lock free)


def ring_allowed(v) -> float:
    """render_mix's `ring_past_length` in seconds: False 0, True RING_S, a number up to MOST_RING_S."""
    if v is None or v is False:
        return 0.0
    if v is True:
        return RING_S
    if isinstance(v, (int, float)) and 0 <= v <= MOST_RING_S:
        return float(v)
    raise RostrumError(codes.BAD_ARGUMENT, "render_mix", f"ring_past_length={v!r}", f"is not true, false or seconds from 0 to {MOST_RING_S:g}",
                       hint=f"true lets the ring run up to {RING_S:g} s past the length; 1.5 up to 1.5 s.")


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
    trim: bool = False               # asked only: the silent end (below -80 dBFS) is cut to the last sound + TAIL; off, the file is the engine's whole length
    start: float | None = None       # a range of the song (seconds): `from` / `to` in a request; both or neither
    end: float | None = None
    length: float | None = None      # exact: the song's Length (seconds) the file must be; what still sounds there is cut (a de-click)
    ring: float = 0.0                # seconds a ring-out may run past `length` (ring_past_length), cut there (a de-click)
    loop: bool = False               # the brief asks for a loop: no warning for the cut at `length` (it plays on into bar 1)

    @classmethod
    def read(cls, args: dict | None, doc_rate: int = 48000) -> Options:
        args = args or {}
        fmt = args.get("format") or DEFAULT_FORMAT
        fmt = ALIASES.get(fmt, fmt)
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
        return cls(fmt, int(rate), bool(args.get("trim", False)), None if a is None else float(a), None if b is None else float(b),
                   None if args.get("length") is None else float(args["length"]), float(args.get("ring") or 0.0), bool(args.get("loop")))

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


def ringing_at(path: Path, at: int, sf) -> tuple[float, float] | None:
    """Is the mix still sounding where a file cut at frame `at` ends? Read with look_sound's own measure (listen.ending:
    the last 0.5 s over -50 dBFS): (that level, seconds heard past the cut until under -60 dBFS for good), else None."""
    with sf.SoundFile(str(path)) as f:
        rate = f.samplerate
        f.seek(max(0, at - int(ending.TAIL_S * rate)))
        y = f.read(dtype="float32", always_2d=True)
    before, after = y[:at - max(0, at - int(ending.TAIL_S * rate))], y[at - max(0, at - int(ending.TAIL_S * rate)):]
    if not ending.still_sounding(before, rate):
        return None
    return ending.sounding_db(before), ending.audible_end(after, rate)


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


def write(path: Path, src: Path, keep: int, rate: int, spec: dict, sf, offset: int = 0, fade: int = 0) -> int:
    """Write `keep` frames of the engine's float file `src` (from frame `offset`) as `spec`, a block at a time (a stem is never
    held whole; one is much bigger than a block). A file shorter than `keep` is padded with silence so every file is
    the same length. `fade`: the last frames of the kept part are faded out (a cosine ramp). Returns how many samples went past
    full scale."""
    import numpy as np
    rng = np.random.default_rng(16)
    kw = {"compression_level": 0.0, "bitrate_mode": "CONSTANT"} if spec["format"] == "MP3" else {}     # 0.0 = best quality (320 kbps)
    over = done = 0
    with sf.SoundFile(str(src)) as r, sf.SoundFile(str(path), "w", samplerate=rate, channels=r.channels,
                                                   format=spec["format"], subtype=spec["subtype"], **kw) as f:
        r.seek(offset)
        for block in r.blocks(blocksize=BLOCK, dtype="float32", always_2d=True, frames=keep):
            if fade and done + len(block) > keep - fade:       # the end of the kept part: a cosine fade to nothing
                x = np.clip((np.arange(done, done + len(block)) - (keep - fade)) / fade, 0.0, 1.0)
                block = block * (0.5 + 0.5 * np.cos(np.pi * x))[:, None].astype("float32")
            data, n = _convert(block, spec, rng)
            f.write(data); over += n; done += len(block)
        while done < keep:
            n = min(BLOCK, keep - done)
            f.write(_convert(np.zeros((n, r.channels), "float32"), spec, rng)[0]); done += n
    return over


def mix_stem(item: str, name: str = "", taken=()) -> str:
    """The mix's name without its type: the one the person or agent gave (made safe for a file name), else "<item>_mix".
    `taken`: names the engine's own stem files already hold in the folder (a track called like the mix gets " 2")."""
    return safe_name(name, {t.lower() for t in taken}, f"{item}_mix") if name else f"{item}_mix"


def mix_name(item: str, ext: str = "wav", name: str = "") -> str:
    """The mix's file name in a render's version folder: the one name the writer uses and the Export sheet shows."""
    return f"{mix_stem(item, name)}.{ext}"


def deliver(folder: Path, r: dict, names: dict, opts: Options, item: str, name: str = "") -> dict:
    """Turn the engine's float files in `folder` into the delivered ones. `r` is the engine's answer (`file`,
    `stems` {track id: path}, `busStems` {bus id: path}); `names` maps a track or bus id to the name the screen shows.
    Returns `r` with the new paths (`range` [from, to] when only a part of the song was asked for: the engine renders
    that part itself, mastered and measured on its own; an older render of the whole song is cut here), `seconds` (the
    delivered length), `songSeconds` (the song's own), `files` (what
    each id became) and what was written (`format`, `sampleRate`, `trimmedTo`, `clippedSamples`, and `clippedFiles`: {file
    name: samples cut flat} for each fixed-point file that went past full scale).
    `opts.length` (render_mix, whenever the song has a Length): the file is exactly that long. Trim never cuts below it, and a
    ring-out the engine let run past it is cut there with a 10 ms de-click, never faded (the engine's own ring-out warnings
    are replaced by one saying so)."""
    sf = _soundfile()
    spec = opts.spec
    mix = mix_stem(item, name, [Path(p).stem for p in (*(r.get("stems") or {}).values(), *(r.get("busStems") or {}).values())])
    jobs = [("mix", None, Path(r["file"]), mix)]
    taken = {mix.lower()}
    for tid, p in (r.get("stems") or {}).items():
        jobs.append(("track", tid, Path(p), safe_name(names.get(tid) or tid, taken)))
    for bid, p in (r.get("busStems") or {}).items():
        jobs.append(("bus", bid, Path(p), safe_name(names.get(bid) or bid, taken)))
    meters = {("track", k): m for k, m in (r.get("stemMeters") or {}).items()} |              {("bus", k): m for k, m in (r.get("busStemMeters") or {}).items()}

    def where_heard(kind, key, src):
        """(frames, last audible frame, rate): the engine measured each stem as it wrote it; only the mix is read here."""
        m = meters.get((kind, key))
        if m is None or m.get("lastAudible") is None:
            return last_audible(src, sf)
        i = sf.info(str(src))
        return i.frames, int(m["lastAudible"]), i.samplerate
    info = {j[2]: where_heard(*j[:3]) for j in jobs}
    frames, rate = max(i[0] for i in info.values()), next(iter(info.values()))[2]
    if any(i[2] != opts.sample_rate for i in info.values()):
        raise RostrumError(codes.JOB_FAILED, "render", str(folder), f"the engine wrote {rate} Hz, not the {opts.sample_rate} Hz asked for")
    heard = max(i[1] for i in info.values())
    keep, first, declick, ringing = frames, 0, 0, None
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
    elif opts.length is not None:      # the song's Length is the file's length: not shorter (trim), not longer (a ring-out)
        keep = round(opts.length * rate)
        if opts.ring:                  # the ring may run on up to `ring` past it (its silent end trimmed)
            keep = min(frames, max(keep, min(heard + int(TAIL * rate), keep + round(opts.ring * rate))))
        if frames > keep and heard > keep:   # anything left where it ends: cut there as asked, only a de-click, never a
            declick = min(int(DECLICK_S * rate), keep)   # fade (Sam, 2026-10-29: the delivery never reshapes the music)
            ringing = ringing_at(Path(r["file"]), keep, sf)
    elif opts.trim and heard:
        keep = min(frames, max(heard + int(TAIL * rate), int(MIN_SECONDS * rate)))
    def one(job):
        kind, key, src, stem = job
        dest = folder / f"{stem}.{spec['ext']}"
        part = dest.with_name(dest.name + ".part")        # the engine's file may have the final name: write beside it, then swap
        n = write(part, src, keep, rate, spec, sf, first, declick)
        if dest != src:
            src.unlink()
        part.replace(dest)
        return dest, n
    with ThreadPoolExecutor(max_workers=max(1, min(WRITERS, len(jobs)))) as pool:
        done = list(pool.map(one, jobs))
    files = {(kind, key): dest for (kind, key, _, _), (dest, _) in zip(jobs, done)}
    clipped = {dest.name: n for dest, n in done if n}       # samples cut flat at full scale, per file (a fixed-point file only)
    over = sum(clipped.values())
    mix = files[("mix", None)]
    start = r["range"][0] if ranged else first / rate
    song = (r.get("seconds") or frames / rate) if ranged else frames / rate
    cut = bool(declick) and opts.length is not None
    warnings = [w for w in r.get("warnings") or [] if not (cut and w.startswith(RING_WARNINGS))]
    if cut and ringing and not opts.loop:    # said only when look_sound would call the file's end still sounding (one measure)
        is_ = (f"{opts.length:.2f} s; the file is {keep / rate:.2f} s with the {opts.ring:g} s of ring allowed" if opts.ring and opts.length is not None
               else f"{keep / rate:.2f} s and so is the file")
        warnings.append(f"The song's length is {is_}: it still sounds there (last 0.5 s at {ringing[0]:.0f} dBFS, over "
                        f"{ending.SILENT_DBFS:g}), so the file stops while ringing ({ringing[1]:.1f} s more was heard past it, "
                        f"to under {ending.HEARD_DBFS:g} dBFS; not faded). To let it ring: end the last notes earlier, "
                        f"set a longer length, or `ring_past_length: true` (up to {RING_S:g} s past the length); a fade: ending(\"fade\").")
    return {**{k: v for k, v in r.items() if k not in ("range", "warnings")}, "warnings": warnings, "file": str(mix), "seconds": keep / rate, "songSeconds": song,
            "stems": {k: str(files[("track", k)]) for k in (r.get("stems") or {})},
            "busStems": {k: str(files[("bus", k)]) for k in (r.get("busStems") or {})},
            "format": opts.describe(), "sampleRate": rate, "trimmed": bool(opts.trim and keep < frames and (ranged or opts.start is None) and opts.length is None),
            **({"range": [start, start + keep / rate]} if opts.start is not None else {}),
            "clippedSamples": over, "clippedFiles": clipped,
            }
