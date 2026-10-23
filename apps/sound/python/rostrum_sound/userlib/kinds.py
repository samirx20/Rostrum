"""What kind of sound it is (whoosh, click, hit, impact, riser, ui, beep, ambience, foley, drone, glitch), from three
kinds of evidence, strongest first:

  UCS category   a file named "WHSHSwsh_..." is a whoosh, said by the library itself       (weight 4)
  words          its file name (3), its metadata description (2), its folders (1)
  shape          what was measured: a 5 ms attack on a 0.1 s sound is a click, a long rise to a late peak is a
                 riser, a slow attack to a middle peak is a whoosh, a long flat sound is an ambience  (1)

Every kind with some evidence is kept (`kinds`, strongest first), so a short UI "select" counts as both `ui` and
`click`, and `kind` is the strongest. Facts, not taste: this only sorts, it never judges a sound good or bad.
"""
from __future__ import annotations

KINDS = ("whoosh", "riser", "impact", "hit", "click", "ui", "beep", "ambience", "foley", "drone", "glitch")
WORDS = {
    "whoosh": "whoosh woosh swoosh swish swirl whip swipe swing whizz zip passby flyby whooshes swooshes swishes "
              "transition transitions pass_by fly_by",
    "riser": "riser risers rise rising uplifter build buildup swell reverse suck sweep",
    "impact": "impact impacts boom booms slam slams braam explosion crash smash thud",
    "hit": "hit hits punch knock thump strike bang tap stab",
    "click": "click clicks button buttons switch switches press tick ticks toggle latch knob snap clack key keys "
             "shutter flash",
    "ui": "ui interface menu notification select back error confirm cancel scroll alert accent access denied "
          "querry query hover",
    "beep": "beep beeps bleep bleeps blip blop blops chime ding marimba tone tones",
    "ambience": "ambience ambiences ambient amb atmos atmosphere roomtone room_tone background bed loop",
    "foley": "foley footstep footsteps cloth leather paper handling rustle door drawer glass squeak",
    "drone": "drone drones pad hum",
    "glitch": "glitch glitches corrupt data chatter digital magic",
}
TOKEN = {w.replace("_", " "): k for k, ws in WORDS.items() for w in ws.split()}
UCS = {"WHSH": "whoosh", "SWSH": "whoosh", "UI": "ui", "BEEP": "beep", "AMB": "ambience", "ROOM": "ambience",
       "FOLY": "foley", "FEET": "foley", "CLOTH": "foley", "DOOR": "foley", "EXPL": "impact", "IMPT": "impact",
       "SWTCH": "click", "MECH": "click", "COMP": "glitch", "SCI": "glitch"}
UCS_SUB = {"Click": "click", "Beep": "beep", "Rise": "riser", "Risr": "riser", "Impt": "impact", "Boom": "impact",
           "Hit": "hit", "Whsh": "whoosh", "Swsh": "whoosh", "Drn": "drone", "Drone": "drone", "Glitch": "glitch"}
# What the Library's kind filter offers, real and musical sounds first (PURPOSE.md). Whoosh and glitch are still
# sorted (facts), never offered: a person's own whoosh is found by its name.
OFFERED = ("drone", "beep", "ambience", "foley", "hit", "impact", "click", "ui")
SOURCES = (("name", 3.0), ("meta", 2.0), ("folder", 1.0))


def _from_words(text: str) -> set[str]:
    ws = text.split()
    pairs = [f"{a} {b}" for a, b in zip(ws, ws[1:])]
    return {TOKEN[w] for w in ws + pairs if w in TOKEN}


def _from_ucs(cat: str) -> set[str]:
    out = set()
    for prefix, k in UCS.items():
        if cat.startswith(prefix):
            out.add(UCS_SUB.get(cat[len(prefix):], k))
    return out


def named(about: dict) -> set[str]:
    """The kinds its name, metadata and UCS category say (no measuring)."""
    out = _from_ucs(about.get("ucs", ""))
    for field, _ in SOURCES:
        out |= _from_words(about.get(field, ""))
    return out


def from_shape(m: dict) -> str | None:
    """The kind the measurements alone suggest, or None when they say nothing clear."""
    length, attack, peak = m["seconds"], m["attack_ms"], m["peak_frac"]
    if length >= 6 and m.get("crest_db", 99) < 12:
        return "ambience"
    if length > 1.2 and peak > 0.65:
        return "riser"
    if attack < 15 and length < 0.35:
        return "click"
    if attack < 20 and peak < 0.2:
        return "impact" if length > 1.0 and m["centroid_hz"] < 1500 else "hit"
    if attack > 40 and 0.12 <= peak <= 0.75:
        return "whoosh"
    return None


def classify(about: dict, measured: dict) -> dict:
    """{"kind": strongest, "kinds": every kind with evidence, strongest first}. `about` = meta.about(...),
    `measured` = measure.measure(...)."""
    score: dict[str, float] = {}
    for k in _from_ucs(about.get("ucs", "")):
        score[k] = score.get(k, 0) + 4
    for field, w in SOURCES:
        for k in _from_words(about.get(field, "")):
            score[k] = score.get(k, 0) + w
    shaped = from_shape(measured)
    if shaped:
        score[shaped] = score.get(shaped, 0) + 1
    ranked = sorted(score, key=lambda k: (-score[k], KINDS.index(k)))
    return {"kind": ranked[0] if ranked else "other", "kinds": ranked or ["other"]}
