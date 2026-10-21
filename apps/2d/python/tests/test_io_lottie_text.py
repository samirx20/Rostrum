"""Lottie export: a text never silently vanishes. It is exported as glyph outlines, or (font not found) the report
says so by name."""
from rostrum2d import fields as F
from rostrum2d.io.lottie import to_lottie


def _export(**props):
    layer = {"id": "title", "type": "text", "props": {**F.defaults("text"), "body": "Hi", "font": "Inter", **props}}
    comp = {"id": "c", "type": "comp", "props": {**F.defaults("comp")}, "layers": [layer]}
    lottie, report = to_lottie({"format": "rostrum-2d-scene", "version": 1, "comp": comp})
    return next((l for l in lottie["layers"] if l["nm"] == "title"), None), report


def test_text_becomes_glyph_outlines():
    layer, _ = _export()
    assert layer and len(layer["shapes"][0]["it"]) > 2          # glyph contours, a fill, the group transform


def test_a_missing_font_is_reported_not_dropped_silently():
    layer, report = _export(font="No Such Font")
    assert layer is None and any('"title"' in r and "No Such Font" in r for r in report)
