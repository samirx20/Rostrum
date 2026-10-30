"""A markup film's `random` is seeded: a re-run draws the same film, and a draw inside scene(t) is the same at the same t
whatever order frames are drawn in (looks, export, blur samples)."""
from rostrum2d.markup import runner

CODE = """
xs = [random.uniform(0, 1000) for _ in range(3)]
film = Film(duration=2)
film.scene(lambda t: f'<div id="a" style="left:{xs[0]:.3f}px; top:{random.uniform(0, 500):.3f}px"></div>')
"""


def _film(tmp_path, code=CODE):
    return runner.load(runner.save(tmp_path, "f", code), tmp_path)


def test_rerun_draws_the_same_film(tmp_path):
    a, b = _film(tmp_path), _film(tmp_path)
    assert a.markup(0.5) == b.markup(0.5)


def test_scene_draws_fixed_per_moment(tmp_path):
    f = _film(tmp_path)
    first = f.markup(1.0)
    f.markup(0.2), f.markup(1.5)
    assert f.markup(1.0) == first
    assert f.markup(0.2) != first


def test_scripts_own_seed_counts(tmp_path):
    a, b = _film(tmp_path), _film(tmp_path, "random.seed(9)\n" + CODE)
    assert a.markup(0.5) != b.markup(0.5)
