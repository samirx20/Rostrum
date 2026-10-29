"""Is this file a delivery, or a refused render put in its place?

Round sound-vault: render_mix refused a mix with open faults and kept it as `<name>.NOT-DONE.wav`; the agent copied it
to `<name>.wav` by hand and the bench took it. So a refused render now carries three things a copy cannot shed:

- a mark inside the file, `ROSTRUM NOT DONE: <fault ids>` (WAV: a LIST/INFO ICMT chunk at the end; FLAC: an APPLICATION
  block after STREAMINFO; MP3: an ID3v2 TXXX frame in front). Written by hand, no tag library: the bytes are tiny.
- a record, `renders/refused.json` in the project (and `refused.json` in the asked `folder`): the sha256 of the decoded
  samples (so re-saving the same samples without the mark is still caught), the fault ids, the asked path, the time.
- `check(path)`: refused when the mark is in the file, the name says NOT-DONE, or a record beside it or above it names
  its samples. `python -m rostrum_sound.delivered <file> [--records refused.json ...]` says so and exits 1.

render_mix's replies also check every asked path a record names (`stale_faults`): a refused render sitting there opens
the reply as a fault."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import time
from pathlib import Path

MARK = b"ROSTRUM NOT DONE"
RECORDS = "refused.json"
KEEP_RECORDS = 200          # a record file keeps the newest this many refusals
EDGE = 1 << 20              # the mark is looked for in the first and last 1 MB (where every format here puts it)


def held_name(path: str | Path) -> Path:
    p = Path(path)
    return p.with_name(f"{p.stem}.NOT-DONE{p.suffix}")


def words(asked, held) -> str:
    """The refusal's own sentence (render_mix's error opens with it)."""
    return (f"Not delivered. Nothing was written at {asked}; copying the .NOT-DONE file there does not deliver it "
            f"(it is marked inside). The render is kept for listening only, as {held}.")


# ---- the mark --------------------------------------------------------------------------------------------------------

def _text(ids) -> bytes:
    return MARK + b": " + ", ".join(ids).encode("utf-8", "replace")


def _mark_wav(data: bytes, text: bytes) -> bytes | None:
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    icmt = text + b"\0"
    sub = b"ICMT" + struct.pack("<I", len(icmt)) + icmt + (b"\0" if len(icmt) % 2 else b"")
    body = b"INFO" + sub
    chunk = b"LIST" + struct.pack("<I", len(body)) + body
    data = data + (b"\0" if len(data) % 2 else b"")        # chunks start on an even byte
    out = data + chunk
    return out[:4] + struct.pack("<I", len(out) - 8) + out[8:]


def _mark_flac(data: bytes, text: bytes) -> bytes | None:
    if data[:4] != b"fLaC" or len(data) < 42:
        return None
    head = data[4]                                          # STREAMINFO: always first, 34 bytes
    last = head & 0x80
    block = b"RSTM" + text + b"\0"                          # an APPLICATION block (type 2): any number are allowed
    ours = bytes([0x02 | last]) + len(block).to_bytes(3, "big") + block
    return data[:4] + bytes([head & 0x7F]) + data[5:42] + ours + data[42:]


def _mark_mp3(data: bytes, text: bytes) -> bytes:
    body = b"\0" + b"ROSTRUM\0" + text + b"\0"              # TXXX: encoding latin-1, description, value
    frame = b"TXXX" + struct.pack(">I", len(body)) + b"\0\0" + body
    n = len(frame)
    size = bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])   # syncsafe
    return b"ID3\x03\x00\x00" + size + frame + data


def mark(path: str | Path, ids) -> None:
    """Write `ROSTRUM NOT DONE: <ids>` inside the file, by its format; the audio is not touched."""
    p = Path(path)
    data, text = p.read_bytes(), _text(ids)
    out = _mark_wav(data, text) or _mark_flac(data, text)
    if out is None:
        out = _mark_mp3(data, text) if p.suffix.lower() == ".mp3" else data + text   # any other file: the words at its end
    p.write_bytes(out)


def marked(path: str | Path) -> str | None:
    """The mark's words when the file carries one, else None."""
    with open(path, "rb") as f:
        head = f.read(EDGE)
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - EDGE))
        tail = f.read()
    for part in (head, tail):
        i = part.find(MARK)
        if i >= 0:
            end = min((j for j in (part.find(b"\0", i), part.find(b"\n", i)) if j >= 0), default=min(len(part), i + 400))
            return part[i:end].decode("utf-8", "replace")
    return None


# ---- the record ------------------------------------------------------------------------------------------------------

def audio_hash(path: str | Path) -> str:
    """sha256 of the decoded samples (as float64: exact for 16/24-bit and float files), so the same audio in a new container matches; the file's
    bytes when it cannot be decoded."""
    h = hashlib.sha256()
    try:
        import soundfile as sf
        with sf.SoundFile(str(path)) as f:
            h.update(f"{f.samplerate}:{f.channels}:".encode())
            for block in f.blocks(blocksize=1 << 16, dtype="float64"):
                h.update(block.tobytes())
        return "pcm:" + h.hexdigest()
    except Exception:  # noqa: BLE001  not audio soundfile reads: hash the bytes
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return "file:" + h.hexdigest()


