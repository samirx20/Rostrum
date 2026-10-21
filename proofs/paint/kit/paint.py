"""One CLI over the painting document, seeing and where. See HOWTO.md.

    python paint.py <doc.paint.json> <command> ...

Image commands write a PNG (default: LOOK_ROOT/<document name>/, outside the worktree), print its path, and fail
loudly (message on stderr, exit code 2) on bad arguments.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import see  # noqa: E402
import where  # noqa: E402

KEEP = 40  # newest look pictures kept per command
LOOK_ROOT = os.path.join(os.path.expanduser("~"), ".rostrum", "waves", "scratch", "paint-look")


def out_path(docpath, cmd, out):
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        return os.path.abspath(out)
    name = os.path.basename(docpath)
    d = os.path.join(LOOK_ROOT, name[:-len(".paint.json")] if name.endswith(".paint.json") else name)
    os.makedirs(d, exist_ok=True)
    mine = sorted(f for f in os.listdir(d) if f.startswith(cmd + "-") and f.endswith(".png"))
    n = int(mine[-1][len(cmd) + 1:-4]) + 1 if mine else 1
    for f in mine[:max(0, len(mine) - KEEP + 1)]:
        os.remove(os.path.join(d, f))
    return os.path.join(d, f"{cmd}-{n:03d}.png")


def zoom_arg(p):
    p.add_argument("--zoom", type=float, nargs=4, metavar=("X", "Y", "W", "H"), help="canvas-pixel box to look at")
    p.add_argument("--grid", type=int, help="grid spacing in canvas px (0 = none; default: about 8 lines)")
    p.add_argument("--out", help="where to write the PNG")


def build():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("doc", help="the .paint.json file")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("see", help="look at the canvas, with a labelled pixel grid"); zoom_arg(p)
    p.add_argument("--size", type=int, default=1200, help="picture width in px")
    p.add_argument("--layer", help="show only this layer (over a checkerboard)")
    p = sub.add_parser("before-after", help="last K batches: before | after | difference"); zoom_arg(p)
    p.add_argument("--batches", type=int, default=1); p.add_argument("--size", type=int, default=600, help="width of each panel")
    p = sub.add_parser("ref", help="reference image beside the work, same scale"); zoom_arg(p)
    p.add_argument("ref"); p.add_argument("--diff", action="store_true"); p.add_argument("--size", type=int, default=600)
    p = sub.add_parser("values", help="greyscale + value steps"); zoom_arg(p)
    p.add_argument("--steps", type=int, default=5); p.add_argument("--size", type=int, default=600)
    p = sub.add_parser("small", help="as seen small"); p.add_argument("--width", type=int, default=480); p.add_argument("--out")
    p = sub.add_parser("what", help="what is at this pixel"); p.add_argument("x", type=int); p.add_argument("y", type=int)
    p = sub.add_parser("landed", help="did this stroke land on its path"); p.add_argument("stroke", type=int)
    p = sub.add_parser("export", help="the finished picture, full size, no grid"); p.add_argument("out")
    sub.add_parser("history"); sub.add_parser("undo"); sub.add_parser("redo")
    p = sub.add_parser("run", help="run a stroke script against the document, then save"); p.add_argument("script")
    p.add_argument("--new", nargs=2, type=int, metavar=("W", "H"), help="start a new document of this size if the file does not exist")
    return ap


def history_text(doc):
    hist = doc.history()
    if not hist:
        return "no batches yet"
    return "\n".join(f"#{e['batch']:<3} {e['label']!r:<40} {e.get('author', '?'):<18} {e['n_ops']} ops, strokes {e.get('stroke_ids')}"
                     for e in hist)


def run(a):
    from doc import Doc
    if a.cmd == "run":
        if not os.path.exists(a.script):
            raise FileNotFoundError(f"script {a.script} not found")
        if os.path.exists(a.doc):
            doc = Doc.open(a.doc)
        elif a.new:
            doc = Doc.new(a.new[0], a.new[1])
        else:
            raise FileNotFoundError(f"{a.doc} does not exist (use --new W H to create it)")
        before = len(doc.history())
        scope = {"doc": doc, "__name__": "__paint_script__", "__file__": os.path.abspath(a.script)}
        with open(a.script, encoding="utf-8") as f:
            code = compile(f.read(), a.script, "exec")
        sys.path.insert(0, os.path.dirname(os.path.abspath(a.script)))
        exec(code, scope)
        doc.save(a.doc)
        new = doc.history()[before:]
        print(f"ran {a.script}: {len(new)} new batch(es); saved {os.path.abspath(a.doc)}")
        for e in new:
            print(f"  #{e['batch']} {e['label']!r}: {e['n_ops']} ops, strokes {e.get('stroke_ids')}")
        return
    if not os.path.exists(a.doc):
        raise FileNotFoundError(f"{a.doc} does not exist")
    doc = Doc.open(a.doc)
    c = a.cmd
    old_redo = a.doc + ".redo"  # older kit versions kept the redo list in this side file
    if os.path.exists(old_redo) and not doc._redo:
        with open(old_redo, encoding="utf-8") as f:
            doc._redo = json.load(f)
    if c in ("see", "before-after", "ref", "values", "small"):
        if c == "see":
            img = see.layer_view(doc, a.layer, a.zoom, a.grid, a.size) if a.layer else \
                see.view(np_comp(doc), a.zoom, a.grid, a.size)
        elif c == "before-after":
            img, box = see.before_after(doc, a.batches, a.zoom, a.grid, a.size)
            print("changed box:", box)
        elif c == "ref":
            if not os.path.exists(a.ref):
                raise FileNotFoundError(f"reference {a.ref} not found")
            img = see.side_by_side(doc, a.ref, a.zoom, a.grid, a.size, a.diff)
        elif c == "values":
            if not 2 <= a.steps <= 16:
                raise ValueError("--steps must be 2..16")
            img = see.values(doc, a.zoom, a.grid, a.size, a.steps)
        else:
            img = see.small(doc, a.width)
        path = out_path(a.doc, c.replace("-", "_"), a.out)
        img.save(path)
        print(path)
    elif c == "what":
        print(where.what(doc, a.x, a.y))
    elif c == "landed":
        print(where.landed_text(where.landed(doc, a.stroke)))
    elif c == "history":
        print(history_text(doc))
    elif c == "export":
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        doc.export_png(a.out)
        print(os.path.abspath(a.out))
    elif c in ("undo", "redo"):
        before = len(doc.history())
        getattr(doc, c)()
        doc.save(a.doc)  # the redo list is saved in the document
        if os.path.exists(old_redo):
            os.remove(old_redo)
        print(f"{c} done; {len(doc.history())} batch(es) now (was {before}); saved")


def np_comp(doc):
    import numpy as np
    return np.asarray(doc.composite(), np.float32)


def main(argv=None):
    a = build().parse_args(argv)
    try:
        run(a)
    except Exception as e:  # fail loudly, never carry on
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
