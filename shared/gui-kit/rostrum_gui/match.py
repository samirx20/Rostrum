"""The one word match, for the command bar and the settings panel's search alike (no Qt)."""
from __future__ import annotations

import re


def starts(words: list[str], text: str) -> bool:
    """Every word (lower case) starts a word of the text: "move" finds "move it", never "remove"."""
    return all(re.search(r"(?<![a-z0-9])" + re.escape(w), text) for w in words)
