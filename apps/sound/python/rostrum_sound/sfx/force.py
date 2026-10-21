"""Level from force: the agent writes a force word on an event; the app turns it into a peak level.

The table is data (one place). Levels are the peak of the cut before mastering, in dBFS; a kind's
offset trims it (a palm pat reads louder than a fingertip at the same force). The whole mix's gain
stays separate."""

FORCES = ["touch", "very soft", "soft", "medium", "hard", "very hard"]

# force word -> peak dBFS. "touch", "very soft" and "soft" are the door proof's measured values.
FORCE_PEAK_DB = {"touch": -38.0, "very soft": -30.0, "soft": -20.0,
                 "medium": -12.0, "hard": -6.0, "very hard": -2.0}

# kind -> dB added to the force level (from the proof's door close-up).
KIND_OFFSET_DB = {"ring_clink": 0.0, "padlock": 0.0, "metal_touch": 0.0, "finger_tap": 0.0,
                  "palm_pat": -6.0, "palm_slide": -10.0, "sleeve": -10.0}


def peak_for(kind, force):
    """Target peak (dBFS) for a `kind` of sound at a `force` word. An unknown force or kind
    raises (an unknown kind has offset 0 only when `kind` is None)."""
    if force not in FORCE_PEAK_DB:
        raise ValueError(f"unknown force '{force}'; use one of {FORCES}")
    if kind is not None and kind not in KIND_OFFSET_DB:
        raise ValueError(f"unknown kind '{kind}'; known kinds {sorted(KIND_OFFSET_DB)} (or None for no offset)")
    return FORCE_PEAK_DB[force] + (KIND_OFFSET_DB[kind] if kind is not None else 0.0)


def gain_to_peak(cut_peak_db, target_db):
    """Linear gain that brings a cut whose peak is `cut_peak_db` to `target_db`."""
    return 10 ** ((target_db - cut_peak_db) / 20)
