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
    assert labels and data["tracks"][0]["volume"] != 0.9 and data["tracks"][2]["volume"] == 0.7     # a sampled track has no gain
    sent = {t["id"]: t for t in compile(data)["tracks"]}
    assert all(abs(sent[t["id"]]["volume"] - t["volume"]) < 1e-4 for t in OLD["tracks"])
    assert all(abs(a[1] - b[1]) < 1e-4 for a, b in zip(sent["keys"]["automation"]["volume"], LANE))


def test_every_built_in_and_the_kit_has_a_measured_gain():
    have = preset_level.presets()
    assert all(f"builtIn:{n}" in have for n in names.BUILT_INS) and "kit:synth" in have
