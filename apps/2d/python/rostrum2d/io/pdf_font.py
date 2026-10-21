"""A PDF text run's font → (family, weight, slant). One place decides it, for every run (pdf.py `_text`).

A PDF font says its style in three places, and none is reliable alone: the BaseFont name ("ABCDEF+Inter-SemiBoldItalic",
"Arial,Bold", "Helvetica-BoldOblique"), the descriptor's Flags (bit 19 ForceBold, bit 7 Italic) and ItalicAngle, and
a stem width pdfium turns into a weight (0 when the file has none; rough, so snapped to a hundred). Order: the name's own words win (they are what the
designer wrote), then ForceBold, then pdfium's weight; italic is any of name / Italic flag / a non-zero ItalicAngle.
"""
from __future__ import annotations

import ctypes
import re

import pypdfium2.raw as R

FORCE_BOLD, ITALIC = 1 << 18, 1 << 6        # descriptor Flags bits 19 and 7 (1-based)
WEIGHTS = [("extrabold", 800), ("ultrabold", 800), ("semibold", 600), ("demibold", 600), ("extralight", 200),
           ("ultralight", 200), ("hairline", 100), ("thin", 100), ("black", 900), ("heavy", 900), ("bold", 700),
           ("medium", 500), ("light", 300), ("regular", 400), ("normal", 400), ("book", 400), ("roman", 400)]
DEFAULT_SLANT = -12.0                        # a font that says "italic" without an angle (the field: negative leans right)


def split_name(base: str) -> tuple[str, str]:
    """"ABCDEF+Arial-BoldItalicMT" → ("Arial", "bolditalicmt"): family before the first - or , (a PS / MT foundry tag
    dropped from it), the style words after it, lower-cased."""
    name = base.split("+")[-1]
    family, style = (re.split(r"(?<=\w)[-,]", name, maxsplit=1) + [""])[:2]
    return re.sub(r"(?<=[a-z])(MT|PS)$", "", family) or name, style.lower()


def style_of(base: str, flags: int, angle: float, stem_weight: float) -> tuple[str, float, float]:
    """(family, weight 1–1000, slant degrees; 0 upright) from a BaseFont name, descriptor Flags, ItalicAngle, pdfium's weight."""
    family, words = split_name(base)
    weight = next((w for key, w in WEIGHTS if key in words), None)
    if weight is None:
        weight = 700.0 if flags & FORCE_BOLD else (float(round(stem_weight / 100) * 100) if 100 <= stem_weight <= 900 else 400.0)
    italic = any(k in words for k in ("italic", "oblique", "slanted", "kursiv")) or bool(flags & ITALIC) or bool(angle)
    return family, float(weight), (float(angle) or DEFAULT_SLANT) if italic else 0.0


def of_text_object(obj) -> tuple[str, float, float]:
    """The style of a pypdfium2 text object's font."""
    font = obj.get_font()
    angle = ctypes.c_int()
    R.FPDFFont_GetItalicAngle(font.raw, angle)
    return style_of(font.get_base_name(), R.FPDFFont_GetFlags(font.raw), float(angle.value), font.get_weight())
