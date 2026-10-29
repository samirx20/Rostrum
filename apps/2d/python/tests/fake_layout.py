"""A stand-in for the engine's `measure` and `layout` requests in the layout tests (textsize.use(FakeEngine())): a text
is 10 px a character on one line, `size` px a line, wrapped at its boxWidth; a layout is a plain row or column of
the children at their own sizes from the padding, `gap` apart, a fit side following them. `boxes` gives fixed
answers by node id instead; `layouts` records each request's trees."""
import math


class FakeEngine:
    def __init__(self, boxes=None):
        self.boxes, self.layouts = boxes, []

    def measure(self, items):
        out = {}
        for i in items:
            w = 10.0 * len(i["body"])
            lines = math.ceil(w / i["boxWidth"]) if i.get("boxWidth") else 1
            out[i["id"]] = (min(w, i["boxWidth"]) if i.get("boxWidth") else w, i["size"] * max(lines, 1))
        return out

    def layout(self, trees):
        self.layouts.append(trees)
        if self.boxes is not None:
            return [{k: tuple(v) for k, v in self.boxes.items()} for _ in trees]
        out = []
        for tree in trees:
            got = {}
            got[tree["id"]] = (0.0, 0.0, *self._lay(tree, got))
            out.append(got)
        return out

    def _size(self, node, got):
        s = node["style"]
        if node["kind"] == "box":
            return self._lay(node, got)
        if node["kind"] == "text":
            return 10.0 * len(node["text"]["body"]), node["text"]["size"]
        num = lambda v, own: v if isinstance(v, (int, float)) else own      # "auto", "N%", "fit": its own size here
        return num(s.get("width"), node["w"]), num(s.get("height"), node["h"])

    def _lay(self, box, got):
        s = box["style"]
        pad = s.get("padding", 0)
        top, right, bottom, left = pad if isinstance(pad, list) else [pad] * 4
        row = s.get("direction", "row") == "row"
        gap = s.get("columnGap" if row else "rowGap", 0)
        at, cross = 0.0, 0.0
        for child in box["children"]:
            w, h = self._size(child, got)
            if child["style"].get("position") == "absolute":
                got[child["id"]] = (child["style"]["left"], child["style"]["top"], w, h)
                continue
            got[child["id"]] = (left + at, top, w, h) if row else (left, top + at, w, h)
            at += (w if row else h) + gap
            cross = max(cross, h if row else w)
        at = max(at - gap, 0.0)
        cw, ch = (at, cross) if row else (cross, at)
        w = s["width"] if isinstance(s.get("width"), (int, float)) else cw + left + right
        h = s["height"] if isinstance(s.get("height"), (int, float)) else max(ch + top + bottom, s.get("minHeight", 0))
        return w, h
