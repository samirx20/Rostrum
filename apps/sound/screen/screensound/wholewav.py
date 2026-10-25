"""Is this file a whole WAV? The player is only ever handed a render that is: a RIFF header is there and the file is
as long as that header says (a partial or empty file is not). One place for the check, used by the renderer."""
from __future__ import annotations

import os
import struct
from pathlib import Path


def is_whole_wav(path) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(12)
        return len(head) == 12 and head[:4] == b"RIFF" and head[8:12] == b"WAVE" and \
            struct.unpack("<I", head[4:8])[0] + 8 == os.path.getsize(path)
    except OSError:
        return False


def require_whole_wav(path):
    """The path, when it is a whole WAV; else a loud error (nothing partial reaches the player)."""
    if not is_whole_wav(path):
        raise RuntimeError(f"the engine's render at {Path(path)} is not a whole WAV")
    return path
