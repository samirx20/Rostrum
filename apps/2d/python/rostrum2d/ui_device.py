"""device(): a phone, laptop or browser window drawn from plain shapes, sized and placed by ui_layout.device_box
(its share of the picture's height, centred or against a side of the title-safe area), its screen a clipped group
(guide ui-and-product-animation, "Building blocks" and "Framing a device")."""
from __future__ import annotations

from . import ui_layout as U


def maker(build, box, words):
    L = build.layer

    def device(id, kind="phone", x=None, y=None, w=None, h=None, fit=None, anchor="center", margin=None,
               body="#0b0d12", screen=U.PAPER, radius=None, url="app.example.com"):
        """A device drawn from plain shapes, centred on (x, y). Left out, its size fills `fit` of the parent's height
        (phone 0.82) keeping its shape, placed by `anchor` (center, left, right) inside `margin`. Returns its screen: a
        clipped group (rounded by a mask) whose px start at the screen's top-left; make the screen's layers inside `with` it."""
        if kind not in U.SHAPES:
            raise ValueError(f'device {id}: kind "{kind}" is not one of {", ".join(U.SHAPES)}')
        x, y, w, h = U.device_box(kind, build, x, y, w, h, fit, anchor, margin)
        outer = L("group", id, x=x, y=y, w=w, h=h)
        with outer:
            if kind == "phone":
                bez = round(w * 0.033)
                r = radius if radius is not None else w * 0.15
                L("shape", f"{id}_body", x=w / 2, y=h / 2, w=w, h=h, radius=r, fill=body)
                sx, sy, sw, sh, sr = bez, bez, w - 2 * bez, h - 2 * bez, max(r - bez, 0)
            elif kind == "laptop":
                lid = h * 0.93
                r = radius if radius is not None else 26
                L("shape", f"{id}_body", x=w / 2, y=lid / 2, w=w * 0.9, h=lid, radius=r, fill=body)
                L("shape", f"{id}_base", x=w / 2, y=lid + (h - lid) / 2, w=w, h=h - lid, radius=(h - lid) / 2, fill=body, fillOpacity=0.85)
                L("shape", f"{id}_lip", x=w / 2, y=lid + (h - lid) * 0.3, w=w * 0.14, h=(h - lid) * 0.35, radius=(h - lid) * 0.2, fill="#000000", fillOpacity=0.35)
                bez = w * 0.02
                sx, sy, sw, sh, sr = w * 0.05 + bez, bez, w * 0.9 - 2 * bez, lid - 2.4 * bez, 6
            else:
                bar = h * 0.07
                r = radius if radius is not None else 16
                L("shape", f"{id}_body", x=w / 2, y=h / 2, w=w, h=h, radius=r, fill=body)
                for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
                    L("shape", f"{id}_dot{i}", shape="ellipse", x=bar * (0.46 + i * 0.43), y=bar / 2, w=bar * 0.23, h=bar * 0.23, fill=c)
                L("shape", f"{id}_address", x=w / 2, y=bar / 2, w=w * 0.42, h=bar * 0.57, radius=bar * 0.28, fill="#ffffff", fillOpacity=0.12)
                words(f"{id}_url", url, w / 2, bar / 2, bar * 0.29, "#ffffff", align="center", weight=450, opacity=0.7)
                sx, sy, sw, sh, sr = 0, bar, w, h - bar, 0
            scr = box(f"{id}_screen", sx, sy, sw, sh, clip=True)
            if sr:
                scr.mask(f"{id}_screen_round", x=0, y=0, w=sw, h=sh, radius=sr)
            with scr:
                L("shape", f"{id}_screen_bg", x=sw / 2, y=sh / 2, w=sw, h=sh, fill=screen)
            if kind == "phone":
                L("shape", f"{id}_island", x=w / 2, y=bez + sw * 0.05, w=sw * 0.3, h=sw * 0.085, radius=sw * 0.05, fill="#000000")
            elif kind == "laptop":
                L("shape", f"{id}_camera", shape="ellipse", x=w / 2, y=bez / 2, w=6, h=6, fill="#2a2f3a")
        return scr

    return device
