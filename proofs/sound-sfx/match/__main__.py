"""Sound-match check: how well does a take fit a description?

  python -m match rank  --text "small iron ring tapping a brass plate, close" a.wav b.ogg@0.29+1.39 ...
  python -m match score --pairs pairs.json      # [{"path", "text", "offset"?, "length"?}, ...]
  python -m match eval  match/eval_set.json     # zero-shot accuracy, see match/eval.py

Prints ONE JSON line on stdout (progress and errors go to stderr). Run from proofs/sound-sfx/.
"""
import argparse
import json
import sys
import time

# Contrast texts used when the caller gives none: broad everyday sound families, so the softmax
# says "this take is more X than any of these". Agents should pass their own --contrast.
DEFAULT_CONTRAST = [
    "a wooden knock", "metal clinking", "a whoosh through the air", "a door creaking",
    "cloth rustling", "footsteps", "glass clinking", "paper rustling", "water pouring",
    "an electronic beep",
]


def _common(p):
    p.add_argument("--model", default=None, help="Hugging Face id or local folder (default laion/larger_clap_general)")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--pad", default="silence", choices=["silence", "repeat"],
                   help="how takes shorter than 10 s are filled (default silence)")
    p.add_argument("--keep", type=int, default=3, help="loudest 10 s windows kept for long takes")


def _matcher(a):
    from .model import DEFAULT_MODEL, Matcher
    return Matcher(a.model or DEFAULT_MODEL, a.device, a.pad, a.keep)


def rank(a, m):
    from .audio import Take
    takes = [Take.parse(s) for s in a.takes]
    contrast = [c for c in (a.contrast or DEFAULT_CONTRAST) if c not in a.text]
    texts = a.text + contrast
    cos = m.embed_takes(takes) @ m.embed_texts(texts).T          # takes x texts
    out = []
    for j, target in enumerate(a.text):
        # softmax over this target + the contrast texts only (other targets left out)
        cols = [j] + list(range(len(a.text), len(texts)))
        prob = m.softmax(cos[:, cols])
        rows = [{"take": t.label(), "cosine": round(float(cos[i, j]), 4),
                 "prob": round(float(prob[i, 0]), 4),
                 "best_other": max(contrast, key=lambda c: cos[i, texts.index(c)]) if contrast else None}
                for i, t in enumerate(takes)]
        rows.sort(key=lambda r: -r[a.by])
        out.append({"text": target, "ranked": rows})
    return {"command": "rank", "by": a.by, "contrast": contrast, "results": out}


def score(a, m):
    from .audio import Take
    with open(a.pairs, encoding="utf-8") as f:
        pairs = json.load(f)
    takes = [Take.from_dict(p) for p in pairs]
    texts = sorted({p["text"] for p in pairs})
    cos = m.embed_takes(takes) @ m.embed_texts(texts).T
    return {"command": "score", "pairs": [
        {"take": t.label(), "text": p["text"], "cosine": round(float(cos[i, texts.index(p["text"])]), 4)}
        for i, (t, p) in enumerate(zip(takes, pairs))]}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m match", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rank", help="rank takes against one or more texts")
    r.add_argument("--text", action="append", required=True, help="what the take should sound like (repeatable)")
    r.add_argument("--contrast", action="append", help="texts it should NOT sound like (repeatable)")
    r.add_argument("--by", default="cosine", choices=["cosine", "prob"])
    r.add_argument("takes", nargs="+", help="file or file@start+length (seconds)")
    _common(r)
    s = sub.add_parser("score", help="cosine for each {path, text} pair in a JSON file")
    s.add_argument("--pairs", required=True)
    _common(s)
    e = sub.add_parser("eval", help="zero-shot accuracy on an eval set (see match/eval.py)")
    e.add_argument("eval_set")
    e.add_argument("--out", help="also write the full report here")
    _common(e)
    a = ap.parse_args(argv)

    from .peak import peak
    t0 = time.perf_counter()
    m = _matcher(a)
    t_load = time.perf_counter() - t0
    try:
        if a.cmd == "eval":
            from .eval import evaluate
            res = evaluate(m, a.eval_set, a.out)
        else:
            res = (rank if a.cmd == "rank" else score)(a, m)
        res.update(model=m.name, device=m.device, pad=a.pad, keep=a.keep,
                   load_s=round(t_load, 2), run_s=round(time.perf_counter() - t0 - t_load, 2), **peak())
    finally:
        m.close()
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
