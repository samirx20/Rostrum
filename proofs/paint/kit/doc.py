"""The P-PAINT painting document: layers, masks, operations, batches, undo / redo, replay.

The JSON op list is the truth. Every op is a plain dict (JSON round-tripped before it runs);
the live call and the replay both run it through `_State.apply`, so a saved document reopens
to the very same float32 pixels. Layer pixels (`layer_pixels`) are **premultiplied** RGBA
float32, sRGB-encoded 0..1; `composite()` is HxWx3 sRGB. Paint ops (stroke, fill, gradient,
fill_region) each get a stroke id (1, 2, ...); an int32 map keeps the last id per pixel.

Additions to INTERFACE.md (no renames): `layers()` -> [{name, mode, opacity, visible, locked}]
bottom to top; `masks()` -> names; `mask_array(name)` (accepts "!name"); `mask_from_layer(layer,
name=None)` snapshots the layer's alpha at that point of the history; `snapshot(k)` = composite
after batch k (0-based, as in `history()`), `snapshot(-1)` = the blank start; `fill` / `gradient`
take `opacity`, `mode`; `gradient(..., shape="linear"|"radial")`. Setup ops (add_layer, set_layer,
masks) outside a `batch` join the next batch (or one "setup" batch at save / undo / history); paint
ops outside a `batch` are each their own batch (author `Doc.author`). Nested batches join the outer
one. An error inside a batch rolls the whole batch back and re-raises. The redo list is saved in the
JSON ("redo"); a pixel cache (`cache.py`) beside the file spares the replay on open.
"""
import contextlib, json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import brush as B
import cache

FORMAT = "rostrum-paint/0"
LAYER_MODES = ("normal", "multiply", "screen", "add")
SETUP_OPS = ("add_layer", "set_layer", "mask")
LAYER_KEYS = ("mode", "opacity", "visible", "locked")
CHECKPOINT_BYTES = 800 << 20  # in-memory states kept for fast undo / snapshot


class MaskName(str):
    def inverted(self):
        return MaskName(self[1:] if self.startswith("!") else "!" + self)


def _poly(h, w, pts, feather):
    ss = 4  # supersampled, so polygon edges are antialiased
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).polygon([(x * ss, y * ss) for x, y, *_ in pts], fill=255)
    im = im.reduce(ss)
    if feather:
        im = im.filter(ImageFilter.GaussianBlur(feather))
    return np.asarray(im, np.float32) / 255


