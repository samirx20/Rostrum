"""The clean-up job in a process of its own, so a person can Cancel it (DESIGN.md §3.10): ending the process stops a
model in the middle of a step, which a thread cannot be made to do. The cache publishes a step only when it is whole
(rostrum_core.cache: made under a temporary name, renamed at the end), so a stopped job leaves nothing a take could be
read from.

    python -I -m rostrum_sound.cleanup_job <spec.json>      spec = {"root": the document's data, "ids": [clip ids]}

Prints one line per event: `P <note>` (progress, the same notes as clean_clips.make_clips), then `OK`, or
`E <the error in plain words>` and exit code 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import clean_clips


def _say(tag: str, text: str = ""):
    print(f"{tag} {text}".rstrip().replace("\n", " "), flush=True)


def main(argv: list[str]) -> int:
    spec = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    try:
        clean_clips.make_clips(spec["root"], spec["ids"], progress=lambda note: _say("P", note))
    except Exception as e:  # noqa: BLE001  the screen shows it in words, whatever it was
        _say("E", getattr(e, "line", lambda: str(e))())
        return 1
    _say("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
