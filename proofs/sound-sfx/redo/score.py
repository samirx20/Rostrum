"""Score every cut against its kind's description, in ONE model load (CLAP venv, GPU slot).

For each item: `cosine` with its own kind's text, `prob` = softmax of its own text against the
other kinds' texts and the old pass's wrong sounds (kinds.contrast), and `heard_as` = the text it
is closest to of all. Writes the input list back with those fields added.

Run (from proofs/sound-sfx, model venv, through heavy.ps1 gpu):
  python -m redo.score <items.json> <out.json> [<items2.json> <out2.json> ...] [--device cuda]
"""
import json
import sys
import time

from match.audio import Take
from match.model import Matcher

from .kinds import KINDS, contrast


def score(m, items):
    names = list(KINDS)
    texts = [KINDS[n]["text"] for n in names] + contrast(names[0])[len(names) - 1:]
    t_emb = m.embed_texts(texts)
    cos = m.embed_takes([Take(i["path"], float(i.get("offset") or 0), i.get("length")) for i in items]) @ t_emb.T
    for i, row in zip(items, cos):
        own = names.index(i["kind"])
        cols = [own] + [c for c in range(len(texts)) if c != own]
        i["cosine"] = round(float(row[own]), 4)
        i["prob"] = round(float(m.softmax(row[cols])[0]), 4)
        i["heard_as"] = texts[int(row.argmax())]
    return items


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    device = "cuda" if "--device" not in sys.argv else sys.argv[sys.argv.index("--device") + 1]
    args = [a for a in args if a != device]
    if not args or len(args) % 2:
        sys.exit("usage: python -m redo.score <items.json> <out.json> [...] [--device cuda|cpu]")
    t0 = time.time()
    m = Matcher(device=device)
    load_s = time.time() - t0
    summary = {}
    try:
        for src, dst in zip(args[::2], args[1::2]):
            with open(src, encoding="utf-8") as f:
                items = score(m, json.load(f))
            with open(dst, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=1)
            summary[dst] = len(items)
        import torch
        peak = torch.cuda.max_memory_allocated() / 2**20 if torch.cuda.is_available() else 0
    finally:
        m.close()
    print(json.dumps({"scored": summary, "load_s": round(load_s, 1), "total_s": round(time.time() - t0, 1),
                      "device": device, "peak_gpu_mb": round(peak)}))


if __name__ == "__main__":
    main()
