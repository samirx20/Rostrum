"""A shot's render settings, part of the one table (item_fields.FIELDS["shot"]),
and `settings()`, the one reading of them: the Render button, render_still / render_video and render_estimate all
ask it, so what the estimate measures is what the render draws (preview ≡ export, SPEC §11.2–11.3).

Quality is a preset of the numbers (Draft 32 samples, Good 128, Final 512, noise clean-up on); Custom shows the
numbers themselves. Size is the shot's own frame size, half or double. Range: the whole shot or a stretch of it.
Save as: PNG, EXR (for the Editor) or both; with an EXR, the Passes it carries as layers (SPEC §11.2, core passes.h),
each a switch that exists only while the shot saves an EXR (absent for PNG, never greyed).
"""
from __future__ import annotations

from .field_kit import ANY, CH, D, IS, N, S, T

QUALITIES = {"draft": {"samples": 32, "denoise": True}, "good": {"samples": 128, "denoise": True},
             "final": {"samples": 512, "denoise": True}}
SIZES = {"full": 1.0, "half": 0.5, "double": 2.0}
CUSTOM, RANGE = IS("renderQuality", "custom"), IS("renderRange", "range")
BLUR = IS("motionBlur", True)
FORMATS = {"png": ["png"], "exr": ["exr"], "both": ["png", "exr"]}
EXR = ANY("renderFormat", "exr", "both")
# pass name (the core's) -> its switch on the shot, its label, on by default; Beauty is always in the EXR
PASSES = {"light": ("passLight", "Light", False), "shadow": ("passShadow", "Shadow", False),
          "reflections": ("passReflections", "Reflections", False), "masks": ("passMasks", "Masks per item", True),
          "depth": ("passDepth", "Depth", False), "normal": ("passNormal", "Surface direction", False)}
PASS_HELP = {"light": "Light on matte surfaces. Light + Reflections + Rest (written with them: glass, glow, sky) = the picture",
             "shadow": "0 lit to 1 in full shadow, on matte surfaces. Renders each frame twice",
             "reflections": "Reflections and highlights", "masks": "One white-on-black matte per item, named by its id",
             "depth": "Distance from the camera in metres", "normal": "Which way each surface faces (world space)"}

RENDER = [
    CH("renderQuality", [*QUALITIES, "custom"], "Quality", "Render", "good", S,
       help="Draft 32 samples, Good 128, Final 512, each with noise clean-up; Custom sets the numbers"),
    N("renderSamples", "Samples", "Render", 1, 8192, 1, "", D, CUSTOM, integer=True, default=128,
      help="Cycles samples per pixel: time grows in step with them"),
    T("renderDenoise", "Noise clean-up", "Render", True, D, CUSTOM),
    CH("renderSize", list(SIZES), "Size", "Render", "full", S, help="The shot's frame size, half of it or double"),
    CH("renderRange", ["shot", "range"], "Frames", "Render", "shot", S, help="The whole shot, or a stretch of it"),
    N("renderStart", "From", "Render", 0, 36000, 0.001, "s", S, RANGE, help="Seconds from the start of the shot"),
    N("renderEnd", "To", "Render", 0, 36000, 0.001, "s", S, RANGE, default=1.0,
      help="Seconds from the start of the shot; the frame at this time is the last one"),
    CH("renderFormat", list(FORMATS), "Save as", "Render", "png", S,
       help="PNG picture, EXR layers for the Editor (scene-linear, with the passes below), or both"),
    *[T(field, label, "Passes", on, S, EXR, help=PASS_HELP[name]) for name, (field, label, on) in PASSES.items()],
    T("motionBlur", "Motion blur", "Motion blur", False, S,
      help="Things that move smear along their path, as in a real camera. Shows only in Final and in renders"),
    N("shutter", "Shutter", "Motion blur", 1, 360, 1, "°", S, BLUR, default=180.0,
      help="How long each frame is exposed: 180° is half a frame (the film look), 360° a whole frame (more smear)"),
]


def shutter_frames(shot: dict) -> float:
    """How long the shutter is open, in frames (0 = no motion blur): what the scene description's `shot.shutter`
    carries (ENGINE_CONTRACT.md § 2), so the Final look and every render blur alike."""
    return float(shot.get("shutter", 180.0)) / 360.0 if shot.get("motionBlur", False) else 0.0


def passes(shot: dict) -> list[str]:
    """The passes switched on for the shot's EXR (the core's names, in the table's order; Beauty is always there)."""
    return [name for name, (field, _, on) in PASSES.items() if shot.get(field, on)]


def settings(shot: dict, info: dict) -> dict:
    """{renderer, samples, denoise, width, height, start, end (shot frames, inclusive), formats, passes} from a shot's
    fields (defaults filled) and its compile.shot_info. Frames outside the shot are clamped into it; a range running backwards is one frame."""
    get = lambda name, default: shot.get(name, default)  # noqa: E731
    q = get("renderQuality", "good")
    nums = QUALITIES.get(q) or {"samples": int(get("renderSamples", 128)), "denoise": bool(get("renderDenoise", True))}
    k = SIZES[get("renderSize", "full")]
    w, h = max(2, round(info["width"] * k / 2) * 2), max(2, round(info["height"] * k / 2) * 2)   # even, for H.264
    f0, f1 = info["start"], info["end"]
    if get("renderRange", "shot") == "range":
        fps = info["fps"]
        f0 = min(max(info["start"] + round(get("renderStart", 0.0) * fps), info["start"]), info["end"])
        f1 = min(max(info["start"] + round(get("renderEnd", 1.0) * fps), f0), info["end"])
    return {"renderer": "cycles", "quality": q, **nums, "width": w, "height": h, "start": f0, "end": f1,
            "formats": (fmts := FORMATS[get("renderFormat", "png")]), "passes": passes(shot) if "exr" in fmts else []}
