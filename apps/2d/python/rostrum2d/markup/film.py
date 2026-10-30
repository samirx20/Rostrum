"""A markup film: what an agent's script makes. HTML + inline SVG + CSS for the picture, Rostrum's keys on any
attribute or CSS value, a camera, light on shapes, true motion blur, lip sync and the project's markers on top.

    film = Film(1920, 1080, fps=30, duration=30, background="#0d0f14")
    film.css(".card { border-radius: 24px; box-shadow: 0 30px 80px #0008 }")
    film.scene(lambda t: f'<svg width="1920" height="1080">…<circle id="sun" cx="960" cy="400" r="{80 + 10 * t}"/></svg>')
    film.key("#sun", cy={0: 700, 2: (400, "snappy")}, fill={0: "#ff8a3d", 2: "#ffd36e"})
    film.camera(x={0: 960, 4: 1100}, zoom={0: 1, 4: (1.4, "smooth")})
    film.light(angle={0: -60, 30: 40})          # any data-light element is shaded by it
    film.grain(amount=.12)                       # film grain on the whole frame (data-grain: one element)

Per frame (`markup(t)`): the scene's markup at t → keys put on their elements → the camera (each data-depth at its
own depth) → the light filters → the grain → the overlay (screen-fixed) → the whole-frame grain. The engine draws exactly that markup (rostrum2d-render serve, `frame {stage}`).
"""
from __future__ import annotations

from typing import Callable

from rostrum_core.byname import expand_icons

from . import apply, depth, grain as grain_mod, light as light_mod, normal
from .values import Keys

_CAM = ("x", "y", "zoom", "rotate", "focus", "aperture")
CURRENT_FOLDER = None                           # the project folder a script runs in (runner.py sets it)


def _as_keys(v):
    if isinstance(v, Keys):
        return v
    if isinstance(v, dict):
        return Keys(v)
    return lambda t, v=v: v                     # a still value


def _named(values: tuple, order: dict, what: str) -> dict:
    """Values given without names, in the order the fields are listed."""
    if len(values) > len(order):
        raise ValueError(f"{what} takes at most {len(order)} values in order ({', '.join(order)}); got {len(values)}")
    return dict(zip(order, values))


