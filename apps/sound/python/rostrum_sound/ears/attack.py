"""Each written note judged on its attack: is its pitch in the sound, and in the octave written?

A pitch finder follows one line, the loudest; on a part that rings (a harp arpeggio, a piano with the pedal, a bass
whose notes overlap their tails) it follows a ringing note and reads the next attack as missing, late or an octave
off. Here each written note is judged on what is NEW in the sound just after it starts: the spectrum of a short window
after the onset (LOOK, ending before the next note of the part starts) against the window just before it. A partial
counts where it stands over the spectrum around it and rose over what was already ringing, so a ringing earlier note
never reads as this one.

A written note is there when one of its own odd partials rose (the fundamental, 3rd or 5th harmonic: a note an
octave up has none of them). It sounds an octave LOW when the partials only a note an octave under has (1.5× and 0.5× or 2.5× the written
pitch) are there and rose with it, and an octave HIGH only when its even partials rose and the fundamental and 3rd
harmonic are clearly not there (a re-struck note under the pedal raises its upper partials, its fundamental still
rings: that reads as there). Partials that fall on a harmonic of another
note struck or held at that moment are not used: it can't tell there. Low notes' faint fundamentals don't matter: the
judgement reads the harmonics above them.
"""
from __future__ import annotations

import numpy as np

from ..doc.keys import pitch_name
from ..listen.core import load, mono, num

N_FFT = 16384                 # zero-padded FFT of the short window: fine bins to read peaks from
LOOK = (0.03, 0.35)           # seconds after the start judged: past the attack noise, until the part's next note
SHORTEST = 0.05               # the window is never shorter than this, even before a fast next note
PRE = 0.06                    # seconds before the start: what was already ringing
STANDS_DB = 8.0               # a partial this far over the median of the spectrum around it
ROSE_DB = 3.0                 # and this much louder than just before the start (new, not a ringing earlier note)
UNDER_LOUDEST_DB = 30.0       # and no further than this under the loudest peak of the window
LOWEST_HZ = 30.0              # partials under this are not read


def _hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _spec(x: np.ndarray, sr: float, a: float, b: float) -> np.ndarray | None:
    """dB spectrum of x from a to b seconds (one Blackman window, zero padded), or None when it is empty. Blackman,
    not Hann: its side lobes sit ~58 dB down, so a loud note's skirt never reads as a quiet partial beside it."""
    seg = x[max(0, int(a * sr)):max(0, int(b * sr))]
    if len(seg) < 64:
        return None
    win = np.blackman(len(seg))                          # amplitude per window sum: windows of any length compare
    return 20 * np.log10(np.abs(np.fft.rfft(seg * win, N_FFT)) / win.sum() + 1e-12)


class _Window:
    """The attack window of one onset and the window before it."""

    def __init__(self, x, sr, onset, end):
        start = onset + LOOK[0]
        self.sr, self.t = sr, end - start
        self.att, self.pre = _spec(x, sr, start, end), _spec(x, sr, onset - PRE - 0.01, onset - 0.01)

    def _band(self, spec, lo, hi):
        k = lambda f: int(round(f * N_FFT / self.sr))  # noqa: E731
        return spec[max(0, k(lo)):k(hi) + 1]

    def read(self, hz: float):
        """(dB the partial stands over the spectrum around it, dB it rose since just before the start), or None."""
        if self.att is None or hz < LOWEST_HZ or hz > self.sr / 2.2:
            return None
        tol = max(hz * (2 ** (0.35 / 12) - 1), 0.6 / self.t)          # a short window's peaks are wide
        side = max(hz * (2 ** (2 / 12) - 1), 5.0 / self.t)               # past the main lobe (3 / t each side)
        near, around = self._band(self.att, hz - tol, hz + tol), self._band(self.att, hz - side, hz + side)
        if len(near) < 3:
            return None
        top = near.max() if 0 < near.argmax() < len(near) - 1 else -np.inf    # a peak, not the slope of one beside it
        stands = top - np.median(around) if top >= self.att.max() - UNDER_LOUDEST_DB else -np.inf
        return stands, (np.inf if self.pre is None else top - self._band(self.pre, hz - tol, hz + tol).max())


