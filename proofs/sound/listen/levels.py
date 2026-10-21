"""levels: per-stem loudness, share of the mix per band, who dominates, buried/crowded facts."""
import os

import numpy as np
import pyloudnorm as pyln

from .core import BAND_NAMES, band_power, db, duration, load, num, section_power, sections

ACTIVE_DB = -70.0   # a section quieter than this counts as "stem not playing"
CROWD_SHARE = 30.0  # % of a band's energy each, for two stems to count as sharing it
CROWD_MIN_DB = -45.0


def analyse(stems, mix=None, section_s=5.0, buried_db=15.0):
    names = [os.path.basename(p) for p in stems]
    data = [load(p) for p in stems]
    sr = data[0][1]
    if any(s != sr for _, s in data):
        raise ValueError("stems have different sample rates; resample first")
    n = max(y.shape[0] for y, _ in data)
    ys = [np.pad(y, ((0, n - y.shape[0]), (0, 0))) for y, _ in data]
    if mix:
        my, msr = load(mix)
        if msr != sr:
            raise ValueError("mix sample rate differs from the stems")
        my = np.pad(my, ((0, max(0, n - my.shape[0])), (0, 0)))[:max(n, my.shape[0])]
    else:
        ch = max(y.shape[1] for y in ys)
        my = sum(np.repeat(y, ch, axis=1) if y.shape[1] == 1 and ch > 1 else y for y in ys)
    dur = n / sr
    secs = sections(dur, section_s)
    times, mix_pw = band_power(my, sr)
    mix_whole = mix_pw.mean(axis=1)
    pws = [band_power(y, sr)[1] for y in ys]
    sps = [section_power(times, p, secs) for p in pws]     # [secs, bands] per stem
    totals = np.array([sp.sum(axis=1) for sp in sps])      # [stems, secs]
    totals_db = np.array([[db(v) for v in row] for row in totals])
    meter = pyln.Meter(sr)

    stems_out = []
    for i, y in enumerate(ys):
        whole = pws[i].mean(axis=1)
        lufs = meter.integrated_loudness(y) if y.shape[0] >= int(0.4 * sr) else float("-inf")
        stems_out.append({
            "stem": names[i], "lufs": num(lufs), "peak_dbfs": num(db(np.max(np.abs(y)) ** 2)),
            "share_of_mix_energy_pct": {b: num(100 * whole[k] / max(mix_whole[k], 1e-30), 1)
                                        for k, b in enumerate(BAND_NAMES)},
            "level_db_per_section": [num(v, 1) for v in totals_db[i]]})

    sec_rows, buried_gap = [], [[] for _ in names]
    for s, (t0, t1) in enumerate(secs):
        order = np.argsort(-totals_db[:, s])
        row = {"from_s": num(t0, 2), "to_s": num(t1, 2), "loudest_stem": names[order[0]],
               "ranking": [names[j] for j in order if totals_db[j, s] > ACTIVE_DB]}
        dom = {}
        for k, b in enumerate(BAND_NAMES):
            col = np.array([sp[s, k] for sp in sps])
            if col.sum() > 0 and db(col.sum()) > CROWD_MIN_DB:
                dom[b] = names[int(np.argmax(col))]
        row["dominant_per_band"] = dom
        sec_rows.append(row)
        for j in range(len(names)):
            if totals_db[j, s] > ACTIVE_DB and len(names) > 1:
                others = np.delete(totals_db[:, s], j).max()
                buried_gap[j].append(others - totals_db[j, s])

    flags = []
    for j, gaps in enumerate(buried_gap):
        if gaps and min(gaps) > buried_db:
            flags.append({"flag": "buried", "stem": names[j],
                          "detail": f"always >{buried_db:g} dB under the loudest other stem "
                                    f"(smallest gap {min(gaps):.1f} dB over {len(gaps)} active sections)"})
    for s, (t0, t1) in enumerate(secs):
        for k, b in enumerate(BAND_NAMES):
            col = np.array([sp[s, k] for sp in sps])
            tot = col.sum()
            if tot <= 0 or db(tot) <= CROWD_MIN_DB:
                continue
            heavy = [names[j] for j in range(len(names)) if 100 * col[j] / tot >= CROWD_SHARE]
            if len(heavy) >= 2:
                flags.append({"flag": "crowded_band", "from_s": num(t0, 1), "to_s": num(t1, 1),
                              "band": b, "stems": heavy,
                              "detail": f"each holds >={CROWD_SHARE:g}% of the {b} energy: they overlap there"})
    return {"section_s": section_s, "mix": mix or "sum of stems", "duration_s": num(dur, 2),
            "stems": stems_out, "sections": sec_rows, "flags": flags,
            "note": "share >100% means the mix is quieter than that stem alone; flags are facts about levels, not verdicts; a buried stem may be meant to sit low"}
