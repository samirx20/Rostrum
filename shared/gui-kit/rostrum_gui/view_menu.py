"""The view control's menu ("Fit · 50 % ▾", INTERACTION.md 1.1 and 1.12; qml ViewControl.qml): Fit, 50 %, 100 %, 200 %,
Zoom in, Zoom out, each with its key from the key map. The rows are data: `job:<name>` runs one of CanvasView's view
jobs, `zoom:<percent>` sets the zoom. QML only shows them and sends the chosen value to `CanvasView.pick(value)`.
Rule of individuality: a step already on (100 % while at 100 %) is absent, and so is Fit while the view is fitted.
"""
from __future__ import annotations

from .keymap import SHARED

KEYS = {r["job"]: r["keys"][0] for r in SHARED if r["keys"]}
PERCENTS = (50, 100, 200)


def entries(zoom: float, fitted: bool) -> list[dict]:
    out = [] if fitted else [{"value": "job:fit_all", "label": "Fit", "keys": KEYS["fit_all"], "group": "fit"}]
    for pct in PERCENTS:
        if round(zoom * 100) != pct or fitted:
            out.append({"value": f"zoom:{pct}", "label": f"{pct} %", "keys": KEYS["actual_size"] if pct == 100 else "",
                        "group": "steps"})
    return out + [{"value": "job:zoom_in", "label": "Zoom in", "keys": KEYS["zoom_in"], "group": "step"},
                  {"value": "job:zoom_out", "label": "Zoom out", "keys": KEYS["zoom_out"], "group": "step"}]
