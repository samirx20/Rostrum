"""stereo: left/right correlation, width and mono-compatibility per section."""
import numpy as np

from .core import db, duration, load, num, sections


def analyse(path_or_data, section_s=5.0, sr=None):
    y, sr = load(path_or_data) if isinstance(path_or_data, str) else (path_or_data, sr)
    if y.shape[1] < 2:
        return {"channels": 1, "note": "mono file: no stereo image"}
    L, R = y[:, 0].astype(np.float64), y[:, 1].astype(np.float64)
    rows, warn = [], []
    for t0, t1 in sections(duration(y, sr), section_s):
        a, b = int(t0 * sr), int(t1 * sr)
        l, r = L[a:b], R[a:b]
        el, er = np.mean(l ** 2), np.mean(r ** 2)
        if el < 1e-12 and er < 1e-12:
            rows.append({"from_s": num(t0, 2), "to_s": num(t1, 2), "silent": True})
            continue
        corr = float(np.corrcoef(l, r)[0, 1]) if el > 0 and er > 0 and (l != r).any() else 1.0
        mid, side = (l + r) / 2, (l - r) / 2
        em, es = np.mean(mid ** 2), np.mean(side ** 2)
        loss = db(em) - db((el + er) / 2)
        row = {"from_s": num(t0, 2), "to_s": num(t1, 2), "correlation": num(corr, 3),
               "side_vs_mid_db": num(db(es) - db(em), 1),
               "width_pct": num(100 * es / max(em + es, 1e-30), 1),
               "balance_lr_db": num(db(el) - db(er), 1),
               "mono_loss_db": num(loss, 1)}
        rows.append(row)
        if corr < 0 or loss < -6:
            warn.append(f"{t0:g}-{t1:g}s: correlation {corr:.2f}, mono sum {loss:.1f} dB quieter")
    return {"channels": y.shape[1], "section_s": section_s, "sections": rows,
            "mono_compat_warnings": warn,
            "note": "correlation +1 = identical, 0 = unrelated, <0 = cancels in mono; width_pct = side energy share"}
