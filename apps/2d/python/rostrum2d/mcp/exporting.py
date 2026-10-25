"""The one export path for every format (mp4, prores4444, webm, gif, png and exr sequences, lottie, motion): the `render_export`
tool and the screen's Export button both take `snapshot()` and run `run()`. The formats and what each takes come from
`io/formats.py` (FORMATS) plus the two data formats (Lottie; motion: the samples RostrumSound places sounds from,
rostrum2d/motion_samples.py), and the settings rule, in export_settings.py; nothing per format is written anywhere else.
Nothing is reported as done unless the file read back right."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from rostrum_core import project
from rostrum_core.errors import RostrumError, codes

from rostrum2d import settings as app_settings
from rostrum2d.io import formats as table

from .export_settings import DATA, LABELS, QUALITY_ARGS, GIF_ARGS, formats, info, see_through, settings  # noqa: F401  (callers read them here)
from . import export_area
from .render import _fail


def snapshot(doc, comp_id: str, fmt: str, layers: list[str] | None = None) -> dict:
    """What a job exports, taken now (edits made while it runs are not in the file): the engine's scene, or for motion
    the samples themselves (read from the composition as it plays)."""
    from . import render
    if fmt != "motion":
        comp = next((c for c in doc.data.get("comps", []) if c["id"] == comp_id), None)
        if comp is not None and not any(not lay.get("hidden") for lay in comp.get("layers", [])) and not comp.get("soundtrack"):
            raise RostrumError(codes.BAD_ARGUMENT, "export", f'composition "{comp_id}"', "has nothing showing to export", hint="Add a layer (or show a hidden one) first.",
                               plain="There is nothing to export yet: the composition has no layers showing. Add one first.")
        return render.scene_of(doc, comp_id)
    import copy
    from rostrum_core import markers
    from rostrum2d import motion_samples, retime
    comp = next((c for c in doc.data.get("comps", []) if c["id"] == comp_id), None)
    if comp is None:
        raise RostrumError(codes.NOT_FOUND, "export", f'composition "{comp_id}"', "is not in the document")
    timed = copy.deepcopy(retime.timed(comp, markers.times(doc.folder) if doc.folder else None, comp.get("fps", 30)))
    data = motion_samples.sample(timed, only=layers, where="export motion")
    return {"comp": {"id": comp_id, "props": {"fps": comp.get("fps", 30), "duration": comp.get("duration", 5.0)}}, "samples": data}


def _to_file(where: str, scene: dict, fmt: str, s: dict, target: Path, progress, engine_factory, folder=None, on_stop=None) -> dict:
    """Draw into `target` (a file; for a sequence the base its frames are named from). Facts read back, or RENDER_FAILED."""
    if fmt == "motion":
        data, p = scene["samples"], scene["comp"]["props"]
        try:
            target.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
            back = json.loads(target.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            raise _fail(where, f"the motion samples {target.name}", e) from e
        n = len(next(iter(back["layers"].values()))["x"])
        return {"file": str(target), "frames": round(p["duration"] * p["fps"]), "fps": p["fps"], "alpha": False, "depth": None,
                "checked": {"layers": list(back["layers"]), "samples": n, "rate": back["rate"]}}
    if fmt == "lottie":
        from rostrum2d.io.lottie import write_lottie
        try:
            baked: list[str] = []
            report = write_lottie(scene, target, baked=baked)
            doc = json.loads(target.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            raise _fail(where, f"the Lottie file {target.name}", e) from e
        p = scene["comp"]["props"]
        return {"file": str(target), "frames": round((p["duration"]) * p["fps"]), "fps": p["fps"], "alpha": False, "depth": None,
                "checked": {"layers": len(doc.get("layers", [])), "size": (doc.get("w"), doc.get("h")), "baked": baked}, "report": report}
    if s.get("area"):                                # a picture of an area of the world (export_area.py), not of the frame
        return export_area.pictures(where, scene, s, target, progress, engine_factory)
    from rostrum2d.io.export import export
    try:
        with (engine_factory or _engine)() as eng:
            if on_stop:                              # a job's on_cancel: run_stop ends the engine at once, even mid-frame
                on_stop(eng.kill)
            eng.load(scene)
            facts = export(eng, fmt, target, s["alpha"], s["depth"], s["start"], s["end"], progress, s.get("quality"), s.get("bitrate"), s.get("gif"))
    except Exception as e:  # noqa: BLE001  the engine, the encoder, or the read-back: one loud failure naming what was drawn
        raise _fail(where, f"the {fmt} export {target.name}", e) from e
    return with_sound(where, facts, target, s, folder)


def with_sound(where: str, facts: dict, target: Path, s: dict, folder) -> dict:
    """Settings with a `sound`: the project's mix goes under the picture in `target` (facts["sound"]), or the export
    fails, never a silent file passed off as done. render_video takes this step too."""
    if s.get("sound"):
        from rostrum2d.io.export_sound import attach
        try:
            facts["sound"] = attach(target, folder, s["sound"], s["start"], s["end"])
        except Exception as e:  # noqa: BLE001
            raise _fail(where, f"the sound of {target.name}", e) from e
    return facts


def _engine():
    from rostrum2d.engine import Engine
    return Engine()


def project_renders(folder, item) -> Path | None:
    """The one rule for where an export goes when no path is chosen, for every format: the project's
    renders/<item>/ (a new vNNN version folder each time), else None (no project yet: see default_folder)."""
    return Path(folder) / "renders" / item if folder and item else None


def default_folder(folder, item) -> Path:
    """The folder a no-path export is written into: the one rule the Export sheet shows and `run` writes by. A project's
    renders/<item>/ (the version folder goes inside), else the person's Videos (a scripted run's scratch home)."""
    return project_renders(folder, item) or app_settings.videos_dir()


def _manifest(item, doc_seq, comp_id, fmt, s, facts, version, names, size) -> dict:
    fps, first = facts["fps"], 1001 + round(s["start"] * facts["fps"])
    # Lottie and motion samples are data, not frames: their own kind, so readers of "pictures" never pick them up
    return {"item": item, "version": version, "kind": "data" if fmt in DATA else "pictures", "format": fmt, "made_by": "agent:rostrum-2d",
            "made_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": {"document": item, "history_entry": doc_seq, "comp": comp_id}, "engine": "rostrum-2d",
            "frames": {"first": first, "last": first + facts["frames"] - 1, "fps": f"{fps:g}/1", "start": s["start"], "end": s["end"]},
            "size": list(size), "duration": round(s["end"] - s["start"], 6), "files": names, "alpha": facts["alpha"], "depth": facts["depth"],
            "colour": {"space": "ACEScg", "view": table.HANDOFF_VIEW} if fmt == "exr" else {"space": "Rec.709 (bt709, display-referred)"}, "checks": {"frame_count": "ok"}}


def run(where: str, scene: dict, fmt: str, s: dict, folder=None, item=None, doc_seq=0, out=None, progress=None, engine_factory=None,
        name=None, overwrite=False, on_stop=None) -> dict:
    """Export `scene` as `fmt` with settings `s` (from settings()). Where it goes: `out` (a file; for a sequence a folder), else
    project_renders(folder, item) for every format, else default_folder (Videos, or a scripted run's scratch home).
    Written under a .partial name and renamed when read back right; a failed or cancelled run removes what it wrote. Returns the facts: file, frames, fps, alpha, depth, checked,
    files (what was written), report (Lottie: what it couldn't carry).
    `name`: the file's name without its extension (export_name.stem_of: the project's and the composition's); default item_composition.
    An `out` that already exists is refused unless `overwrite` (a sequence's folder is never replaced).
    `on_stop`: a job's on_cancel, handed the engine's end so a stop needs no next frame."""
    row, comp = info(where, fmt), scene["comp"]
    stem = name or f'{item or "doc"}_{comp["id"]}'
    png = fmt in table.FORMATS and not table.FORMATS[fmt].video     # a sequence: one file per frame, in a folder
    seq_name = lambda base: table.pattern(table.FORMATS[fmt], base)
    if out is None and project_renders(folder, item):              # a project render: renders/<item>/vNNN/
        part = project.begin_render(folder, item)
        name = f"{stem}{row['ext']}"
        try:
            facts = _to_file(where, scene, fmt, s, part / (stem if png else name), progress, engine_factory, folder, on_stop)
            names = sorted(p.name for p in part.iterdir())
            done = project.finish_render(part, _manifest(item, doc_seq, comp["id"], fmt, s, facts, int(part.name[1:].split(".")[0]),
                                                         names, facts["checked"]["size"] if s.get("area") else (comp["props"].get("width"), comp["props"].get("height"))))
        except BaseException:                        # a failed or stopped (cancelled) render leaves no unfinished version behind
            shutil.rmtree(part, ignore_errors=True)
            raise
        facts["files"] = [str(done / n) for n in names]
        facts["file"] = str(done / (Path(seq_name(stem)).name if png else name))
        return facts
    final = Path(out) if out else default_folder(folder, item) / f"{stem}_{time.strftime('%Y%m%d_%H%M%S')}{'' if png else row['ext']}"
    if not png and final.suffix.lower() != row["ext"]:
        raise RostrumError(codes.BAD_ARGUMENT, where, f'path "{final}"', f"must end in {row['ext']} for {fmt}")
    if png and final.exists():
        raise RostrumError(codes.BAD_ARGUMENT, where, f'path "{final}"', "already exists; a sequence is written into a new folder")
    if final.exists() and not overwrite:
        raise RostrumError(codes.BAD_ARGUMENT, where, f'path "{final}"', "already exists; nothing was replaced",
                           hint='Pass "overwrite": true to replace it, or choose another path.')
    final.parent.mkdir(parents=True, exist_ok=True)
    part = final.with_name(final.name + ".partial") if png else final.with_name(final.stem + ".partial" + final.suffix)
    if png:
        shutil.rmtree(part, ignore_errors=True)
    else:
        part.unlink(missing_ok=True)
    try:
        facts = _to_file(where, scene, fmt, s, part / final.name if png else part, progress, engine_factory, folder, on_stop)
        if not png and (not part.is_file() or part.stat().st_size == 0):
            raise _fail(where, f"the {fmt} export {final.name}", RuntimeError(f"no file at {part}"))
    except BaseException:                            # a failed or stopped (cancelled) export leaves no .partial behind
        shutil.rmtree(part, ignore_errors=True) if png else part.unlink(missing_ok=True)
        raise
    if png:
        part.rename(final)
    else:
        part.replace(final)
    facts["files"] = sorted(str(p) for p in final.iterdir()) if png else [str(final)]
    facts["file"] = seq_name(final / final.name) if png else str(final)
    return facts
