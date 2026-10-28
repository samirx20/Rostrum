"""The script call `light_shafts(...)`: beams of light through water, a window or haze, as plain editable layers (guide
frame-parallax-motion-blur, "Light shafts"). One group (`<id>`) of tall shapes (`<id>_0` …), each lit at its top end and
fading to fully clear along its length (a linear fill whose last stop is see-through, so it never darkens what is under
it), added onto the picture (`blend="add"`), soft at its sides (a blur), leaning and spread from a source line.

    sh = light_shafts("rays", x=960, y=-80, count=6, spread=1500, length=1500, lean=12, color="#bff8ee", strength=0.5)
    sh.set(depth=2)                                  # at a depth like any group: parallax, depth of field, fog
    sh.key("opacity", {0: 1, 16: 0})                 # all of them fade; or key one shaft: layer("rays_2")

`strength` is how much light a shaft adds at its brightest (0 = none, 1 = the full colour added): the default reads at
frame size over a dark or mid-tone picture; key the group's opacity to let the light come and go. `sway` turns each
shaft a few degrees back and forth over `duration` seconds and `breathe` lets its light rise and fall, each shaft on its
own phase; 0 keeps them still. Every value is only a starting point: the shafts are ordinary layers."""
from __future__ import annotations

import math
import random as _random


def for_script(build) -> dict:
    L = build.layer

    def light_shafts(id="shafts", x=960.0, y=-80.0, count=5, spread=1400.0, length=1500.0, width=(90.0, 280.0),
                     lean=10.0, color="#fff6dc", strength=0.45, fade=1.0, softness=28.0, blend="add", sway=3.0,
                     breathe=0.3, duration=None, seed=1, **fields):
        """A group of `count` light shafts hanging from the line `spread` px wide centred on (x, y), each `length` px
        long, its width between `width`, leaning `lean` degrees (the light's angle). Returns the group."""
        if count < 1:
            raise ValueError(f"light_shafts: count {count} — give 1 or more shafts")
        if not 0 <= strength <= 1:
            raise ValueError(f"light_shafts: strength {strength} — 0 (no light) … 1 (the full colour added)")
        lo, hi = (width, width) if isinstance(width, (int, float)) else width
        rnd = _random.Random(seed)
        end = float(duration if duration is not None else build.root.get("comps", [{}])[-1].get("duration", 10.0))
        g = L("group", id, x=x, y=y, w=spread, h=length, anchorX=0.5, anchorY=0, **fields)
        with g:
            for i in range(count):
                along = (i + 0.5) / count + rnd.uniform(-0.35, 0.35) / count
                bw = rnd.uniform(lo, hi)
                turn = lean + rnd.uniform(-0.25, 0.25) * max(abs(lean), 4.0)
                peak = strength * rnd.uniform(0.7, 1.0)
                stops = [{"type": "stop", "id": f"{id}_{i}_top", "at": 0.0, "color": color[:7], "opacity": round(peak, 4)},
                         {"type": "stop", "id": f"{id}_{i}_mid", "at": round(0.45 * fade, 3), "color": color[:7], "opacity": round(peak * 0.45, 4)},
                         {"type": "stop", "id": f"{id}_{i}_end", "at": round(min(1.0, fade), 3), "color": color[:7], "opacity": 0.0}]
                s = L("shape", f"{id}_{i}", x=along * spread, y=0, w=bw, h=length, anchorX=0.5, anchorY=0, rotation=-turn,
                      fillType="linear", gradAngle=180.0, blend=blend)
                s.node["stops"] = [{**st, "name": "Gradient stop", "keys": []} for st in stops]   # a fill's stops are a list, not a field
                if softness > 0:
                    s.effect("blur", radius=softness)
                phase = rnd.uniform(0, 1)
                if sway:
                    s.key("rotation", {0: -turn - sway * math.sin(phase * 6.283), end: -turn + sway * math.sin(phase * 6.283)}, ease="easeInOut")
                if breathe:
                    lows = {round(end * k / 4, 3): 1.0 - breathe * (0.5 + 0.5 * math.sin(phase * 6.283 + k * 1.9)) for k in range(5)}
                    s.key("opacity", lows, ease="easeInOut")
        return g

    return {"light_shafts": light_shafts}
