"""The kinds of sound the door close-up needs (from eyes/door_events.json), as data:
which downloaded takes may hold them (words in the title), how to cut them, and the plain
description the sound-match model scores every cut against.

Each kind's description is scored against the other kinds' descriptions plus the sounds the old
pass used wrongly (whoosh, creak, clang, loud knock), so a cut wins only if it sounds more like
its own kind than like any of those."""
from pathlib import Path

TAKES_JSON = Path.home() / ".rostrum" / "assets" / "sounds" / "foley-h4" / "takes.json"

KINDS = {
    "ring_clink": {
        "text": "a small iron ring clinking against a metal plate, close and quiet",
        "words": ["knocker", "clink", "ring", "metal_hit", "anneau", "metal knocking", "metal_on_metal", "chain"],
        "not": ["knock on", "door closing", "door opening", "heavy", "keys", "squeak"],
        "mode": "hits", "max_s": 0.6, "per_file": 25},
    "padlock": {
        "text": "a small brass padlock rattling against an iron ring, close",
        "words": ["padlock", "lock rattle", "small chain", "small metal chain", "keys-ring", "safe misc"],
        "not": ["clang", "unlocking", "opening", "locking"],
        "mode": "hits", "max_s": 0.5, "per_file": 25},
    "metal_touch": {
        "text": "fingers gently touching and gripping a metal ring, very quiet, close",
        "words": ["key pickup", "keys in a hand", "handling", "grabbing keys", "key movement", "keymovement", "keychain"],
        "mode": "hits", "max_s": 0.4},
    "finger_tap": {
        "text": "a fingertip tapping on a wooden door, very soft, close",
        "words": ["finger", "tap", "wood_hit", "wood knock", "wood_knock", "soft_knock", "soft door knocks"],
        "not": ["woodecho"],
        "mode": "hits", "max_s": 0.3},
    "palm_pat": {
        "text": "a flat hand landing softly on a wooden door, a dull pat, close",
        "words": ["hand squeezing", "desk hit", "lay down", "hollow hit", "wood_hit", "light knock", "knocking once"],
        "mode": "hits", "max_s": 0.4},
    "palm_slide": {
        "text": "a hand sliding across a wooden surface, close",
        "words": ["sliding", "desliz", "scratching", "finger - slide", "rubbing hands"],
        "mode": "beds", "length": 0.35, "per_file": 4, "min_snr": 12},
    "sleeve": {
        "text": "a cotton jacket sleeve rustling softly, close up",
        "words": ["cloth", "rustle", "jacket", "coat", "clothing", "clothes", "ruffle", "fabric"],
        "not": ["floor cloth", "aggressive", "shake"],
        "mode": "beds", "length": 0.6, "per_file": 4, "min_snr": 12},
    "room": {
        "text": "the quiet tone of an empty indoor room",
        "words": ["room"],
        "mode": "beds", "length": 9.0, "per_file": 1, "min_snr": 0},
}

# The old pass's wrong sounds: every cut must sound more like its own kind than like these.
WRONG = ["a cinematic whoosh", "a wooden door creaking", "a heavy metal clang", "a loud knock on a door", "wind blowing"]


def contrast(kind: str) -> list[str]:
    return [k["text"] for n, k in KINDS.items() if n != kind] + WRONG
