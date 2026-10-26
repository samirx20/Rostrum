"""Ctrl+K's own rows for Rostrum3D: the actions (the same list as the settings panel, right-click and the keys: the hub's
`commands`), then a row for every key-map job that would do something visible NOW (the same "valid when" idea as an
action's, for the jobs a route or the window runs). One table, WHEN; a job not in it is always offered. So Render, the
pages, Paint and Look are rows only when they'd change something (the page shown is no row, Paint needs a mesh), and
Edit mesh is the action's row (only with one shape or combine picked)."""
from __future__ import annotations

from rostrum_gui import job_rows
from rostrum3d import fields as F

from .actions3d import LIST
from .keys3d import HAVE_ROWS, KEYS3D, ROUTES, SHELL, WINDOW


def _vp(b):
    return getattr(b, "viewport", None)


def _mesh_tools(b) -> bool:
    v = _vp(b)
    return v is not None and v.mesh_edit.on and not v.mesh_edit.needsEdit


def _movable(b) -> bool:
    v = _vp(b)
    return bool(b._movable()) and (v is None or not (v.mesh_edit.on or v.paint.on))


def _gizmo(b, show) -> bool:
    v = _vp(b)
    return v is not None and v.gizmo.show != show and v.gizmo._item() is not None


WHEN = {
    "page_build": lambda b: b.page != "build", "page_animate": lambda b: b.page != "animate",
    "page_render": lambda b: b.page != "render",
    "render": lambda b: not b.exporter.open,
    "paint_tool": lambda b: _vp(b) is not None and (_vp(b).paint.on or _vp(b).paint.can),
    "look": lambda b: _vp(b) is not None,
    "shot_view": lambda b: _vp(b) is not None and _vp(b).hasShot and (bool(b.selection) or _vp(b).mode == "shot"),   # else its action's row
    "go_in": lambda b: _vp(b) is not None and (_vp(b).mesh_edit.knifing or _vp(b).bone_tool.on) or (    # a shape: Edit mesh's own row
        bool(b.selected) and b.doc.has(b.selected) and b.doc.item(b.selected)["type"] not in F.SOLIDS
        and bool(b.doc.item(b.selected).get("children"))),
    "move_tool": lambda b: _vp(b) is not None and (_vp(b).paint.on or _vp(b).gizmo.show != "all" or b.add.armed != ""),
    "gizmo_move": lambda b: _gizmo(b, "move"), "gizmo_turn": lambda b: _gizmo(b, "turn"),
    "gizmo_scale": lambda b: _gizmo(b, "scale"),
    "mesh_points": lambda b: _mesh_tools(b) and _vp(b).mesh_edit.kind != "points",
    "mesh_edges": lambda b: _mesh_tools(b) and _vp(b).mesh_edit.kind != "edges",
    "mesh_faces": lambda b: _mesh_tools(b) and _vp(b).mesh_edit.kind != "faces",
    "mesh_xray": _mesh_tools, "mesh_knife": _mesh_tools,
    "go_out": lambda b: (_vp(b) is not None and _vp(b).mesh_edit.on)
    or (bool(b.selected) and b.doc.has(b.selected) and b.doc.parent_of(b.selected)[0] not in ("", b.doc.data["id"])),
    "key_here": lambda b: _vp(b) is not None and not _vp(b).mesh_edit.on and _vp(b).gizmo._item() is not None,
    **{j: (lambda b: b._keys.count > 0) for j in ("smooth", "ease_in", "ease_out", "jump")},
    **{f"nudge_{d}{s}": _movable for d in ("left", "right", "up", "down") for s in ("", "_big", "_fine")},
    "next_item": lambda b: bool(b._scene_order()), "prev_item": lambda b: bool(b._scene_order()),
    "select_all": lambda b: bool(b._scene_order()),
    "zoom_in": lambda b: _vp(b) is not None, "zoom_out": lambda b: _vp(b) is not None,
    "onion": lambda b: b.page == "animate", "poses_panel": lambda b: b.page == "animate",
    "shapes_menu": lambda b: b.page == "build", "type_menu": lambda b: b.page == "build",
}


def rows(bridge, jobs: list[dict]) -> list[dict]:
    """`jobs`: job_rows.rows' list ("job:<name>" keys): only those that would do something now."""
    return [r for r in jobs if not (r["key"].startswith("job:") and r["key"][4:] in WHEN and not WHEN[r["key"][4:]](bridge))]


def commands(bridge) -> list[dict]:
    """The actions as Ctrl+K rows (each runs through the hub: one guard), then the key-map jobs' rows."""
    hub = bridge._hub
    mine = [{**{k: c[k] for k in ("key", "label", "hint", "keys", "words", "weight") if k in c},
             "do": (lambda k=c["key"]: hub.choose(k)), "own": True} for c in hub.commands("")]
    taken = ({LIST.job_of(a) for a in LIST.actions} - set(ROUTES)) | set(HAVE_ROWS)   # a route's job stays a row (WHEN: no twin)
    jobs = job_rows.rows(KEYS3D, set(ROUTES) | set(WINDOW) | set(SHELL), taken,
                         state={"selected": bool(bridge.selection), "problems": False})
    jobs = [{**r, "do": (lambda j=r["key"][4:]: hub.run_job(j))} for r in rows(bridge, jobs)]
    return mine + jobs
