"""rostrum-2d, the 2D agent surface (2026-10-30): markup films behind three tools. `python -m rostrum2d.mcp` starts it
(ROSTRUM2D_TOOLSET=classic starts the older 28-tool document server, kept for comparison only).

    run_film      save + run a film script, answer with a contact sheet
    look_film     frames at any times (the live engine, ~0.1-0.3 s a frame), a sheet, review notes, or a guide section
    render_film   the MP4, every frame, with the project's sound (RostrumSound's main mix) under it, and a review sheet

The project folder is the one this agent session's other Rostrum apps opened (agent_last.film), so voice lines,
music and markers made in RostrumSound are this film's; else a scratch project of its own.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from rostrum_core import agent_last, agent_start
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import App, Guides, Reply, Runtime, Tools, build_server
from rostrum_core.mcp.sheet import contact_sheet, scaled_copy, tile_width

from . import render, runner

GUIDES = Path(__file__).resolve().parents[3] / "guides" / "markup"
INSTRUCTIONS = ("rostrum-2d makes 2D films written as HTML + inline SVG + CSS from Python: keys on any attribute or "
                "CSS value, a camera, light and grain on shapes, true motion blur, lip sync to RostrumSound voices. Read "
                "look_film {guide: true} first (one short page). Loop: run_film (a contact sheet comes back), look_film at the "
                "moments that matter at full size, change the script, run_film again under the same name; render_film to "
                "deliver. Every reply ends with a clock line.")
_STATE: dict = {"session": None, "folder": None}


def folder() -> Path:
    row = agent_last.film()
    if row:
        return Path(row["folder"])
    if _STATE["folder"] is None:
        f = agent_start.scratch_folder("rostrum-2d-markup")
        f.mkdir(parents=True)
        _STATE["folder"] = f
    return Path(_STATE["folder"])


def session() -> render.Session:
    s = _STATE["session"]
    if s is None or s.proc.poll() is not None:
        s = _STATE["session"] = render.Session(folder() / "logs" / "markup-engine.log")
    return s


def _film(name: str, code: str | None, file: str | None = None):
    """The film `name`: its script sent as `code` (saved as films/<name>.py), a `file` the agent keeps and edits
    itself (remembered for the name), or the last one it ran."""
    f = folder()
    link = runner.films_dir(f) / f"{name}.file"
    if file is not None:
        p = Path(file)
        if not p.is_absolute() or not p.is_file():
            raise RostrumError(codes.NOT_FOUND, "film", "file", f"{file} is not an existing script (an absolute path to a .py)")
        link.write_text(str(p), encoding="utf-8")
        path = p
    elif code is not None:
        link.unlink(missing_ok=True)
        path = runner.save(f, name, code)
    else:
        path = Path(link.read_text(encoding="utf-8").strip()) if link.is_file() else runner.films_dir(f) / f"{name}.py"
    if not path.is_file():
        raise RostrumError(codes.NOT_FOUND, "film", f'"{name}"', "has no script yet: send its code or file with run_film")
    try:
        return runner.load(path, f), path
    except runner.ScriptError as e:
        raise RostrumError(codes.BAD_ARGUMENT, "film script", name, str(e)) from None


def _sheet(film, times: list[float], name: str, width: int, cols: int) -> tuple[Path, float, list[Path]]:
    """The frames at `times` as one picture (a still or a contact sheet), ms a frame, and each frame's full-size file."""
    out = folder() / "looks" / f"{name}-{datetime.now():%H%M%S%f}"
    t0 = time.perf_counter()
    try:
        shots = render.stills(session(), film, times, out)
    except render.RenderError as e:
        raise RostrumError(codes.RENDER_FAILED, "look", name, str(e)) from None
    ms = (time.perf_counter() - t0) * 1000 / max(1, len(times))
    frames = [p for p, _ in shots]
    if len(shots) == 1:
        p = out / "look.png"
        scaled_copy(shots[0][0], width, p)
        return p, ms, frames
    sheet = out / "sheet.png"
    contact_sheet([(p, f"{t:.2f} s") for p, t in shots], tile_width(width, cols), cols, sheet)
    return sheet, ms, frames


_UNMEASURED = " Shapes inside an <svg> are not measured one by one: judge their edges in the pictures."


def _review(film, times: list[float], frames: list[Path]) -> list[str]:
    """Plain observations on these frames (cut edges, covered text, near-empty or unmoving stretches): information only."""
    from . import review
    try:
        return review.notes(session(), film, times, frames)
    except render.RenderError as e:
        raise RostrumError(codes.RENDER_FAILED, "look", "notes", str(e)) from None


# The engine's own words (what a browser can't draw from the same markup), named in run_film's reply while a film
# doesn't use them yet: information, never a prompt (the bench: 1 of 7 final scripts used any).
_WORDS = [("light", lambda f, m: bool(f._light) or "data-light" in m, 'data-light / film.light()'),
          ("grain", lambda f, m: bool(getattr(f, "_grain", None)) or "data-grain" in m, 'data-grain / film.grain()'),
          ("camera", lambda f, m: bool(f._cam), "film.camera()"),
          ("motion blur", lambda f, m: bool(f.blur_samples), "film.blur()")]


