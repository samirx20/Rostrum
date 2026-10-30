"""A markup film script's print comes back in the film's notes (never on the server's channel); exit() keeps the film."""
from rostrum2d.markup import runner


def test_print_comes_back_as_notes(tmp_path):
    p = runner.save(tmp_path, "f", "print('frames', 24)\nfilm = Film(duration=1)\n")
    assert "print: frames 24" in runner.load(p, tmp_path).notes
