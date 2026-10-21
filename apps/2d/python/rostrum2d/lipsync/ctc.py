"""CTC over the phone model's per-frame log probabilities (frames × labels): forced alignment of a known label
sequence (Viterbi), and free decoding (best label per frame). Pure numpy; each returns one frame span per label."""
from __future__ import annotations


def log_softmax(logits):
    import numpy as np
    x = logits.astype(np.float64)
    m = x.max(axis=1, keepdims=True)
    return x - m - np.log(np.exp(x - m).sum(axis=1, keepdims=True))


def align(logp, labels: list[int], blank: int) -> list[tuple[int, int]]:
    """(first, last) frame of each label on the best path that says `labels` in order. Too few frames is a ValueError."""
    import numpy as np
    T, S = logp.shape[0], 2 * len(labels) + 1
    if not labels:
        return []
    if T < len(labels):
        raise ValueError(f"{len(labels)} phones can't fit in {T} frames ({T * 0.02:.2f} s of audio)")
    ext = np.array([blank if s % 2 == 0 else labels[s // 2] for s in range(S)])
    skip = np.zeros(S, bool)                                 # s may come from s-2: a label after a different label
    skip[3::2] = ext[3::2] != ext[1:-2:2]
    prev = np.full(S, -np.inf)
    prev[:2] = logp[0, ext[:2]]
    back = np.zeros((T, S), np.int8)
    for t in range(1, T):
        stay, step = prev, np.concatenate(([-np.inf], prev[:-1]))
        jump = np.where(skip, np.concatenate(([-np.inf, -np.inf], prev[:-2])), -np.inf)
        choice = np.stack([stay, step, jump])
        back[t] = choice.argmax(axis=0)
        prev = choice.max(axis=0) + logp[t, ext]
    s = S - 2 if prev[S - 2] > prev[S - 1] else S - 1
    if not np.isfinite(prev[s]):
        raise ValueError(f"no alignment of {len(labels)} phones fits {T} frames")
    spans = [[-1, -1] for _ in labels]
    for t in range(T - 1, -1, -1):
        if s % 2:
            k = s // 2
            spans[k][0] = t
            if spans[k][1] < 0:
                spans[k][1] = t
        s -= int(back[t, s])
    return [tuple(x) for x in spans]


def decode(logp, blank: int) -> list[tuple[int, int, int]]:
    """(label, first, last) of each run of the best label per frame, blanks dropped, repeats merged."""
    best = logp.argmax(axis=1)
    out = []
    for t, lab in enumerate(best.tolist()):
        if lab == blank:
            continue
        if out and out[-1][0] == lab and out[-1][2] == t - 1:
            out[-1][2] = t
        else:
            out.append([lab, t, t])
    return [tuple(x) for x in out]
