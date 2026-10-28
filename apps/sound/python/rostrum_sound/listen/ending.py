"""ending: how a file ends. Does the sound reach silence, or is it still going when the file stops (a cut)?

Facts only: the level of the last 0.5 s, whether it is still above -50 dBFS (not finished), whether the last 50 ms
fall faster than the fade before them (a cut: a fade drops a little every block, a cut drops all at once), and the
audible end: where the sound falls under -60 dBFS for good (the last 50 ms block, of the louder channel, above it), so
"it rings out by 52 s" can be checked (critic r12)."""
import numpy as np

from .core import db, num

TAIL_S = 0.5            # the stretch whose level says "finished or not"
BLOCK_S = 0.05          # the last block, and the size of the blocks the fade before it is read in
SILENT_DBFS = -50.0     # a tail under this has finished
FADE_BLOCKS = 6         # blocks before the last one that give the fade's own slope
CUT_MIN_DB = 6.0        # the last block must fall at least this far, and 3x the fade's drop per block, to be a cut
CUT_TIMES_FADE = 3.0
NO_FADE_DB = 3.0        # a tail that fell less than this over its 0.5 s was not faded at all
HEARD_DBFS = -60.0      # under this a tail is gone for a listener at a normal level (the audible end)


def audible_end(y, sr) -> float:
    """Seconds into `y` where the sound falls under HEARD_DBFS for good: the end of the last 50 ms block (RMS of the
    louder channel) above it; 0 for a file that never reaches it."""
    a = np.asarray(y, dtype=np.float64)
    a = a.reshape(len(a), -1)
    n = max(1, int(BLOCK_S * sr))
    k = len(a) // n
    if not k:
        return 0.0
    rms = np.sqrt((a[:k * n].reshape(k, n, -1) ** 2).mean(axis=1)).max(axis=1)
    over = np.nonzero(rms > 10 ** (HEARD_DBFS / 20))[0]
    return float((over[-1] + 1) * n / sr) if over.size else 0.0


def ending(y, sr):
    """-> {last_0_5s_dbfs, finished, last_50ms_dbfs, last_50ms_drop_db, fade_drop_db_per_50ms, cut, audible_end_s, words}."""
    m = np.asarray(y, dtype=np.float64).mean(axis=1) if y.ndim > 1 else np.asarray(y, dtype=np.float64)
    n = max(1, int(BLOCK_S * sr))
    tail = m[-min(len(m), int(TAIL_S * sr)):]
    level = db(np.mean(tail ** 2))
    k = min(len(m) // n, 1 + FADE_BLOCKS)
    blocks = [db(np.mean(m[len(m) - (i + 1) * n:len(m) - i * n] ** 2)) for i in range(k)][::-1]     # oldest first
    last = blocks[-1]
    drop = blocks[-2] - last if len(blocks) > 1 else 0.0
    fade = (blocks[0] - blocks[-2]) / (len(blocks) - 2) if len(blocks) > 2 else 0.0              # dB lost per block before the last
    finished = level < SILENT_DBFS
    tail_fall = (db(np.mean(tail[:len(tail) // 4] ** 2)) - db(np.mean(tail[-len(tail) // 4:] ** 2))) if len(tail) >= 8 else 0.0
    cut = bool(not finished and (drop >= max(CUT_MIN_DB, CUT_TIMES_FADE * max(fade, 0.0)) or tail_fall < NO_FADE_DB))
    words = (f"Ending: last 0.5 s at {level:.0f} dBFS, finished (under {SILENT_DBFS:g})." if finished else
             f"Ending: last 0.5 s at {level:.0f} dBFS, still sounding (above {SILENT_DBFS:g}): the file "
             + ("is cut off" if cut else "ends in a fade that has not reached silence") + "; give the song a longer tail or a longer fadeOut.")
    heard = audible_end(y, sr)
    words += f" Audible end {heard:.2f} s (under {HEARD_DBFS:g} dBFS for good after it; the file is {len(m) / sr:.2f} s)."
    return {"audible_end_s": num(heard, 2), "last_0_5s_dbfs": num(level, 1), "finished": bool(finished), "last_50ms_dbfs": num(last, 1),
            "last_50ms_drop_db": num(drop, 1), "fade_drop_db_per_50ms": num(fade, 1), "cut": cut, "words": words}


DEAD_AIR_S = 0.95       # silence this long before the file ends reads as the piece stopping early (bench 3e: 1.0 s faulted; 0.85 s twice, and a 0.5 s decay, not)


def dead_air(y, sr) -> list[dict]:
    """[{"kind": "dead_air_end", ...}] when the last DEAD_AIR_S or more of the file is under HEARD_DBFS."""
    total = len(y) / sr
    heard = audible_end(y, sr)
    gap = total - heard
    return [{"kind": "dead_air_end", "at_s": num(heard, 2), "measured": {"silent_s": num(gap, 2), "file_s": num(total, 2)}}] \
        if heard > 0 and gap >= DEAD_AIR_S else []


def dead_air_words(f) -> str:
    d, t = f["measured"], f["at_s"]
    return (f"dead air at the end: nothing sounds from {t:g} s to the file's end at {d['file_s']:g} s ({d['silent_s']:g} s); "
            "a listener hears the piece stop early; let the last notes, a drone or the reverb run to the end "
            "(end=\"#end\" on the held notes, or a later release), or make the length end with the sound")
