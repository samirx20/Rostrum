"""What an export takes, for every format: the formats and what each carries (`formats`, from io/formats.py plus the two
data formats, Lottie and motion samples), and the one settings rule (`settings`) the render_export and render_video
tools and the screen's Export sheet all go through: defaults filled, a setting a format can't take refused. No drawing
here; exporting.py runs the export."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes

from rostrum2d.io import formats as table

LABELS = {"mp4": "MP4 (H.264)", "prores4444": "ProRes 4444", "webm": "WebM (VP9)", "gif": "GIF", "png": "PNG sequence", "exr": "EXR sequence (for the Editor)", "lottie": "Lottie (JSON)",
          "motion": "Motion samples (for RostrumSound)"}
DATA = ("lottie", "motion")
# The MP4 quality arguments, as render_export and render_video both take them.
QUALITY_ARGS = {
    "quality": {"type": "string", "enum": list(table.QUALITY), "description": f"mp4 only: how much detail the file keeps (default {table.DEFAULT_QUALITY}; the encoder's constant quality: each frame gets the bits its picture needs, so simple motion graphics stay small and a busy shot keeps its detail)."},
    "bitrate": {"type": "number", "exclusiveMinimum": 0, "maximum": table.MAX_MBIT, "description": "mp4 only: an exact bitrate in Mbit/s, instead of quality."}}                # not pictures: no engine, never a versioned picture render


# The GIF arguments, as render_export takes them (a GIF is for chats and pages: size and rate decide its weight).
GIF_ARGS = {
    "size": {"type": "string", "enum": list(table.GIF_SIZES), "description": f"gif only: full | half | 480 (480 px wide) of the scene's size (default {table.GIF_DEFAULTS['size']}; a full-HD GIF is tens of MB)."},
    "rate": {"type": "string", "enum": list(table.GIF_RATES), "description": f"gif only: 15 (frames a second) | scene (the scene's own rate; default {table.GIF_DEFAULTS['rate']})."}}


def formats() -> list[dict]:
    """Every format and what it takes: alpha (can carry it), depths (bits; first = default), range (start / end apply),
    sequence (one file per frame, written into a folder), qualities (the quality choices it takes; quality = the default)."""
    rows = [{"name": n, "label": LABELS.get(n, n), "ext": f.ext, "alpha": f.alpha, "depths": list(f.depths), "range": True,
             "sequence": not f.video, "qualities": list(f.qualities), "quality": table.DEFAULT_QUALITY if f.qualities else None}
            for n, f in table.FORMATS.items()]
    return rows + [{"name": n, "label": LABELS[n], "ext": ".json", "alpha": False, "depths": [], "range": False, "sequence": False,
                    "qualities": [], "quality": None} for n in DATA]


def info(where: str, fmt: str) -> dict:
    row = next((r for r in formats() if r["name"] == fmt), None)
    if row is None:
        raise RostrumError(codes.BAD_ARGUMENT, where, f'format "{fmt}"', "is not an export format", [r["name"] for r in formats()])
    return row


def see_through(background) -> bool:
    """Is the composition's background transparent ("transparent" / "none" / empty, or a colour with zero alpha)?"""
    b = str(background or "").strip().lower()
    return b in ("", "none", "transparent") or (b.startswith("#") and len(b) == 9 and b.endswith("00"))


def settings(where: str, fmt: str, duration: float, alpha=None, depth=None, start=None, end=None, quality=None, bitrate=None,
             background="#000000", sound=None, size=None, rate=None) -> dict:
    """The settings that apply to `fmt`, defaults filled; one that doesn't apply (alpha on mp4, depth on gif, quality on png, any on
    Lottie) is refused. `bitrate` (Mbit/s, exact) replaces `quality`. Transparency defaults on only where the format can carry
    it and the composition's `background` is transparent (a solid background has nothing to keep). `sound`: the Sound item
    whose mix goes under the picture (project_sound.song; MP4 only, io/export_sound.py), None for a silent file. `size` and `rate`
    (GIF only: table.GIF_SIZES, GIF_RATES) are filled with the GIF defaults."""
    row = info(where, fmt)
    bad = lambda what, why: RostrumError(codes.BAD_ARGUMENT, where, what, why)
    if alpha and not row["alpha"]:
        raise bad("transparency", f"{fmt} cannot carry transparency; use one of " + ", ".join(r["name"] for r in formats() if r["alpha"]))
    if depth is not None and depth not in row["depths"]:
        raise bad(f"depth {depth}", f"{fmt} takes " + (" or ".join(map(str, row["depths"])) + " bits per channel" if row["depths"] else "no bit depth"))
    start, end = 0.0 if start is None else start, duration if end is None else end
    if not row["range"] and (start, end) != (0.0, duration):
        raise bad(f"range for {fmt}", f"{fmt} always holds the whole composition")
    if not 0 <= start < end <= duration + 1e-9:
        raise bad(f"range {start}–{end} s", f"must satisfy 0 <= start < end <= {duration} (the composition's length)")
    if (quality is not None or bitrate is not None) and not row["qualities"]:
        raise bad("quality / bitrate", f"{fmt} takes no quality or bitrate; only " + ", ".join(r["name"] for r in formats() if r["qualities"]))
    if quality is not None and quality not in row["qualities"]:
        raise RostrumError(codes.BAD_ARGUMENT, where, f'quality "{quality}"', "is not a quality choice", row["qualities"])
    if bitrate is not None and not 0 < bitrate <= table.MAX_MBIT:
        raise bad(f"bitrate {bitrate:g} Mbit/s", f"must be above 0 and at most {table.MAX_MBIT}")
    if (size is not None or rate is not None) and fmt != "gif":
        raise bad("size / rate", f"{fmt} has no size or rate to choose; only gif does")
    for what, got, words in (("size", size, table.GIF_SIZES), ("rate", rate, table.GIF_RATES)):
        if got is not None and got not in words:
            raise RostrumError(codes.BAD_ARGUMENT, where, f'GIF {what} "{got}"', "is not a choice", list(words))
    if sound and fmt != "mp4":
        raise bad("sound", f"{fmt} carries no sound; only mp4 does")
    return {"sound": sound or None, "alpha": row["alpha"] and see_through(background) if alpha is None else bool(alpha), "depth": depth or (row["depths"][0] if row["depths"] else None),
            "start": start, "end": end, "quality": quality or row["quality"], "bitrate": bitrate,
            "gif": {"size": size or table.GIF_DEFAULTS["size"], "rate": rate or table.GIF_DEFAULTS["rate"]} if fmt == "gif" else None}
