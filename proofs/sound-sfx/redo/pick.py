"""Choosing a cut for each cue: the sound-match score decides WHAT it is, measured facts decide
whether it can sit on the frame (sharp start, long enough, bright or dull enough), and no cut is
used twice within REUSE_GAP_S seconds, and consecutive cues of one kind come from different recordings.

Why not the score alone: the eval (README) shows the model can't hear force, can't tell a whoosh
from cloth, and mixes up small metal / glass / wood hits. So each kind also has fact rules."""

# kind -> (which pool kind to draw from, fact rules)
RULES = {
    # metal capped at 8 kHz: brighter cuts are tinkly small chains, not an iron ring or a brass padlock body
    "ring_clink": ("ring_clink", {"attack_ms_max": 20, "centroid_min": 1800, "centroid_max": 8000}),
    "padlock": ("padlock", {"attack_ms_max": 20, "centroid_min": 1500, "centroid_max": 8000}),
    # the model scores nothing as "fingers touching a ring" (best 0.06): use the quietest-sounding
    # ring cuts, short, played very low
    "metal_touch": ("ring_clink", {"attack_ms_max": 30, "centroid_min": 1500, "centroid_max": 8000}),
    "finger_tap": ("finger_tap", {"attack_ms_max": 15, "centroid_max": 3000}),
    "palm_pat": ("palm_pat", {"attack_ms_max": 15, "centroid_max": 2500}),
    "palm_slide": ("palm_slide", {}),
    "sleeve": ("sleeve", {"centroid_max": 5000}),
}
MIN_PROB = 0.5
REUSE_GAP_S = 3.0  # a small rattle may come back, but not within 3 s of itself


def ok(c, rules, need_s):
    return (c["length"] >= need_s
            and c["attack_ms"] <= rules.get("attack_ms_max", 1e9)
            and rules.get("centroid_min", 0) <= c["centroid_hz"] <= rules.get("centroid_max", 1e9))


class Picker:
    def __init__(self, pool):
        self.pool, self.used, self.last_file = pool, {}, {}

    def pick(self, kind, need_s, at):
        src, rules = RULES[kind]
        cands = [c for c in self.pool if c["kind"] == src and ok(c, rules, need_s)
                 and at - self.used.get((c["path"], c["offset"]), -1e9) >= REUSE_GAP_S]
        strong = [c for c in cands if c["prob"] >= MIN_PROB] or cands
        if not strong:
            raise RuntimeError(f'no cut left for "{kind}" (needs {need_s} s, rules {rules})')
        fresh = [c for c in strong if c["path"] != self.last_file.get(kind)] or strong
        # an unused cut first, then the best score
        best = max(fresh, key=lambda c: ((c["path"], c["offset"]) not in self.used, c["prob"], c["cosine"]))
        self.used[(best["path"], best["offset"])] = at
        self.last_file[kind] = best["path"]
        return best