def _unused(film, t: float) -> str:
    """`t`: a time to read the film's own markup at (before Rostrum's words are turned into filters)."""
    def at(part):
        return (part(t) if callable(part) else part) or ""
    markup = at(film._scene) + at(film._overlay)
    left = [w for name, used, w in _WORDS if not used(film, markup)]
    return f" Engine words not in this film: {', '.join(left)} (look_film {{guide: \"<word>\"}})." if left else ""


def _times(film, args, default_n: int) -> list[float]:
    if args.get("at"):
        return [min(max(0.0, float(t)), film.duration - 1e-3) for t in args["at"]][:24]
    every = args.get("every")
    n = min(24, int(film.duration / every) + 1) if every else default_n
    step = film.duration / n
    return [round(step * (i + 0.5), 3) for i in range(n)]


def _notes(film) -> str:
    return (" Notes: " + "; ".join(film.notes[:8]) + ".") if film.notes else ""


tools = Tools()
GUIDE = "markup"


@tools.tool("run_film", {"properties": {
    "name": {"type": "string", "description": "The film's name (its script is saved as films/<name>.py; run again with the same name to replace it)."},
    "code": {"type": "string", "description": "The whole Python script; it replaces the saved one before it runs. It must leave `film = Film(...)` set up. Omit to re-run the saved script."},
    "file": {"type": "string", "description": "Or a script file you keep and edit yourself (absolute path to a .py); remembered for this name."},
    "at": {"type": "array", "items": {"type": "number"}, "description": "Seconds to show on the sheet (default: 8 across the film)."},
    "width": {"type": "integer", "description": "Sheet width px (default 1600)."}}, "required": ["name"]})