class _State:
    def __init__(self, head):
        self.w, self.h = w, h = head["w"], head["h"]
        bg = np.ones((h, w, 4), np.float32)
        bg[..., :3] = np.asarray(head["background"], np.float32)
        self.layers = [dict(name="background", mode="normal", opacity=1.0, visible=True, locked=False, px=bg)]
        self.masks, self.covs, self.info, self.next_id = {}, {}, {}, 1
        self.last = np.zeros((h, w), np.int32)  # 0 = no stroke
        self.base, self.dirty = None, set()  # kept state this one started from; layers written since
        self.paper = B.Paper(h, w, head["paper"]["seed"], head["paper"]["size"])

    def copy(self):  # a working copy; remembers which kept state it started from
        s = object.__new__(_State)
        s.__dict__.update(self.__dict__, masks=dict(self.masks), covs=dict(self.covs), info=dict(self.info),
                          last=self.last.copy(), layers=[{**l, "px": l["px"].copy()} for l in self.layers],
                          base=self, dirty=set())
        return s

    def snap(self):  # a kept (never changed) state: layers untouched since `base` share base's pixels
        old = {l["name"]: l["px"] for l in self.base.layers} if self.base is not None else {}
        s = object.__new__(_State)
        s.__dict__.update(self.__dict__, masks=dict(self.masks), covs=dict(self.covs), info=dict(self.info),
                          last=self.last.copy(), base=None, dirty=set(),
                          layers=[{**l, "px": old[l["name"]] if l["name"] in old and l["name"] not in self.dirty
                                   else l["px"].copy()} for l in self.layers])
        return s

    def arrays(self):
        return [l["px"] for l in self.layers] + [self.last]

    def layer(self, name, write=False):
        for l in self.layers:
            if l["name"] == name:
                if write and l["locked"]:
                    raise PermissionError(f"layer {name!r} is locked; unlock it with set_layer({name!r}, locked=False)")
                return l
        raise KeyError(f"no layer {name!r}; layers are {[l['name'] for l in self.layers]}")

    def mask(self, name):
        if name is None:
            return None
        base = name[1:] if name.startswith("!") else name
        if base not in self.masks:
            raise KeyError(f"no mask {base!r}; masks are {sorted(self.masks)}")
        return 1 - self.masks[base] if name.startswith("!") else self.masks[base]

    def composite(self, below=None):
        out = np.zeros((self.h, self.w, 3), np.float32)
        for l in self.layers:
            if l["name"] == below:
                break
            if not l["visible"]:
                continue
            c, a = l["px"][..., :3] * l["opacity"], l["px"][..., 3:] * l["opacity"]
            if l["mode"] == "normal":
                out = c + out * (1 - a)
            elif l["mode"] == "multiply":
                out = out * (1 - a + c)
            elif l["mode"] == "add":
                out = np.minimum(out + c, 1)
            else:
                out = out + c - out * c
        return out

    def _mark(self, cov, bbox, batch, idx):
        sid, self.next_id = self.next_id, self.next_id + 1
        x0, y0, x1, y1 = bbox
        self.last[y0:y1, x0:x1][cov > 1 / 255] = sid
        self.covs[sid] = (bbox, (np.clip(cov, 0, 1) * 255 + 0.5).astype(np.uint8))
        self.info[sid] = (batch, idx)
        return sid

    def apply(self, op, batch, idx):
        k = op["op"]
        if k == "add_layer":
            if any(l["name"] == op["name"] for l in self.layers):
                raise ValueError(f"layer {op['name']!r} already exists")
            if op["mode"] not in LAYER_MODES:
                raise ValueError(f"layer mode must be one of {LAYER_MODES}")
            at = len(self.layers) if op["below"] is None else self.layers.index(self.layer(op["below"]))
            self.dirty.add(op["name"])
            self.layers.insert(at, dict(name=op["name"], mode=op["mode"], opacity=float(op["opacity"]), visible=True,
                                        locked=False, px=np.zeros((self.h, self.w, 4), np.float32)))
            return None
        if k == "set_layer":
            l, ch = self.layer(op["name"]), op["changes"]
            if set(ch) - set(LAYER_KEYS) or ch.get("mode", "normal") not in LAYER_MODES:
                raise ValueError(f"set_layer takes {LAYER_KEYS}; modes {LAYER_MODES}; got {ch}")
            l.update(ch)
            return None
        if k == "mask":
            a = _poly(self.h, self.w, op["points"], op["feather"]) if op["kind"] == "polygon" \
                else self.layer(op["layer"])["px"][..., 3].copy()
            if a.max() < 1e-3:
                raise ValueError(f"mask {op['name']!r} is empty (nothing inside it on the canvas)")
            self.masks[op["name"]] = a
            return None
        l, m = self.layer(op["layer"], write=True), self.mask(op.get("mask"))
        self.dirty.add(l["name"])
        under = self.composite(below=l["name"]) if op.get("params", {}).get("sample_all") else None
        if k == "stroke":
            cv = B.stamp_stroke(l["px"], op["points"], op["color"], op["size"], op["brush"], mask=m, under=under,
                                paper=self.paper, **op["params"])
            cov, bbox = (cv.a, cv.bbox) if cv else (np.zeros((0, 0), np.float32), (0, 0, 0, 0))
        elif k == "fill_region":
            B.check(op["brush"], op["params"])
            full = np.zeros((self.h, self.w), np.float32)
            for pts, sd in B.hatch_paths(m, op["size"], **op["hatch"]):
                cv = B.stamp_stroke(l["px"], pts, op["color"], op["size"], op["brush"], mask=m, under=under,
                                    paper=self.paper, **{**op["params"], "seed": sd})
                if cv:
                    x0, y0, x1, y1 = cv.bbox
                    np.maximum(full[y0:y1, x0:x1], cv.a, out=full[y0:y1, x0:x1])
            cov, bbox = full, (0, 0, self.w, self.h)
        elif k in ("fill", "gradient"):
            cov = np.full((self.h, self.w), float(op["opacity"]), np.float32) * (1 if m is None else m)
            col = np.asarray(op["color"] if k == "fill" else op["c0"], np.float32)
            if k == "gradient":
                (x0, y0), (x1, y1) = op["p0"], op["p1"]
                yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
                d2 = max((x1 - x0) ** 2 + (y1 - y0) ** 2, 1e-6)
                t = (np.sqrt(((xx - x0) ** 2 + (yy - y0) ** 2) / d2) if op["shape"] == "radial"
                     else ((xx - x0) * (x1 - x0) + (yy - y0) * (y1 - y0)) / d2)
                col = col + (np.asarray(op["c1"], np.float32) - col) * np.clip(t, 0, 1)[..., None]
                if op.get("v", 1) >= 2:  # v2 paints only where it is: alpha ramp, nothing outside the circle
                    a0, a1 = op["alpha0"], op["alpha1"]
                    cov = cov * (a0 + (a1 - a0) * np.clip(t, 0, 1))
                    if op["shape"] == "radial":  # antialiased rim, one pixel wide
                        cov = cov * np.clip((1 - t) * np.float32(np.sqrt(d2)) + 0.5, 0, 1)
                    cov = cov.astype(np.float32)
            B.apply_paint(l["px"], cov, col, op["mode"])
            bbox = (0, 0, self.w, self.h)
        else:
            raise ValueError(f"unknown op {k!r}")
        return self._mark(cov, bbox, batch, idx)