class Film:
    def __init__(self, width: int = 1920, height: int = 1080, fps: float = 30, duration: float = 10,
                 background: str = "#000000"):
        if width <= 0 or height <= 0 or fps <= 0 or duration <= 0:
            raise ValueError(f"Film({width}, {height}, fps={fps}, duration={duration}): every number must be above 0")
        self.width, self.height, self.fps, self.duration, self.background = int(width), int(height), fps, duration, background
        self._css: list[str] = []
        self._scene: Callable[[float], str] | str = ""
        self._overlay: Callable[[float], str] | str = ""
        self._keys: dict[str, dict[str, object]] = {}
        self._cam: dict[str, object] = {}
        self._light: dict[str, object] = {}
        self._grain: dict[str, object] = {}
        self._grain_frame = False
        self.blur_shutter, self.blur_samples = 0.0, 0
        self._shutter = None                    # keys or a still value, degrees
        self._cuts: list[float] = []
        self.notes: list[str] = []
        self.folder = CURRENT_FOLDER            # the project folder (markers, voice lines, sound)
        self.sound = None                       # True / False / None (default: the project's main mix when it has one)
        self.random = None                      # (generator, state): runner.py; draws in scene(t) are fixed per t

    # --- the picture ---
    def css(self, text: str):
        """Add a stylesheet (any CSS: classes, @font-face, variables)."""
        self._css.append(text)
        return self

    def scene(self, markup):
        """The world: a markup string, or a function of t (seconds) returning markup. Usable as a decorator."""
        self._scene = markup
        return markup

    def overlay(self, markup):
        """Markup fixed to the screen, over the world and outside the camera (titles, captions, letterbox)."""
        self._overlay = markup
        return markup

    def key(self, selector: str, **props):
        """Key properties of the element with id `selector` ("#arm" or "arm"): film.key("#arm", rotate={0: 0, 1: (40,
        "snappy")}, origin="120 80", fill={0: "#fff", 2: "#f80"}). Any attribute (SVG) or CSS property (HTML); x, y,
        rotate, scale, scaleX, scaleY, skewX, origin are the transform; "--name" a CSS variable; underscores in names
        are dashes (stop_color = stop-color). A plain value (not a dict) is a still value."""
        ident = selector.removeprefix("#")
        slot = self._keys.setdefault(ident, {})
        for k, v in props.items():
            name = k if k.startswith("--") else k.replace("_", "-")
            slot[name] = _as_keys(v)
        return self

    def camera(self, **fields):
        """The camera: x, y (the world point at the frame's centre; default the frame's centre), zoom (1 = the world at
        its own size), rotate (degrees), focus (a depth) and aperture (px of blur per unit of depth away from focus).
        Each a value or keys {t: value}. Elements with data-depth move by their depth (depth.py)."""
        bad = set(fields) - set(_CAM)
        if bad:
            raise ValueError(f"camera fields are {', '.join(_CAM)}; not {', '.join(sorted(bad))}")
        self._cam.update({k: _as_keys(v) for k, v in fields.items()})
        return self

    def light(self, *values, **fields):
        """The light every `data-light` element is shaded by: angle (degrees, where it comes from: 0 above, 90 right),
        elevation (degrees above the picture, 90 = straight on: flat), colour, shadow (the colour of the turned-away
        side), strength, soft (px: how round forms read; small = an edge bevel, large = a pillowed form), cast (px:
        shadow offset; 0 = none), castBlur, castColour, castOpacity. Numbers may be keys. An element's own
        data-light="soft: 40; cast: 20" wins over these. Values without names go in that order (angle, elevation, …)."""
        fields = {**_named(values, light_mod.DEFAULTS, "light"), **fields}
        bad = set(fields) - set(light_mod.DEFAULTS)
        if bad:
            raise ValueError(f"light fields are {', '.join(light_mod.DEFAULTS)}; not {', '.join(sorted(bad))}")
        self._light.update({k: _as_keys(v) for k, v in fields.items()})
        return self

    def grain(self, *values, frame: bool = True, **fields):
        """Film grain (the engine's grain shader): amount (0.1 fine film, 0.4 rough), size (px), seed, colour (1: each
        colour its own grain), smooth (0: square cells), still (1: the same each frame). Numbers may be keys. These
        are also the settings every `data-grain` element starts from (its own data-grain="amount: .3" wins).
        frame=True grains the whole frame (world and overlay, background included); frame=False only sets them. Values
        without names go in that order: film.grain(.06, 1.6) = amount .06, size 1.6."""
        fields = {**_named(values, grain_mod.DEFAULTS, "grain"), **fields}
        bad = set(fields) - set(grain_mod.DEFAULTS)
        if bad:
            raise ValueError(f"grain fields are {', '.join(grain_mod.DEFAULTS)}; not {', '.join(sorted(bad))}")
        self._grain.update({k: _as_keys(v) for k, v in fields.items()})
        self._grain_frame = bool(frame)
        return self

    def blur(self, shutter=180, samples: int = 8):
        """True motion blur: each frame is `samples` pictures across the shutter (degrees; 180 = half a frame), averaged.
        `shutter` may be keys ({t: degrees}; 0 over a stretch turns it off there). blur(0) turns it off."""
        if isinstance(shutter, (int, float)) and shutter <= 0:
            self._shutter, self.blur_shutter, self.blur_samples = None, 0.0, 0
            return self
        self._shutter = _as_keys(shutter)
        self.blur_shutter, self.blur_samples = float(self._shutter(0) or 0), int(samples)
        return self

    def cut(self, *times: float):
        """Hard cuts at these seconds: a frame's motion-blur samples never reach across one (no two shots in one frame)."""
        self._cuts = sorted(set(self._cuts) | {float(t) for t in times})
        return self

    # --- time and sound from the project ---
    def marker(self, ref: str) -> float:
        """Seconds of a project marker ("drop", "drop+0.5"): RostrumSound's moments and the project's markers."""
        if not self.folder:
            raise ValueError(f'marker("{ref}"): no project is open, so there are no markers')
        from rostrum_core import markers
        return markers.at(self.folder, ref)

    def lipsync(self, source: str, at: float = 0.0, text: str | None = None, pronounce: dict | None = None) -> "Mouth":
        """Mouth shapes for a voice clip: "voice:<line id>" (a RostrumSound voice line of this project) or a WAV path,
        starting at `at` s; `pronounce` {"word": "ARPAbet"} for words the dictionary lacks. Returns mouth(t) -> "X"
        (rest) or "A".."H" (Preston Blair shapes; look_film {guide: "sound"})."""
        from rostrum_core.lipsync.track import track
        from ..lipsync import voice_line
        wav, words = voice_line.resolve(source, self.folder, "lipsync")
        out = track(wav, at, self.fps, text=text or words, pronounce=pronounce)
        return Mouth(out["cues"], out["words"])

    # --- per frame ---
    def _props_at(self, t: float) -> dict[str, dict]:
        return {i: {k: v(t) for k, v in props.items()} for i, props in self._keys.items()}

    def _seed_at(self, t: float):
        """Seed the script's `random` for the moment t: the same draws at the same t however often and in whatever
        order frames are drawn (looks, export, blur samples), and new ones the next moment."""
        if self.random:
            rnd, state = self.random
            rnd.setstate(state)
            rnd.seed(f"{rnd.random()!r}:{t:.6f}")

    def markup(self, t: float, missing: list | None = None) -> str:
        self._seed_at(t)
        world = self._scene(t) if callable(self._scene) else self._scene
        over = (self._overlay(t) if callable(self._overlay) else self._overlay) or ""
        world, over = expand_icons(world), expand_icons(over)    # <i data-lucide="…"> / <i class="ti ti-…"> -> inline SVG
        for ident, props in self._props_at(t).items():       # keys reach the world and the overlay alike
            gone: list = []
            world = apply.set_props(world, ident, props, gone)
            over = apply.set_props(over, ident, props, gone)
            if len(gone) == 2 and missing is not None:
                missing.append(ident)
        world, over = normal.svg_color(world), normal.svg_color(over)
        cam = {k: v(t) for k, v in self._cam.items()}
        if cam:                                 # first, so a lit or grained part keeps its depth (depth.py)
            world = depth.camera_wrap(world, cam, self.width, self.height)
        if self._light:
            world = light_mod.apply(world, {k: v(t) for k, v in self._light.items()})
        elif "data-light" in world:
            world = light_mod.apply(world, {})
        grain = {k: v(t) for k, v in self._grain.items()}
        frame = round(t * self.fps)
        if "data-grain" in world:
            world = grain_mod.apply(world, grain, frame)
        if "data-grain" in over:
            over = grain_mod.apply(over, grain, frame)
        if self._grain_frame:
            return grain_mod.whole(world + over, grain, frame, self.width, self.height, self.background)
        return world + over

    def samples(self, t: float) -> list[str]:
        """The stage at each shutter sub-frame (motion blur), or [] when blur is off at t. Samples stay inside the shot
        t is in (film.cut)."""
        n = self.blur_samples
        shutter = float(self._shutter(t)) if self._shutter is not None else 0.0
        if n < 2 or shutter <= 0:
            return []
        span = shutter / 360 / self.fps
        lo = max([c for c in self._cuts if c <= t], default=float("-inf"))
        hi = min([c for c in self._cuts if c > t], default=float("inf")) - 1e-6
        return [self.markup(min(max(t + span * (i / (n - 1) - 0.5), lo), hi)) for i in range(n)]

    def shell(self) -> str:
        """The page every frame's markup goes into: the app's fonts, the agent's CSS, the stage."""
        from .fonts import face_css
        base = (f"html, body {{ margin: 0; padding: 0; background: {self.background}; }} "
                f"#rostrum-stage {{ position: relative; width: {self.width}px; height: {self.height}px; overflow: hidden; "
                f"background: {self.background}; font-family: Inter, sans-serif; }} "
                "#rostrum-stage * { box-sizing: border-box; }")
        named = "\n".join(self._css) + self.markup(0) + self.markup(self.duration / 2)
        return ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>' + face_css(named) + base + "\n".join(self._css)
                + '</style></head><body><div id="rostrum-stage"></div></body></html>')


class Mouth:
    """mouth(t): the mouth shape at t ("X" rest, "A".."H"); .words: [{word, start, end}]; .talking(t): inside a word."""

    def __init__(self, cues: list[dict], words: list[dict]):
        self.cues, self.words = cues, words

    def __call__(self, t: float) -> str:
        for c in self.cues:
            if c["start"] <= t < c["end"]:
                return c.get("shape") or c.get("value") or "X"
        return "X"

    def talking(self, t: float) -> bool:
        return any(w["start"] <= t < w["end"] for w in self.words)
