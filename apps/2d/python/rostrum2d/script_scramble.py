"""The script call `scramble(...)`: a line of text whose characters cycle and lock, one by one, into the final words. It
is plain editable layers: a swap set (a group with One at a time on, swap.py) of texts `<id>_0` … `<id>_<n>`, one per
step, the last the final words; the group's `show` keys step through them (`rate` steps a second) from `start` to `end`.

    s = scramble("freq", "1420.405 MHZ", x=960, y=700, start=3, end=4.2, font="JetBrains Mono", size=48)
    s.set(start=3)                       # the group shows from 3 s (before `start` it holds the first jumble)
    scramble("title", "SIGNAL", start=6, end=7, order="random", chars="#%&*01", seed=4, size=200, weight=800)

Each character keeps its kind while it cycles (a capital cycles through capitals, a digit through digits; spaces and
marks stay), unless `chars=` gives the set to draw from. `order` is which letter locks first: "forward" (left to
right), "backward", "center" (from the middle out) or "random". Every text field (font, size, weight, color, tracking,
x, y, align …) goes to each text, so all steps sit in the same place; a mono font keeps the line's width still.
A number that counts up is `counter(...)` (guide ui-and-product-animation); this is for characters."""
from __future__ import annotations

import math
import random as _random
import string

ORDERS = ("forward", "backward", "center", "random")
MOST = 240          # steps (texts) in one scramble: 8 s at 30 a second


def _kind(c: str, chars: str | None) -> str:
    if chars:
        return chars
    for group in (string.ascii_uppercase, string.ascii_lowercase, string.digits):
        if c in group:
            return group
    return ""            # a space or a mark stays itself


def _ranks(body: str, order: str, rnd) -> list[int]:
    """Each character's place in the locking order (0 locks first)."""
    idx = list(range(len(body)))
    if order == "backward":
        idx.reverse()
    elif order == "center":
        mid = (len(body) - 1) / 2
        idx.sort(key=lambda i: abs(i - mid))
    elif order == "random":
        rnd.shuffle(idx)
    ranks = [0] * len(body)
    for r, i in enumerate(idx):
        ranks[i] = r
    return ranks


def for_script(build) -> dict:
    L = build.layer

    def scramble(id="scramble", body="", start=0.0, end=1.0, rate=15.0, chars=None, order="forward", seed=1, **fields):
        """A swap set of texts cycling into `body` from `start` to `end` seconds, `rate` steps a second. Returns the group."""
        where = f'scramble("{id}")'
        if not isinstance(body, str) or not body:
            raise ValueError(f"{where}: body is the final words, a non-empty string")
        if order not in ORDERS:
            raise ValueError(f'{where}: order "{order}" — it is one of {", ".join(ORDERS)}')
        if not end > start:
            raise ValueError(f"{where}: end {end} s must be after start {start} s")
        if not rate > 0:
            raise ValueError(f"{where}: rate {rate} — steps a second, above 0 (15 is a fast flicker)")
        if chars is not None and (not isinstance(chars, str) or not chars):
            raise ValueError(f"{where}: chars is a non-empty string of the characters to cycle through")
        steps = max(1, math.ceil((end - start) * rate))
        if steps + 1 > MOST:
            raise ValueError(f"{where}: {steps + 1} steps ({end - start} s at {rate} a second); at most {MOST} — lower rate")
        rnd = _random.Random(seed)
        ranks = _ranks(body, order, rnd)
        g = L("group", id, swap=True)
        with g:
            for k in range(steps + 1):
                locked = k * len(body) / steps          # characters locked at this step: all of them at the last
                line = "".join(c if ranks[i] < locked or not _kind(c, chars) else rnd.choice(_kind(c, chars))
                               for i, c in enumerate(body))
                L("text", f"{id}_{k}", body=line, **fields)
        times = {round(start + k / rate, 6): (k, "hold") for k in range(steps)}
        times[round(float(end), 6)] = (steps, "hold")
        g.key("show", times)
        return g

    return {"scramble": scramble}
