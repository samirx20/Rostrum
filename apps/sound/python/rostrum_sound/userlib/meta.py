"""What a sound file says about itself: the words in its name and folder, its WAV metadata (BWF `bext`
description, iXML notes / Soundminer fields, LIST INFO title / comment / subject / keywords) and a UCS category
(Universal Category System: a file name that starts like "WHSHSwsh_..." or "UIClick_...") when it has one.
Reads only the small chunks; the audio itself is skipped by seeking.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path

INFO_TAGS = {b"INAM", b"ICMT", b"ISBJ", b"IKEY", b"IGNR", b"IPRD"}
IXML_TAGS = ("NOTE", "DESCRIPTION", "FXNAME", "CATEGORY", "SUBCATEGORY", "CATID", "KEYWORDS", "TRACK_NAME")
UCS = re.compile(r"^([A-Z]{2,5})([A-Z][a-z]+)[_\- ]")
MAX_CHUNK = 1 << 20                     # metadata chunks bigger than this are not metadata


def words(text: str) -> str:
    """Plain lower-case words: separators to spaces, numbers and version tags dropped."""
    text = re.sub(r"\.(wav|wave|flac|ogg|mp3|aif|aiff)$", "", text, flags=re.I)
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)                     # CamelCase -> Camel Case
    text = re.sub(r"([A-Za-z])(\d)", r"\1 \2", text)                     # Pack04 -> Pack 04
    text = re.sub(r"[_\-,.()\[\]|+&]+", " ", text).lower()
    return " ".join(w for w in text.split() if not re.fullmatch(r"v?\d+[a-z]?|version\d*|v", w))


def _text(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("utf-8", "replace").strip()


def _ixml(raw: bytes) -> list[str]:
    s = raw.decode("utf-8", "replace")
    out = []
    for tag in IXML_TAGS:
        out += [m.strip() for m in re.findall(rf"<{tag}>(.*?)</{tag}>", s, flags=re.S | re.I) if m.strip()]
    return out


def chunks(path) -> dict:
    """{"description": [...texts], "ucs": "WHSH" or ""} from a WAV's metadata chunks; {} for other files."""
    out: dict = {"description": []}
    p = Path(path)
    if p.suffix.lower() not in (".wav", ".wave", ".bwf"):
        return out
    with open(p, "rb") as f:
        head = f.read(12)
        if len(head) < 12 or head[:4] not in (b"RIFF", b"RF64") or head[8:12] != b"WAVE":
            return out
        while True:
            h = f.read(8)
            if len(h) < 8:
                break
            cid, size = h[:4], struct.unpack("<I", h[4:])[0]
            if cid in (b"bext", b"iXML", b"LIST") and size <= MAX_CHUNK:
                body = f.read(size)
                if cid == b"bext":
                    out["description"].append(_text(body[:256]))
                elif cid == b"iXML":
                    out["description"] += _ixml(body)
                elif body[:4] == b"INFO":
                    out["description"] += _info(body[4:])
            elif size == 0xFFFFFFFF:            # RF64 data of unknown size: nothing readable follows
                break
            else:
                f.seek(size, 1)
            if size % 2:
                f.seek(1, 1)
    out["description"] = [d for d in dict.fromkeys(out["description"]) if d]
    return out


def _info(body: bytes) -> list[str]:
    out, i = [], 0
    while i + 8 <= len(body):
        tag, n = body[i:i + 4], struct.unpack("<I", body[i + 4:i + 8])[0]
        if tag in INFO_TAGS:
            out.append(_text(body[i + 8:i + 8 + n]))
        i += 8 + n + (n % 2)
    return out


def about(path, root=None) -> dict:
    """{"name": file-name words, "folder": folder words (inside `root`), "meta": metadata words, "ucs": category,
    "description": the metadata texts as written}."""
    p = Path(path)
    m = chunks(p)
    rel = p.parent.relative_to(root).parts if root and p.parent != Path(root) else (p.parent.name,)
    ucs = UCS.match(p.name)
    return {"name": words(p.name), "folder": words(" ".join(rel)), "meta": words(" ".join(m["description"])),
            "ucs": (ucs.group(1) + ucs.group(2)) if ucs else "", "description": m["description"]}
