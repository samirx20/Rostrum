"""levels: per-stem loudness, each stem against the loudest and against the mix, buried flags."""
import numpy as np

from .bs1770 import integrated
from .core import db, duration, is_float_file, load, num, peak_db, sections
from .loudness import CLIP_LEVEL

ACTIVE_DB = -70.0     # a section quieter than this counts as "stem not playing"


def _pad_to(y, n, ch):
    y = np.pad(y, ((0, n - y.shape[0]), (0, 0)))
    return np.repeat(y, ch, axis=1) if y.shape[1] == 1 and ch > 1 else y


def _lufs(y, sr):
    return integrated(y, sr)


def levels(stems, mix=None, section_s=2.0, buried_db=18.0):
    """stems: {id: wav path}; mix: its rendered wav (default: the stems summed).
    Per stem: LUFS, peak, RMS, dB under the loudest stem and dB against the mix.
    flags: a float stem above 0 dBFS ("over full scale": held, not clipped); a fixed-point stem at full scale ("clips"); a stem more than `buried_db` under the loudest other stem in every section it plays."""
    if not stems:
        raise ValueError("levels: no stems given")
    data = {k: load(p) for k, p in stems.items()}
    floats = {k: is_float_file(p) for k, p in stems.items()}
    sr = next(iter(data.values()))[1]
    for k, (_, s) in data.items():
        if s != sr:
            raise ValueError(f"levels: stem '{k}' is {s} Hz but the others are {sr} Hz; resample first")
    n = max(y.shape[0] for y, _ in data.values())
    ch = max(y.shape[1] for y, _ in data.values())
    ys = {k: _pad_to(y, n, ch) for k, (y, _) in data.items()}
    if mix:
        my, msr = load(mix)
        if msr != sr:
            raise ValueError(f"levels: mix is {msr} Hz but the stems are {sr} Hz")
    else:
        my = sum(ys.values())
    mix_lufs = _lufs(my, sr)

    ids = list(ys)
    secs = sections(duration(my, sr), section_s)
    sec_db = np.array([[db(np.mean(ys[k][int(a * sr):int(b * sr)].astype(np.float64) ** 2)) for a, b in secs]
                       for k in ids])                      # [stems, sections], dB RMS
    lufs = {k: _lufs(ys[k], sr) for k in ids}
    top = max(v for v in lufs.values())
    rows = {}
    for k in ids:
        rows[k] = {"lufs": num(lufs[k]), "peak_dbfs": num(peak_db(ys[k])),
                   "rms_dbfs": num(db(np.mean(ys[k].astype(np.float64) ** 2))),
                   "db_under_loudest": num(top - lufs[k], 1),
                   "db_vs_mix": num(lufs[k] - mix_lufs, 1)}
    flags = []
    for k, r in rows.items():
        r["format"] = "32-bit float" if floats[k] else "fixed-point"
        if floats[k] and r["peak_dbfs"] > 0.0:
            flags.append({"flag": "over full scale", "stem": k, "peak_dbfs": r["peak_dbfs"], "clips": False,
                          "detail": "this float file holds the peak above 0 dBFS without clipping; it would clip only if "
                                    "converted to a fixed-point file (16 or 24-bit) without turning it down first"})
        elif not floats[k] and r["peak_dbfs"] >= db(CLIP_LEVEL ** 2):
            flags.append({"flag": "clips", "stem": k, "peak_dbfs": r["peak_dbfs"], "clips": True,
                          "detail": "this fixed-point file reaches full scale: the peaks are cut flat in the file"})
    for i, k in enumerate(ids):
        gaps = [np.delete(sec_db[:, s], i).max() - sec_db[i, s]
                for s in range(len(secs)) if sec_db[i, s] > ACTIVE_DB and len(ids) > 1]
        if gaps and min(gaps) > buried_db:
            flags.append({"flag": "buried", "stem": k, "smallest_gap_db": num(min(gaps), 1),
                          "detail": f"always more than {buried_db:g} dB under the loudest other stem "
                                    f"({len(gaps)} active sections of {section_s:g} s)"})
    return {"mix_lufs": num(mix_lufs), "mix": mix or "sum of stems", "section_s": section_s,
            "stems": rows, "flags": flags,
            "note": "flags are facts, not verdicts: a stem may be meant to sit low"}
