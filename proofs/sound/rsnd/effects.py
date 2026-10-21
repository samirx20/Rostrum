"""Insert effects the engine runs (schedule/effect.rs), as plain dicts with every default filled in.

A parameter marked "number or envelope" takes a value or a list of (seconds, value) points.
Put them on a track (`track.effect(...)`) or on the master (`session.effect(...)`).
"""

SPACES = ("dry", "room", "hall", "cathedral", "shimmer", "freeverb.room", "freeverb.hall", "freeverb.cathedral")
# fx/eq.rs: any other name would play as a peak, so names are checked here.
EQ_SHAPES = ("lowshelf", "highshelf", "peak", "lowpass", "highpass", "notch")


def space(name: str) -> str:
    """A reverb space the engine knows; anything else fails here, not as a silent room."""
    if name not in SPACES:
        raise ValueError(f'reverb space "{name}" is not one of {SPACES}')
    return name


def _p(v):
    """A number, or an envelope [(seconds, value), ...]."""
    if isinstance(v, (int, float)):
        return float(v)
    return [[float(t), float(x)] for t, x in v]


def eq(*bands):
    """eq(("lowshelf", 120, -3, 0.7), ("peak", 3000, 2, 1.0)): (shape, Hz, dB, Q) per band."""
    out = []
    for shape, f, gain, q in bands:
        if shape not in EQ_SHAPES:
            raise ValueError(f'EQ shape "{shape}" is not one of {EQ_SHAPES}')
        out.append({"shape": shape, "freq": _p(f), "gain": _p(gain), "q": _p(q)})
    return {"type": "eq", "bands": out}


def compressor(threshold=-18, ratio=3, attack=0.01, release=0.15, makeup=0, knee=6):
    """Threshold and makeup in dB, attack and release in seconds, knee in dB."""
    return {"type": "compressor", "threshold": _p(threshold), "ratio": _p(ratio), "attack": float(attack),
            "release": float(release), "makeup": _p(makeup), "knee": float(knee)}


def reverb(space_name="hall", mix=0.25, decay=None, damping=None, size=None):
    """decay (s), damping and size (0 … 1) tune the freeverb.* spaces only."""
    return {"type": "reverb", "space": space(space_name), "mix": _p(mix), "decay": decay, "damping": damping, "size": size}


def delay(time=0.375, feedback=0.35, mix=0.2, ping_pong=False, damp=0.3):
    return {"type": "delay", "time": float(time), "feedback": _p(feedback), "mix": _p(mix), "pingPong": bool(ping_pong), "damp": float(damp)}


def saturate(drive=0.3, mix=1.0):
    return {"type": "saturate", "drive": _p(drive), "mix": _p(mix)}


def tape(wow=0.2, flutter=0.2, age=0.2):
    return {"type": "tape", "wow": _p(wow), "flutter": _p(flutter), "age": _p(age)}


def limiter(ceiling=-1.0, release=0.1):
    return {"type": "limiter", "ceiling": float(ceiling), "release": float(release)}


def width(amount=1.0, mono_below=120.0):
    """0 mono, 1 as it is, 2 wider; below `mono_below` Hz kept as it is."""
    return {"type": "width", "width": _p(amount), "monoBelow": float(mono_below)}


def gate(threshold=-45, ratio=4, range=30, attack=0.002, hold=0.05, release=0.12):
    return {"type": "gate", "threshold": float(threshold), "ratio": float(ratio), "range": float(range),
            "attack": float(attack), "hold": float(hold), "release": float(release)}
