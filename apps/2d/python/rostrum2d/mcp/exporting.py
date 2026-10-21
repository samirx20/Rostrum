"""The one export path for every format (mp4, prores4444, webm, gif, png and exr sequences, lottie): the `render_export` tool and the
screen's Export button both run `run()`. The formats and what each takes come from `io/formats.py` (FORMATS) plus Lottie
here; nothing per format is written anywhere else. Nothing is reported as done unless the file read back right."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from rostrum_core import project
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp.files import RENDER_DIR

from rostrum2d.io import formats as table

from .render import _fail

LABELS = {"mp4": "MP4 (H.264)", "prores4444": "ProRes 4444", "webm": "WebM (VP9)", "gif": "GIF", "png": "PNG sequence", "exr": "EXR sequence (for the Editor)", "lottie": "Lottie (JSON)"}


def formats() -> list[dict]:
    """Every format and what it takes: alpha (can carry it), depths (bits; first = default), range (start / end apply),
    sequence (one file per frame, written into a folder)."""
    rows = [{"name": n, "label": LABELS.get(n, n), "ext": f.ext, "alpha": f.alpha, "depths": list(f.depths), "range": True,
             "sequence": not f.video}
            for n, f in table.FORMATS.items()]
    return rows + [{"name": "lottie", "label": LABELS["lottie"], "ext": ".json", "alpha": False, "depths": [], "range": False, "sequence": False}]


def info(where: str, fmt: str) -> dict:
    row = next((r for r in formats() if r["name"] == fmt), None)
    if row is None:
        raise RostrumError(codes.BAD_ARGUMENT, where, f'format "{fmt}"', "is not an export format", [r["name"] for r in formats()])
    return row


def settings(where: str, fmt: str, duration: float, alpha=None, depth=None, start=None, end=None) -> dict:
    """The settings that apply to `fmt`, defaults filled; one that doesn't apply (alpha on mp4, depth on gif, any on Lottie) is refused."""
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
    return {"alpha": row["alpha"] if alpha is None else bool(alpha), "depth": depth or (row["depths"][0] if row["depths"] else None),
            "start": start, "end": end}


def _to_file(where: str, scene: dict, fmt: str, s: dict, target: Path, progress, engine_factory) -> dict:
    """Draw into `target` (a file; for a sequence the base its frames are named from). Facts read back, or RENDER_FAILED."""
    if fmt == "lottie":
        from rostrum2d.io.lottie import write_lottie
        try:
            report = write_lottie(scene, target)
            doc = json.loads(target.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            raise _fail(where, f"the Lottie file {target.name}", e) from e
        p = scene["comp"]["props"]
        return {"file": str(target), "frames": round((p["duration"]) * p["fps"]), "fps": p["fps"], "alpha": False, "depth": None,
                "checked": {"layers": len(doc.get("layers", [])), "size": (doc.get("w"), doc.get("h"))}, "report": report}
    from rostrum2d.io.export import export
    try:
        with (engine_factory or _engine)() as eng:
            eng.load(scene)
            return export(eng, fmt, target, s["alpha"], s["depth"], s["start"], s["end"], progress)
    except Exception as e:  # noqa: BLE001  the engine, the encoder, or the read-back: one loud failure naming what was drawn
        raise _fail(where, f"the {fmt} export {target.name}", e) from e


def _engine():
    from rostrum2d.engine import Engine
    return Engine()


def _manifest(item, doc_seq, comp_id, fmt, s, facts, version, names, size) -> dict:
    fps, first = facts["fps"], 1001 + round(s["start"] * facts["fps"])
    return {"item": item, "version": version, "kind": "pictures", "format": fmt, "made_by": "agent:rostrum-2d",
            "made_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": {"document": item, "history_entry": doc_seq, "comp": comp_id}, "engine": "rostrum-2d",
            "frames": {"first": first, "last": first + facts["frames"] - 1, "fps": f"{fps:g}/1", "start": s["start"], "end": s["end"]},
            "size": list(size), "duration": round(s["end"] - s["start"], 6), "files": names, "alpha": facts["alpha"], "depth": facts["depth"],
            "colour": {"space": "ACEScg", "view": table.HANDOFF_VIEW} if fmt == "exr" else {"space": "Rec.709 (bt709, display-referred)"}, "checks": {"frame_count": "ok"}}


def run(where: str, scene: dict, fmt: str, s: dict, folder=None, item=None, doc_seq=0, out=None, progress=None, engine_factory=None) -> dict:
    """Export `scene` as `fmt` with settings `s` (from settings()). Where it goes: `out` (a file; for a sequence a folder), else the
    project's renders folder (folder + item; not for Lottie, which is not a picture hand-off), else the render cache.
    Written under a .partial name and renamed when read back right; a failed or cancelled run removes what it wrote. Returns the facts: file, frames, fps, alpha, depth, checked,
    files (what was written), report (Lottie: what it couldn't carry)."""
    row, comp = info(where, fmt), scene["comp"]
    stem = f'{item or "doc"}_{comp["id"]}'
    png = fmt in table.FORMATS and not table.FORMATS[fmt].video     # a sequence: one file per frame, in a folder
    seq_name = lambda base: table.pattern(table.FORMATS[fmt], base)
    if out is None and folder and item and fmt != "lottie":       # a project render: renders/<item>/vNNN/
        part = project.begin_render(folder, item)
        name = f"{stem}{row['ext']}"
        try:
            facts = _to_file(where, scene, fmt, s, part / (stem if png else name), progress, engine_factory)
            names = sorted(p.name for p in part.iterdir())
            done = project.finish_render(part, _manifest(item, doc_seq, comp["id"], fmt, s, facts, int(part.name[1:].split(".")[0]),
                                                         names, (comp["props"]["width"], comp["props"]["height"])))
        except BaseException:                        # a failed or stopped (cancelled) render leaves no unfinished version behind
            shutil.rmtree(part, ignore_errors=True)
            raise
        facts["files"] = [str(done / n) for n in names]
        facts["file"] = str(done / (Path(seq_name(stem)).name if png else name))
        return facts
    final = Path(out) if out else RENDER_DIR / f"{stem}_{time.strftime('%Y%m%d_%H%M%S')}{'' if png else row['ext']}"
    if not png and final.suffix.lower() != row["ext"]:
        raise RostrumError(codes.BAD_ARGUMENT, where, f'path "{final}"', f"must end in {row['ext']} for {fmt}")
    if png and final.exists():
        raise RostrumError(codes.BAD_ARGUMENT, where, f'path "{final}"', "already exists; a sequence is written into a new folder")
    final.parent.mkdir(parents=True, exist_ok=True)
    part = final.with_name(final.name + ".partial") if png else final.with_name(final.stem + ".partial" + final.suffix)
    if png:
        shutil.rmtree(part, ignore_errors=True)
    else:
        part.unlink(missing_ok=True)
    try:
        facts = _to_file(where, scene, fmt, s, part / final.name if png else part, progress, engine_factory)
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
