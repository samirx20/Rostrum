"""The viewport's Final look (SPEC §11.1): progressive Cycles in place, with the Render button's own settings (one place:
render_job.cycles_of, the shot's render settings), so the converged viewport is the Render button's picture. Screen state only: never the document.

The engine does one step per `view` request and says how far it has got (ENGINE_CONTRACT.md § 4, `final`); this keeps
the progress line and decides what comes next. The 4 GB card: when it is nearly full the look steps down to half the
pixels, and when it is still short (or Cycles fails) it goes back to Quick, saying why. Nothing here is silent.
"""
from __future__ import annotations


FREE_MB = 300                 # under this much free graphics memory, Final steps down (then leaves)
NEXT_MS = 120                 # how soon the next step is asked for while it refines


class FinalLook:
    def __init__(self):
        self.on, self.scale, self.line, self.fraction = False, 1.0, "", 0.0

    def start(self):
        self.on, self.scale, self.line, self.fraction = True, 1.0, "Final · starting Cycles…", 0.0

    def stop(self):
        self.on, self.scale, self.line, self.fraction = False, 1.0, "", 0.0

    def fields(self, cycles: dict) -> dict:
        """What a Final `view` request adds over Quick: the render's renderer and settings, its exposure and view."""
        return {"renderer": "cycles", "samples": cycles["samples"], "denoise": cycles["denoise"],
                "exposure": 0.0, "view": "", "selected": []}

    def size(self, size: tuple[int, int]) -> tuple[int, int]:
        return max(16, round(size[0] * self.scale)), max(16, round(size[1] * self.scale))

    def take(self, reply: dict) -> str:
        """One engine reply: updates the line; returns "next" (ask again), "done", "smaller" (stepped down: ask again)
        or "leave" (back to Quick; the line says why)."""
        f, vram = reply.get("final") or {}, reply.get("vram") or {}
        status = str(f.get("status", ""))
        if "error" in status.lower() or "out of memory" in status.lower():
            self.line = f"Final stopped: Cycles said: {status}. Back to Quick."
            return "leave"
        used, total = vram.get("gpuUsedMb", -1), vram.get("gpuTotalMb", -1)
        if not f.get("converged") and used >= 0 and total > 0 and total - used < FREE_MB:
            if self.scale == 1.0:
                self.scale, self.fraction = 0.5, 0.0
                self.line = f"Final at half size: the graphics card is nearly full ({total - used:.0f} MB free)"
                return "smaller"
            self.line = (f"Final stopped: the graphics card has only {total - used:.0f} MB of {total:.0f} MB free. "
                         "Back to Quick.")
            return "leave"
        half = " · half size" if self.scale < 1 else ""
        secs = f.get("seconds", 0.0)
        if f.get("converged"):
            self.fraction, self.line = 1.0, f"Final · done · {f.get('of')} samples · {secs:.0f} s{half}"
            return "done"
        if not status.startswith("Sample"):          # just started over: Cycles' count is still the last run's
            self.fraction, self.line = 0.0, f"Final · {(status or 'starting').lower()}…{half}"
            return "next"
        self.fraction = float(f.get("fraction", 0.0))
        self.line = f"Final · {f.get('samples', 0)} of {f.get('of')} samples · {secs:.0f} s{half}"
        return "next"
