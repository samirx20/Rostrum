"""Tailwind layout words for the script's containers and layers (script_layout.py): `tw="flex flex-col gap-4 p-6
items-center"` is read into the same keyword arguments a script writes (`layout="column", gap=16, padding=24,
align="center"`). Only layout and box words, on Tailwind's 4 px spacing scale; explicit keyword arguments win.
An unknown word fails loudly, naming it. A data table, nothing guessed."""
from __future__ import annotations

import re

ALIGN = {"start": "start", "center": "center", "end": "end", "stretch": "stretch", "baseline": "baseline"}
JUSTIFY = {"start": "start", "center": "center", "end": "end", "between": "between", "around": "around", "evenly": "evenly"}
RADIUS = {"rounded-none": 0, "rounded-sm": 2, "rounded": 4, "rounded-md": 6, "rounded-lg": 8, "rounded-xl": 12,
          "rounded-2xl": 16, "rounded-3xl": 24, "rounded-full": 9999}
WORDS = {"flex": {"layout": "row"}, "flex-row": {"layout": "row"}, "flex-col": {"layout": "column"}, "grid": {"layout": "grid"},
         "flex-wrap": {"wrap": True}, "flex-nowrap": {"wrap": False}, "grow": {"grow": 1}, "flex-1": {"grow": 1},
         "grow-0": {"grow": 0}, "shrink": {"shrink": 1}, "shrink-0": {"shrink": 0}, "overflow-hidden": {"overflow": "hidden"},
         "overflow-visible": {"overflow": "visible"}, "absolute": {"apart": True}, "relative": {},
         **{f"items-{k}": {"align": v} for k, v in ALIGN.items()}, **{f"justify-{k}": {"justify": v} for k, v in JUSTIFY.items()},
         **{f"self-{k}": {"align_self": v} for k, v in {**ALIGN, "auto": "auto"}.items()},
         **{k: {"radius": v} for k, v in RADIUS.items()}}
SPACE = {"gap": "gap", "gap-x": "gap", "gap-y": "row_gap", "p": "padding", "px": "padding_x", "py": "padding_y", "m": "margin"}
SIZE = {"full": "100%", "fit": "fit", "auto": "fit", "screen": "100%"}


def _px(v: str, word: str) -> float:
    """A spacing value: N on the 4 px scale (2.5 -> 10 px), `px` (1 px) or `[24px]` / `[24]`."""
    if v == "px":
        return 1.0
    m = re.fullmatch(r"\[(-?\d+(?:\.\d+)?)(?:px)?\]", v)
    if m:
        return float(m.group(1))
    if re.fullmatch(r"\d+(?:\.\d+)?", v):
        return float(v) * 4
    raise ValueError(f'tw: "{word}" has a value Rostrum does not read ("{v}"): write a number on the 4 px scale '
                     '(gap-4 = 16 px) or one in brackets (gap-[18px])')


def _size(v: str, word: str):
    if v in SIZE:
        return SIZE[v]
    m = re.fullmatch(r"(\d+)/(\d+)", v)
    return f"{round(100 * int(m.group(1)) / int(m.group(2)), 4)}%" if m else _px(v, word)


def read(classes: str) -> dict:
    """The keyword arguments a string of Tailwind words means (later words win, as in a class list)."""
    out: dict = {}
    for word in str(classes).split():
        if word in WORDS:
            out.update(WORDS[word])
        elif m := re.fullmatch(r"(gap-x|gap-y|gap|px|py|p|m)-(.+)", word):
            out[SPACE[m.group(1)]] = _px(m.group(2), word)
        elif m := re.fullmatch(r"([wh])-(.+)", word):
            out[m.group(1)] = _size(m.group(2), word)
        elif m := re.fullmatch(r"grid-cols-(\d+)", word):
            out["columns"] = int(m.group(1))
        elif m := re.fullmatch(r"col-span-(\d+)", word):
            out["span"] = int(m.group(1))
        elif m := re.fullmatch(r"rounded-\[(\d+(?:\.\d+)?)(?:px)?\]", word):
            out["radius"] = float(m.group(1))
        elif m := re.fullmatch(r"bg-\[(#[0-9a-fA-F]{3,8})\]", word):
            out["bg"] = m.group(1)
        else:
            raise ValueError(f'tw: "{word}" is not a layout word Rostrum reads. It reads flex, flex-row / flex-col, grid, '
                             'grid-cols-N, flex-wrap, gap(-x/-y)-N, p / px / py-N, m-N, items-*, justify-*, self-*, grow, '
                             'shrink-0, w-/h- (full, fit, 1/2, N, [320px]), col-span-N, rounded(-N), bg-[#hex], '
                             'overflow-hidden, absolute; colours, type and the rest are keyword arguments')
    return out