def _masked(hz: float, others: set) -> bool:
    """`hz` falls on a harmonic (1st … 8th) of another note sounding: it can't tell whose partial it is."""
    return any(abs(12 * np.log2(hz / (_hz(o) * h))) < 0.5 for o in others for h in range(1, 9))


def judge(win: _Window, m: int, others: set) -> int | None:
    """0 the written pitch is there, -1 it sounds an octave low, +1 an octave high, None not there at all."""
    f = _hz(m)
    r = {h: None if _masked(h * f, others) else win.read(h * f) for h in (0.5, 2 / 3, 1, 1.5, 2, 2.5, 3, 5)}
    there = lambda h: r[h] is not None and r[h][0] >= STANDS_DB          # noqa: E731
    rose = lambda h: there(h) and r[h][1] >= ROSE_DB                     # noqa: E731
    gone = lambda h: r[h] is not None and r[h][0] < STANDS_DB / 2        # noqa: E731
    if rose(1.5) and (there(0.5) or there(2.5)):
        return -1
    if rose(1) or (rose(3) and (there(1) or rose(2) or rose(5))):   # the 3rd alone: also a fifth-up note's 2nd
        return 0
    if rose(2):                              # an octave up, or a re-struck note whose fundamental was still ringing
        if there(2 / 3) and not there(1):     # that 2nd harmonic is the 3rd of a note a fifth under: another note
            return None
        return 1 if gone(1) and gone(3) else 0
    return None                              # nothing of it was struck now (at most a ringing earlier note)


def polyphonic(written: list[dict], overlap_s: float = 0.05) -> bool:
    """True when the part ever sounds two written notes at once (a chord in one note, or notes overlapping)."""
    ends = []
    for w in sorted(written, key=lambda w: w["start"]):
        if len(w["midis"]) > 1 or any(e - w["start"] > overlap_s for e in ends):
            return True
        ends.append(w["end"])
    return False


def check(wav, written: list[dict]) -> list[dict]:
    """Rows per written pitch: {id, written, start_s, target, octave (0 / -1 / +1) or None (not there), heard}."""
    y, sr = load(wav)
    x = mono(y).astype(float)
    starts = sorted({w["start"] for w in written})
    rows = []
    for w in written:
        later = [s for s in starts if s > w["start"] + 0.01]
        end = w["start"] + min(LOOK[1], max(SHORTEST, (later[0] - w["start"] - 0.01) if later else LOOK[1]))
        win = _Window(x, sr, w["start"], max(end, w["start"] + LOOK[0] + SHORTEST))
        struck = {m for v in written if v is not w and (abs(v["start"] - w["start"]) < end - w["start"] or v["start"] < w["start"] < v["end"])
                  for m in v["midis"]}
        for m in w["midis"]:
            octave = judge(win, m, (struck | set(w["midis"])) - {m})
            rows.append({"id": w["id"], "written": pitch_name(m), "start_s": num(w["start"], 3), "target": m,
                         "octave": octave, "heard": pitch_name(m + 12 * octave) if octave is not None else None})
    return rows


def register(track: str, rows: list[dict]) -> str:
    """The track's register in plain words: where written, or an octave off on N of M notes."""
    judged = [r for r in rows if r["octave"] is not None]
    if not judged:
        return f"{track}: no written note could be heard on its attack, so its register can't be told"
    low, high = (sum(r["octave"] == k for r in judged) for k in (-1, 1))
    if max(low, high) < max(3, 0.25 * len(judged)):
        return f"{track} sounds where written ({len(judged) - low - high} of {len(judged)} notes heard in their octave)"
    k, n = (-1, low) if low >= high else (1, high)
    ex = next(r for r in judged if r["octave"] == k)
    return (f"{track} sounds one octave {'lower' if k < 0 else 'higher'} than written on {n} of {len(judged)} notes "
            f"(written {ex['written']}, heard {ex['heard']}): the instrument's samples, or your octave")
