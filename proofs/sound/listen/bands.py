"""bands: energy per frequency band, averaged over sections of N seconds."""
from .core import BAND_NAMES, BANDS, band_power, db, duration, load, num, section_power, sections

RANGES = {n: (lo, hi) for n, lo, hi in BANDS}


def analyse(path_or_data, section_s=5.0, sr=None):
    y, sr = load(path_or_data) if isinstance(path_or_data, str) else (path_or_data, sr)
    times, pw = band_power(y, sr)
    secs = sections(duration(y, sr), section_s)
    sp = section_power(times, pw, secs)
    rows = []
    for (t0, t1), p in zip(secs, sp):
        tot = max(p.sum(), 1e-30)
        rows.append({"from_s": num(t0, 2), "to_s": num(t1, 2),
                     "db": {n: num(db(v), 1) for n, v in zip(BAND_NAMES, p)},
                     "share_pct": {n: num(100 * v / tot, 1) for n, v in zip(BAND_NAMES, p)},
                     "total_db": num(db(tot), 1)})
    return {"band_hz": {n: [lo, hi or "nyquist"] for n, (lo, hi) in RANGES.items()},
            "section_s": section_s, "sections": rows,
            "note": "db ~ dBFS RMS inside the band; share_pct = band's share of total energy"}
