"""stereo: left/right balance, correlation and mono-compatibility per section."""
import numpy as np

from .core import db, duration, load, name_of, num, sections


def stereo(wav, sections_s=5.0):
    """Per `sections_s`-second section: L/R balance (dB, + = left louder), correlation
    (+1 identical, < 0 cancels in mono), side-vs-mid width and mono loss (dB)."""
    y, sr = load(wav)
    if y.shape[1] < 2:
        return {"file": name_of(wav), "channels": 1, "sections": [],
                "note": "mono file: no stereo image"}
    L, R = y[:, 0].astype(np.float64), y[:, 1].astype(np.float64)
    rows, warn = [], []
    for t0, t1 in sections(duration(y, sr), sections_s):
        l, r = L[int(t0 * sr):int(t1 * sr)], R[int(t0 * sr):int(t1 * sr)]
        el, er = np.mean(l ** 2), np.mean(r ** 2)
        base = {"from_s": num(t0, 2), "to_s": num(t1, 2)}
        if el < 1e-12 and er < 1e-12:
            rows.append({**base, "silent": True})
            continue
        corr = float(np.corrcoef(l, r)[0, 1]) if el > 0 and er > 0 and (l != r).any() else 1.0
        em, es = np.mean(((l + r) / 2) ** 2), np.mean(((l - r) / 2) ** 2)
        loss = db(em) - db((el + er) / 2)
        rows.append({**base, "balance_lr_db": num(db(el) - db(er), 1), "correlation": num(corr, 3),
                     "width_pct": num(100 * es / max(em + es, 1e-30), 1), "mono_loss_db": num(loss, 1)})
        if corr < 0 or loss < -6:
            warn.append(f"{t0:g}-{t1:g}s: correlation {corr:.2f}, mono sum {loss:.1f} dB quieter")
    return {"file": name_of(wav), "channels": y.shape[1], "section_s": sections_s, "sections": rows,
            "mono_warnings": warn, "note": "width_pct = share of energy in the side signal"}