def run_film(ctx, args):
    """Save and run a markup film script (HTML + inline SVG + CSS from Python; look_film {guide: true}) and see it: a
    contact sheet of frames drawn by the engine. Errors name the script line."""
    film, path = _film(args["name"], args.get("code"), args.get("file"))
    times = _times(film, args, 8)
    sheet, ms, _ = _sheet(film, times, args["name"], args.get("width", 1600), 4)
    from .gaps import notes
    mid = film.markup(times[len(times) // 2])
    for n in notes(mid):
        if n not in film.notes:
            film.notes.append(n)
    keyed = len(film._keys)
    return Reply(f'Film "{args["name"]}": {film.duration:g} s, {film.width}×{film.height} at {film.fps:g} fps, {keyed} keyed '
                 f'element{"s" * (keyed != 1)}{", motion blur on" if film.blur_samples else ""}; {len(times)} frames, '
                 f'{ms:.0f} ms a frame.{_notes(film)}{_unused(film, times[len(times) // 2])} Next: look_film at the moments that matter at full size '
                 f'(at: [s]) and judge them as a client would, or across the film with notes (every: 2, notes: true); '
                 f'change the script and run_film again.',
                 {"script": str(path), "times": times, "msPerFrame": round(ms), "notes": film.notes}, files=[sheet], images=[sheet])


@tools.tool("look_film", {"properties": {
    "name": {"type": "string"},
    "at": {"type": "array", "items": {"type": "number"}, "description": "Seconds. One time: one full-size still."},
    "every": {"type": "number", "description": "A frame every N seconds across the whole film (a review sheet)."},
    "notes": {"type": "boolean", "description": "Also say what these frames show that a client would notice: text cut by the frame edge, text covered by another element, near-empty frames, stretches where nothing moves."},
    "guide": {"type": ["boolean", "string"], "description": "Read the guide instead: true for the start page, or a section's heading words (\"keys\", \"light\", \"sound\")."},
    "width": {"type": "integer", "description": "Picture width px (default: 1920 for one still, 1600 for a sheet)."},
    "columns": {"type": "integer", "description": "Sheet columns (default 3)."}}})
def look_film(ctx, args):
    """See the film as the export will draw it (same engine, same frame): one still at full size, a few chosen times, or
    a frame every N seconds across the whole film to review it end to end; notes say what a client would notice. Or
    read the guide. Changes nothing."""
    if args.get("guide") not in (None, False):
        g, sec = ctx.app.guides, args["guide"]
        text = g.part(GUIDE, None if sec is True or sec in ("", "start") else str(sec), cap=2600)
        text = text.replace('Ask with `section` (words of its heading), or section: "all".',
                            'Ask with look_film {guide: "<heading words>"}, or guide: "all".')
        return Reply(text, {"guide": GUIDE, "section": None if sec is True else sec})
    if not args.get("name"):
        raise RostrumError(codes.BAD_ARGUMENT, "look_film", "name", "names the film to look at (or send guide)")
    film, _ = _film(args["name"], None)
    times = _times(film, args, 12)
    width = args.get("width", 1920 if len(times) == 1 else 1600)
    pic, ms, frames = _sheet(film, times, args["name"], width, args.get("columns", 3))
    seen = _review(film, times, frames) if args.get("notes") else []
    # What the notes measure: HTML elements with an id; shapes inside an <svg> only as the whole <svg> (the engine's
    # boxes stop there), so a cut clock drawn in SVG goes unsaid; the line says so rather than "nothing is cut".
    said = (" Seen: " + "; ".join(seen) + "." + _UNMEASURED) if seen else (
        " Seen: no HTML text or box with an id is cut, covered or empty in these frames." + _UNMEASURED if args.get("notes") else "")
    return Reply(f'{len(times)} frame{"s" * (len(times) != 1)} of "{args["name"]}" at {", ".join(f"{t:g}" for t in times)} s, '
                 f'{ms:.0f} ms a frame.{said}{_notes(film)}', {"times": times, "msPerFrame": round(ms), "seen": seen},
                 files=[pic], images=[pic])


@tools.tool("render_film", {"properties": {
    "name": {"type": "string"},
    "file": {"type": "string", "description": "The MP4 to write (absolute path)."},
    "quality": {"type": "string", "enum": ["draft", "standard", "high"], "description": "Default high."},
    "sound": {"type": "boolean", "description": "Put the project's sound (RostrumSound's main mix) under it. Default: yes when the project has one."}},
    "required": ["name", "file"]})
def render_film(ctx, args):
    """Export the film to MP4: every frame through the same engine as the looks, then the project's sound under it."""
    film, _ = _film(args["name"], None)
    out = Path(args["file"])
    if not out.is_absolute() or out.suffix.lower() != ".mp4":
        raise RostrumError(codes.BAD_ARGUMENT, "render_film", "file", "must be an absolute path ending in .mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    f = folder()
    from .. import project_sound
    song = None if args.get("sound") is False else project_sound.song(str(f))
    if args.get("sound") and song is None:
        raise RostrumError(codes.BAD_ARGUMENT, "render_film", "sound", "was asked, but the project has no RostrumSound item",
                           hint=project_sound.where_the_music_is(str(f)))
    # The mix is made before any frame is drawn: a song that can't be mixed fails now, not after the whole picture.
    from ..io import export_sound
    wav, silent_why = None, ""
    if song:                                    # an empty song (nothing written in it yet): picture only, said plainly
        from rostrum_sound import soundtrack
        if not (soundtrack.facts(str(f), song["id"]) or {}).get("seconds"):
            song, silent_why = None, f' Silent: the project\'s song "{song.get("name", song["id"])}" in RostrumSound has no sound yet.'
    if song:
        try:
            wav = export_sound.mix(str(f), song["id"])
        except Exception as e:                      # noqa: BLE001 — said, never swallowed
            if args.get("sound"):
                raise RostrumError(codes.RENDER_FAILED, "render_film", "sound", f"the project's sound could not be mixed: {e}") from None
            song, silent_why = None, f" Silent: the project's sound could not be mixed ({e}); make it in RostrumSound first."
    part = out.with_name(out.stem + ".partial" + out.suffix)
    try:
        done = render.export(film, out, f / "logs" / "markup-export.log", args.get("quality", "high"))
        if song:
            export_sound.attach(part, str(f), song["id"], 0.0, film.duration, wav=wav)
        part.replace(out)
    except (render.RenderError, RuntimeError) as e:
        raise RostrumError(codes.RENDER_FAILED, "render_film", args["name"], str(e)) from None
    finally:
        part.unlink(missing_ok=True)            # never a half-made file beside the person's
    mb = out.stat().st_size / 2 ** 20
    return Reply(f'Wrote {out} ({done["frames"]} frames, {mb:.1f} MB, {"with sound " + song["id"] if song else "silent"}) in '
                 f'{done["seconds"]:g} s.{silent_why}{_notes(film)} To review it end to end: look_film every: 2 (it draws the same frames).',
                 {"file": str(out), **{k: v for k, v in done.items() if k != "partial"}}, files=[out])


def main():
    import anyio
    from mcp.server.stdio import stdio_server
    app = App("rostrum-2d", {}, instructions=INSTRUCTIONS, guides=Guides().load_folder(GUIDES))
    rt = Runtime(app)
    rt.tools = tools
    from . import loop

    def review(name):
        film, _ = _film(name, None)
        times = [round(t, 2) for t in _times(film, {"every": loop.REVIEW_EVERY}, 12)]
        png, _, frames = _sheet(film, times, name, 1600, 4)
        return png, times, _review(film, times, frames)
    loop.wrap(tools, review)
    server = build_server(app, runtime=rt)

    async def serve():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    try:
        anyio.run(serve)
    finally:
        if _STATE["session"] is not None:
            _STATE["session"].close()


if __name__ == "__main__":
    main()
