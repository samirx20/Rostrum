"""How a look is drawn: at preview quality by default, the picture the canvas shows while the person scrubs or plays
(one motion-blur step, drawn at the look's own size), so any moment of any film comes back in well under a second; or,
when the agent asks for it, at final quality, exactly as the export draws that frame (every motion-blur step). The one
difference between the two is motion blur (engine `shutterSamples`); everything else (camera, depth of field,
transitions, paint, text) is drawn the same. Each look's reply says which it was in one line."""
from __future__ import annotations

PREVIEW, FINAL = "preview", "final"

QUALITY = {"quality": {"type": "string", "enum": [PREVIEW, FINAL], "default": PREVIEW,
                       "description": 'preview (default): the picture the canvas shows while scrubbing, back in well under a '
                                      'second; everything is drawn as in the export except motion blur. final: this moment '
                                      'exactly as the export draws it, motion blur included (slower on blurred films).'}}


def samples(quality: str | None) -> int | None:
    """The engine's motion-blur steps for a look: 1 at preview quality, the composition's own (None) at final."""
    return None if quality == FINAL else 1


def blurred(comp: dict) -> bool:
    """The composition has motion blur (its shutter is open), so a preview look leaves something out."""
    return bool(comp.get("shutter", 0.0))


def line(comp: dict, quality: str | None) -> str:
    """The reply's one plain line on how the look was drawn."""
    if quality == FINAL:
        return "Final quality: drawn as the export draws it."
    if blurred(comp):
        return ('Preview quality (as the canvas shows it while scrubbing): the same picture as the export but without '
                'motion blur; quality "final" adds it.')
    return "Preview quality (as the canvas shows it while scrubbing): this composition has no motion blur, so it is the export's picture."
