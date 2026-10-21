"""Does the model's ranking agree with what a take actually is? Zero-shot accuracy.

Eval set (JSON):
  {"labels": {"<label>": "<text the model sees>", ...},
   "items":  [{"path", "offset"?, "length"?, "true_label", "name"?}, ...]}
For each take, every label text is scored; top-1 accuracy = how often the best text is the
take's true label. Also top-3, per-label accuracy, and the commonest confusions.

  python -m match eval match/eval_set.json [--out report.json]   (or python -m match.eval ...)
"""
import json
from collections import Counter

import numpy as np

from .audio import Take


def evaluate(m, eval_set_path, out_path=None) -> dict:
    with open(eval_set_path, encoding="utf-8") as f:
        es = json.load(f)
    labels = list(es["labels"])
    items = es["items"]
    unknown = {it["true_label"] for it in items} - set(labels)
    if unknown:
        raise ValueError(f"items use labels not in 'labels': {sorted(unknown)}")
    cos = m.embed_takes([Take.from_dict(it) for it in items]) @ m.embed_texts([es["labels"][l] for l in labels]).T
    prob = m.softmax(cos)
    order = np.argsort(-cos, axis=1)
    per, confusions, rows = {l: [0, 0] for l in labels}, Counter(), []
    top1 = top3 = 0
    for i, it in enumerate(items):
        truth = labels.index(it["true_label"])
        guess = labels[order[i, 0]]
        hit1, hit3 = order[i, 0] == truth, truth in order[i, :3]
        top1 += hit1
        top3 += hit3
        per[it["true_label"]][0] += hit1
        per[it["true_label"]][1] += 1
        if not hit1:
            confusions[f'{it["true_label"]} -> {guess}'] += 1
        rows.append({"name": it.get("name"), "take": Take.from_dict(it).label(), "true": it["true_label"],
                     "guess": guess, "p_true": round(float(prob[i, truth]), 4),
                     "rank_of_true": int(np.where(order[i] == truth)[0][0]) + 1})
    n = len(items)
    report = {"command": "eval", "eval_set": str(eval_set_path), "n": n, "labels": len(labels),
              "chance": round(1 / len(labels), 4),
              "top1": round(top1 / n, 4), "top3": round(top3 / n, 4),
              "per_label": {l: f"{h}/{c}" for l, (h, c) in per.items()},
              "confusions": dict(confusions.most_common(8))}
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({**report, "items": rows}, f, indent=1, ensure_ascii=False)
    return report


if __name__ == "__main__":
    import sys
    from .__main__ import main
    sys.exit(main(["eval", *sys.argv[1:]]))
