"""low_end: how much of each track's energy sits under 150 Hz (a boom where the picture has none)."""

from .core import LOW_END_HZ, band_share, load, mono, name_of, num

FLAG_SHARE_PCT = 50.0       # more than this under 150 Hz is a low-heavy track


def low_end(src, flag_pct=FLAG_SHARE_PCT):
    """src: one wav path or {id: wav path}. Per track: low-end share (% of energy < 150 Hz) and,
    for context, sub-bass (< 60 Hz) share. Flags the tracks over `flag_pct`."""
    tracks = src if isinstance(src, dict) else {name_of(src): src}
    rows, flags = {}, []
    for k, p in tracks.items():
        y, sr = load(p)
        sh = band_share(mono(y), sr, [("low", 0, LOW_END_HZ), ("sub", 0, 60)])
        rows[k] = {"low_end_pct": num(100 * sh["low"], 1), "sub_pct": num(100 * sh["sub"], 1)}
        if 100 * sh["low"] > flag_pct:
            flags.append({"track": k, "detail": f"{100 * sh['low']:.0f}% of the energy is under {LOW_END_HZ:g} Hz"})
    return {"low_end_hz": LOW_END_HZ, "tracks": rows, "flags": flags,
            "note": "a fact, not a verdict: a flagged track is only wrong if the picture shows nothing heavy"}
