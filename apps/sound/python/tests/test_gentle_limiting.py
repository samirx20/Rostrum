"""Gentle limiting (master `gentle`, `maxLimit`): a fresh song at the default volumes, made loud, peaks with at most
2 dB of limiting (the whole mix is turned down instead); a saved song's master keeps limiting as it did."""
from rostrum_sound import run_source
from rostrum_sound.compile import compile
from rostrum_sound.doc import KIND
from rostrum_sound.engine import Engine

SONG = """tempo(110); beats_per_bar(4); length(bar(5)); key("A minor")
prog = ["Am", "F", "C", "G"]
d = track("drums", kit="studio"); bs = track("bass", builtIn="bass"); pn = track("piano", builtIn="piano")
write(d, drum_grid({"kick": "X...x..xX...x...", "snare": "....X.......X...", "hat": "x.x.x.x.x.x.x.x."}, bars=4, crash=True), at=bar(1))
write(bs, bass_line(prog, pattern="R.R.R.R.R.R.R.R5", octave=1, per=4), at=bar(1))
write(pn, comp(prog, rhythm="X.x.x.x.X.x.x.xx", vel=0.7, range=("C3", "E5")), at=bar(1))
master(loudness=-14, truePeak=-1)
"""


def test_a_fresh_song_made_loud_peaks_with_at_most_2_db_of_limiting(tmp_path):
    with Engine() as e:
        got = e.request("render", schedule=compile(run_source(SONG, "fresh.py")), out=str(tmp_path / "mix.wav"))
    m = got["master"]
    assert m["limiterMaxReductionDb"] <= 2.1 and m["heldDb"] > 0, m        # this song needs ~4.5 dB without it


def test_a_song_saved_before_gentle_limiting_limits_as_before():
    data, _ = KIND.migrate({"id": "root", "type": "doc", "tempo": 120, "tracks": [], "master": [
        {"id": "master", "type": "master", "normalize": True, "loudness": -14, "truePeak": -1}]}, 4)
    assert "maxLimit" not in compile(data)["master"]


def test_a_song_saved_before_ring_out_and_even_kits_ends_and_drums_as_before():
    data, _ = KIND.migrate({"id": "root", "type": "doc", "tempo": 120, "length": 4, "tracks": [
        {"id": "d", "type": "track", "instrument": "kit", "kit": "studio", "hits": []}], "master": []}, 5)
    s = compile(data)
    assert "ringOut" not in s and s["master"]["fadeOut"] == 0.1 and s["tracks"][0]["instrument"] == {"kit": "studio"}, s
