"""Level matching (doc/preset_level.py): an old song sounds exactly as before; every built-in has a measured gain."""
import copy

from rostrum_sound import names
from rostrum_sound.compile import compile
from rostrum_sound.doc import KIND, preset_level

LANE = [[0, 0.5], [4, 1.2]]
OLD = {"id": "root", "type": "doc", "tempo": 120, "tracks": [
    {"id": "keys", "type": "track", "instrument": "builtIn", "builtIn": "feltPiano", "volume": 0.9,
     "automation": [{"id": "a", "type": "automation", "lane": "volume", "points": LANE}]},
    {"id": "kit", "type": "track", "instrument": "kit", "kit": "synth", "volume": 0.8},
    {"id": "vox", "type": "track", "instrument": "sfz", "sfz": "x.sfz", "volume": 0.7}], "master": []}


def test_a_song_saved_before_level_matching_gets_the_engine_the_same_volumes():
    data, labels = KIND.migrate(copy.deepcopy(OLD), 1)
    assert labels and data["tracks"][2]["volume"] == 0.7     # a sampled track has no gain; the others are offset by the new table (none yet for the recorded names)
    sent = {t["id"]: t for t in compile(data)["tracks"]}
    assert all(abs(sent[t["id"]]["volume"] - t["volume"]) < 1e-4 for t in OLD["tracks"])
    assert all(abs(a[1] - b[1]) < 1e-4 for a, b in zip(sent["keys"]["automation"]["volume"], LANE))


def test_the_classic_voices_and_kit_keep_their_measured_gains():
    have = preset_level.presets()
    assert all(f"builtIn:{n}" in have for n in names.BUILT_IN_GROUPS["Classic (synthesized)"]) and "kit:classic" in have


def test_every_plain_name_and_kit_has_a_measured_gain():
    have = preset_level.presets()
    assert all(f"builtIn:{n}" in have for g in names.BUILT_IN_GROUPS.values() for n in g) and {"kit:drums", "kit:studio"} <= set(have)


def test_a_song_saved_before_the_starting_balance_sounds_as_before():
    old = {"id": "root", "type": "doc", "tempo": 120, "master": [], "tracks": [
        {"id": "kit", "type": "track", "instrument": "kit", "kit": "studio", "volume": 1.0},
        {"id": "br", "type": "track", "instrument": "builtIn", "builtIn": "brass", "volume": 0.8}]}
    data, _ = KIND.migrate(copy.deepcopy(old), 3)
    sent = {t["id"]: t["volume"] for t in compile(data)["tracks"]}
    heard = {t["id"]: t["volume"] * preset_level.gain(t, preset_level.FORMAT3) for t in old["tracks"]}
    assert all(abs(sent[k] - heard[k]) < 1e-3 for k in heard)
    assert data["tracks"][0]["volume"] > 1.0          # the new table is lower, so the saved volume rises to keep the sound


def test_a_song_saved_before_the_three_phrase_levels_sounds_as_before():
    """Format 8 -> 9 re-measured every starting level; a saved song's tracks and volume lanes keep their sound."""
    old = {"id": "root", "type": "doc", "tempo": 120, "master": [], "tracks": [
        {"id": "db", "type": "track", "instrument": "builtIn", "builtIn": "basses", "volume": 0.6},
        {"id": "br", "type": "track", "instrument": "builtIn", "builtIn": "brass", "volume": 0.8,
         "automation": [{"id": "a", "type": "automation", "lane": "volume", "points": LANE}]}]}
    data, labels = KIND.migrate(copy.deepcopy(old), 8)
    assert any("Starting levels re-measured" in w for w in labels)
    sent = {t["id"]: t for t in compile(data)["tracks"]}
    for t in old["tracks"]:
        assert abs(sent[t["id"]]["volume"] - t["volume"] * preset_level.gain(t, preset_level.FORMAT8)) < 1e-3
    g = preset_level.gain(old["tracks"][1], preset_level.FORMAT8)
    assert all(abs(a[1] - b[1] * g) < 1e-3 for a, b in zip(sent["br"]["automation"]["volume"], LANE))