def _read(records: Path) -> list[dict]:
    try:
        return list(json.loads(records.read_text(encoding="utf-8")).get("refused") or [])
    except (OSError, ValueError, AttributeError):
        return []


def _write(records: Path, entry: dict) -> None:
    try:
        records.parent.mkdir(parents=True, exist_ok=True)
        rows = (_read(records) + [entry])[-KEEP_RECORDS:]
        records.write_text(json.dumps({"refused": rows}, indent=1), encoding="utf-8")
    except OSError:
        pass                                                # a folder we cannot write: the mark still says it


def refuse(file: str | Path, ids, asked: str | Path, project_renders: Path | None, folder: Path | None = None) -> Path:
    """A refused render: renamed `<name>.NOT-DONE<ext>` beside itself, marked inside, recorded in the project (and in the
    asked `folder`). A refused render already sitting at `asked` (copied there by hand) is removed. Returns the kept file."""
    src, held = Path(file), held_name(file)
    if Path(asked).is_file() and Path(asked) != src and not check(asked, [project_renders / RECORDS] if project_renders else ())["delivered"]:
        Path(asked).unlink()
    held.unlink(missing_ok=True)
    src.replace(held)
    entry = {"sha256": audio_hash(held), "faults": list(ids), "asked": str(asked), "held": str(held),
             "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    mark(held, ids)
    for where in ([project_renders] if project_renders else []) + ([folder] if folder else []):
        _write(Path(where) / RECORDS, entry)
    return held


# ---- the check -------------------------------------------------------------------------------------------------------

def _records_near(p: Path) -> list[Path]:
    """refused.json beside the file and in every folder above it (also as renders/refused.json there)."""
    out = []
    for d in [p.parent, *p.parent.parents]:
        out += [d / RECORDS, d / "renders" / RECORDS]
    return [r for r in out if r.is_file()]


def check(path: str | Path, records=()) -> dict:
    """{delivered, why}: delivered False when the file is missing, carries the refusal mark, is named NOT-DONE, or a refusal
    record beside it, above it or in `records` names its samples. True means only: not a refused render."""
    p = Path(path)
    if not p.is_file():
        return {"delivered": False, "why": f"{p} does not exist."}
    said = marked(p)
    if said:
        return {"delivered": False, "why": f"{p} is a refused render (marked inside: {said}); it is not delivered.", "mark": said}
    if ".NOT-DONE" in p.name:
        return {"delivered": False, "why": f"{p} is named as a refused render (NOT-DONE); it is not delivered."}
    files = [Path(r) for r in records if Path(r).is_file()] + _records_near(p)
    if files:
        sha = audio_hash(p)
        for r in files:
            hit = next((e for e in _read(r) if e.get("sha256") == sha), None)
            if hit:
                return {"delivered": False, "record": str(r), "faults": hit.get("faults"),
                        "why": f"{p} is the same audio as a render refused at {hit.get('time')} for {', '.join(hit.get('faults') or [])} "
                               f"(asked for {hit.get('asked')}; record {r}); it is not delivered."}
    return {"delivered": True, "why": f"{p} carries no refusal mark and no refusal record names its audio."}


def stale_faults(project: Path | None, skip=()) -> list[dict]:
    """Faults for asked delivery paths (from the project's refusal record) where a refused render now sits, copied into
    place; `skip`: the paths this call writes itself."""
    if project is None:
        return []
    records = Path(project) / "renders" / RECORDS
    skipped = {str(Path(s)) for s in skip if s}
    asked = dict.fromkeys(str(Path(e["asked"])) for e in _read(records) if e.get("asked"))
    out = []
    for a in asked:
        if a in skipped or not Path(a).is_file():
            continue
        c = check(a, [records])
        if not c["delivered"]:
            out.append({"id": f"refused_copy:{Path(a).name}", "what": f"{a} is a refused render copied into place; it is not delivered",
                        "when": None, "fix": f"delete it, or deliver a clean render there (render_mix with folder {Path(a).parent}) to replace it"})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m rostrum_sound.delivered",
                                 description="Say whether an audio file is a delivery or a refused render (exit 1 when not delivered).")
    ap.add_argument("file")
    ap.add_argument("--records", nargs="*", default=[], help="more refused.json files to look in (e.g. the project's renders/refused.json)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")            # a path or mark a Windows console cannot print
    c = check(a.file, a.records)
    print(json.dumps(c) if a.json else ("DELIVERED: " if c["delivered"] else "NOT DELIVERED: ") + c["why"])
    return 0 if c["delivered"] else 1


if __name__ == "__main__":
    sys.exit(main())