class Doc:
    author = "agent"

    def __init__(self, head):
        self.head, self.batches, self._redo, self._open, self._loose = head, [], [], None, None
        self.s = _State(head)
        self._ck = {0: self.s.snap()}
        self.s.base = self._ck[0]

    @classmethod
    def new(cls, w, h, background=(1.0, 1.0, 1.0), paper_seed=0, paper_size=3.0):
        return cls(dict(format=FORMAT, w=int(w), h=int(h), background=[float(c) for c in background],
                        paper=dict(seed=int(paper_seed), size=float(paper_size))))

    @classmethod
    def open(cls, path, use_cache=True):
        """With a matching pixel cache this is a load, not a replay. Otherwise it replays every op (saying why
        on stderr) and writes a fresh cache, so the next open is fast."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("format") != FORMAT:
            raise ValueError(f"{path}: not a {FORMAT} document")
        d = cls({k: v for k, v in data.items() if k not in ("batches", "redo")})
        d._redo = data.get("redo", [])
        if use_cache:
            try:
                got = cache.load(path, cache.key(d.head, data["batches"]), d._ck[0])
                why = "pixel cache is out of date (the document or the kit changed)" if os.path.exists(
                    cache.path_for(path)) else "no pixel cache yet"
            except Exception as e:  # a broken cache is only slow, never wrong
                got, why = None, f"pixel cache unreadable ({type(e).__name__}: {e})"
            if got:
                d.batches = list(data["batches"])
                d._ck.update(got)
                d.s = got[len(d.batches)].copy()
                return d
            print(f"note: {why}; replaying {len(data['batches'])} batches", file=sys.stderr)
        for b in data["batches"]:
            d._commit(b)
        if use_cache:
            d._write_cache(path)
        return d

    def save(self, path):
        self._flush()
        with open(path, "w", encoding="utf-8") as f:
            json.dump({**self.head, "batches": self.batches, "redo": self._redo}, f)
        self._write_cache(path)

    def _write_cache(self, path):
        n = len(self.batches)
        older = sorted((k for k in self._ck if 0 < k < n), reverse=True)[:cache.UNDO_KEEP]
        top = self._ck.get(n, self.s)  # the kept state shares arrays with the older ones: cheap to write
        cache.save(path, cache.key(self.head, self.batches), {n: top, **{k: self._ck[k] for k in older}})

    # --- batches, undo, redo -------------------------------------------------------------
    @contextlib.contextmanager
    def batch(self, label, author=None):
        if self._open is not None:  # nested: joins the outer batch
            yield self
            return
        loose, self._loose = self._loose, None  # setup ops made outside a batch join this one
        self._open = dict(label=str(label), author=str(author or self.author), ops=list(loose["ops"]) if loose else [])
        try:
            yield self
        except BaseException:
            self._open, self._loose = None, loose
            self.s = self._state_at(len(self.batches))
            for i, op in enumerate(loose["ops"] if loose else []):  # the setup stays, waiting for a batch
                self.s.apply(op, len(self.batches), i)
            raise
        b, self._open = self._open, None
        if b["ops"]:
            self.batches.append(b)
            self._redo.clear()
            self._checkpoint()

    def _commit(self, b):  # replay or redo: run a whole recorded batch, then keep it
        for i, op in enumerate(b["ops"]):
            self.s.apply(op, len(self.batches), i)
        self.batches.append(b)
        self._checkpoint()

    def _do(self, op):
        if self._open is None and op["op"] not in SETUP_OPS:
            with self.batch(op["op"]):
                return self._do(op)
        into = self._open if self._open is not None else self._loose
        if into is None:
            into = self._loose = dict(label="setup", author=str(self.author), ops=[])
        op = json.loads(json.dumps(op))
        sid = self.s.apply(op, len(self.batches), len(into["ops"]))
        into["ops"].append(op)
        return sid

    def _flush(self):  # setup ops still waiting for a batch become one "setup" batch
        if self._loose is not None and self._open is None:
            self.batches.append(self._loose)
            self._loose = None
            self._redo.clear()
            self._checkpoint()

    def _checkpoint(self):
        n = len(self.batches)
        for k in [k for k in self._ck if k >= n]:
            del self._ck[k]
        self._ck[n] = self.s.snap()
        self.s.base, self.s.dirty = self._ck[n], set()
        while len(self._ck) > 2 and self._kept_bytes() > CHECKPOINT_BYTES:
            del self._ck[min(k for k in self._ck if k)]

    def _kept_bytes(self):  # kept states share unchanged layers; count each array once
        return sum({id(a): a.nbytes for s in self._ck.values() for a in s.arrays()}.values())

    def _state_at(self, n):
        k = max(k for k in self._ck if k <= n)
        s = self._ck[k].copy()
        for bi in range(k, n):
            for i, op in enumerate(self.batches[bi]["ops"]):
                s.apply(op, bi, i)
        return s

    def undo(self):
        self._flush()
        if not self.batches:
            raise IndexError("nothing to undo")
        self._redo.append(self.batches.pop())
        self.s = self._state_at(len(self.batches))

    def redo(self):
        self._flush()
        if not self._redo:
            raise IndexError("nothing to redo")
        self._commit(self._redo.pop())

    def history(self):
        self._flush()
        ids = {}
        for sid, (b, _) in self.s.info.items():
            ids.setdefault(b, []).append(sid)
        return [dict(batch=i, label=b["label"], author=b["author"], n_ops=len(b["ops"]), stroke_ids=ids.get(i, []))
                for i, b in enumerate(self.batches)]

    # --- ops -----------------------------------------------------------------------------
    def add_layer(self, name, below=None, mode="normal", opacity=1.0):
        self._do(dict(op="add_layer", name=name, below=below, mode=mode, opacity=opacity))

    def set_layer(self, name, **changes):
        self._do(dict(op="set_layer", name=name, changes=changes))

    def mask_polygon(self, name, points, feather=0.0):
        self._do(dict(op="mask", name=name, kind="polygon", points=[[float(x), float(y)] for x, y, *_ in points],
                      feather=float(feather)))
        return MaskName(name)

    def mask_from_layer(self, layer, name=None):
        self._do(dict(op="mask", name=name or layer, kind="layer", layer=layer))
        return MaskName(name or layer)

    def stroke(self, layer, points, color, size, brush="round", mask=None, **params):
        B.check(brush, params)
        pts = [[float(v) for v in q[:3]] for q in points]
        return self._do(dict(op="stroke", layer=layer, points=pts, color=[float(c) for c in color], size=float(size),
                             brush=brush, mask=mask, params=params))

    def fill(self, layer, color, mask=None, opacity=1.0, mode="normal"):
        return self._do(dict(op="fill", layer=layer, color=list(map(float, color)), mask=mask, opacity=opacity, mode=mode))

    def gradient(self, layer, p0, p1, c0, c1, mask=None, opacity=1.0, mode="normal", shape="linear",
                 alpha0=None, alpha1=None):
        """c0 / c1: RGB or RGBA; alpha0 / alpha1 override their alpha (default 1). Paints over the layer by that
        alpha (fade alpha1 to 0 for a glow); a radial gradient paints nothing outside its circle."""
        if shape not in ("linear", "radial"):
            raise ValueError("gradient shape must be 'linear' or 'radial'")
        if mode not in B.MODES:
            raise ValueError(f"mode must be one of {B.MODES}, got {mode!r}")
        a0 = float(alpha0 if alpha0 is not None else (c0[3] if len(c0) > 3 else 1.0))
        a1 = float(alpha1 if alpha1 is not None else (c1[3] if len(c1) > 3 else 1.0))
        return self._do(dict(op="gradient", v=2, layer=layer, p0=list(p0), p1=list(p1), c0=list(c0[:3]),
                             c1=list(c1[:3]), alpha0=a0, alpha1=a1, mask=mask, opacity=opacity, mode=mode, shape=shape))

    def fill_region(self, layer, mask, color, size, angle=0.0, gap=0.7, length=4.0, bend=0.15,
                    pressure=(0.5, 1.0, 0.3), seed=0, brush="flat", **params):
        if mask is None:
            raise ValueError("fill_region needs a mask")
        return self._do(dict(op="fill_region", layer=layer, mask=mask, color=list(map(float, color)), size=float(size),
                             brush=brush, params=params, hatch=dict(angle=angle, gap=gap, length=length, bend=bend,
                                                                    pressure=list(pressure), seed=seed)))

    # --- reading -------------------------------------------------------------------------
    def layers(self):
        return [{k: l[k] for k in ("name",) + LAYER_KEYS} for l in self.s.layers]

    def masks(self):
        return sorted(self.s.masks)

    def mask_array(self, name):
        return self.s.mask(name).copy()

    def layer_pixels(self, name):
        return self.s.layer(name)["px"].copy()

    def composite(self):
        return self.s.composite()

    def snapshot(self, k):
        self._flush()
        return self._state_at(k + 1).composite()

    def top_stroke_at(self, x, y):
        x, y = int(x), int(y)
        if not (0 <= x < self.s.w and 0 <= y < self.s.h):
            raise ValueError(f"({x}, {y}) is outside the {self.s.w}x{self.s.h} canvas")
        return int(self.s.last[y, x]) or None

    def stroke_info(self, sid):
        if sid not in self.s.info:
            raise KeyError(f"no stroke {sid} (undone, or never made)")
        b, i = self.s.info[sid]
        bt = self.batches[b] if b < len(self.batches) else (self._open or self._loose)  # may be still open
        return {**bt["ops"][i], "id": sid, "bbox": list(self.s.covs[sid][0]), "batch": b,
                "label": bt["label"], "author": bt["author"]}

    def stroke_coverage(self, sid):
        self.stroke_info(sid)
        (x0, y0, x1, y1), a = self.s.covs[sid]
        out = np.zeros((self.s.h, self.s.w), np.float32)
        out[y0:y1, x0:x1] = a / 255
        return out

    def export_png(self, path):
        Image.fromarray((np.clip(self.composite(), 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)
