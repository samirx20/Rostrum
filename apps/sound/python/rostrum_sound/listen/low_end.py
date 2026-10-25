"""low_end: how much of each track's energy sits under 150 Hz (a boom where the picture has none), and in the low mids
(150–500 Hz, where several parts piling up sound muddy), per track and for the whole mix."""

from .core import LOW_END_HZ, band_share, load, mono, name_of, num
from .memo import remembered

FLAG_SHARE_PCT = 50.0       # more than this under 150 Hz is a low-heavy track
LOW_ROLE_FLAG_PCT = 90.0    # a bass or a kick lives down there: only nearly all of its energy under 150 Hz (no body, no attack) is a boom
LOW_MID_HZ = (LOW_END_HZ, 500.0)


@remembered
def low_end(src, flag_pct=None, mix=None, low_roles=()):
    """src: one wav path or {id: wav path}; mix: the mix's wav, measured too (row "mix"). Per track: low-end share
    (% of energy < 150 Hz), sub-bass (< 60 Hz) and low-mid (150–500 Hz) share. Flags the tracks over `flag_pct` under 150 Hz (default 50 %; 90 % for the tracks in `low_roles`: a bass or a kick is
    meant to live there, so only a part with nothing above the low end counts as boomy)."""
    tracks = src if isinstance(src, dict) else {name_of(src): src}
    tracks = {**tracks, "mix": mix} if mix else tracks
    rows, flags = {}, []
    for k, p in tracks.items():
        y, sr = load(p)
        sh = band_share(mono(y), sr, [("low", 0, LOW_END_HZ), ("sub", 0, 60), ("lowmid", *LOW_MID_HZ)])
        rows[k] = {"low_end_pct": num(100 * sh["low"], 1), "sub_pct": num(100 * sh["sub"], 1), "low_mid_pct": num(100 * sh["lowmid"], 1)}
        limit = flag_pct if flag_pct is not None else LOW_ROLE_FLAG_PCT if k in low_roles else FLAG_SHARE_PCT
        if 100 * sh["low"] > limit and not (mix and k == "mix"):
            flags.append({"track": k, "limit_pct": limit, "detail": f"{100 * sh['low']:.0f}% of the energy is under {LOW_END_HZ:g} Hz"
                          + (" (a low part: flagged only over %g%%)" % limit if k in low_roles else "")})
    return {"low_end_hz": LOW_END_HZ, "tracks": rows, "flags": flags,
            "note": "facts, not verdicts: a flagged track is only wrong if the picture shows nothing heavy; low_mid_pct is the "
                    "share in 150–500 Hz (compare the mix's before and after a change: several parts piling up there sound muddy)"}
