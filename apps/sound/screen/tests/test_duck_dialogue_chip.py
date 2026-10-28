"""A duck with no `under` (dips under every dialogue track) reads on its chip as what it dips under, never "Dips under "."""
from screensound.ducks import effective, strip_ducks


def test_chip_and_panel_show_the_dialogue_a_blank_duck_dips_under():
    music = {"id": "music", "ducks": [{"id": "music_duck_1", "under": []}]}
    tracks = [music, {"id": "vo", "role": "dialogue"}, {"id": "drums"}]
    chip = strip_ducks(music, tracks, lambda t: t["id"])["ducks"][0]["label"]
    assert chip == "Dips under vo"
    shown = effective(music["ducks"][0], "music", tracks)
    assert shown["under"] == ["vo"] and shown["voice"] is True
    alone = strip_ducks(music, [music, {"id": "drums"}], lambda t: t["id"])["ducks"][0]["label"]
    assert alone == "Dips under dialogue (none yet)"
