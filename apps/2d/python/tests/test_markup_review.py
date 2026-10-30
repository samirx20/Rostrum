"""Markup review notes (review.notes): what an agent never noticed in its own frames is said with its times: text cut
by the frame's edge during a camera push, a pointer resting on a label, a frame that is almost all background."""
import pytest

from rostrum2d import settings
from rostrum2d.markup import Film, render, review

pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")
TIMES = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    s = render.Session(tmp_path_factory.mktemp("review") / "engine.log")
    yield s
    s.close()


def _film():
    film = Film(480, 270, fps=30, duration=6, background="#0d0f14")
    film.css(".t { position: absolute; margin: 0; font: 600 24px Inter; color: #fff }")
    film.scene('<h1 id="headline" class="t" style="left: 60px; top: 40px; font-size: 44px">Quarterly results</h1>'
               '<div id="total" class="t" style="left: 280px; top: 190px">Total 4,210</div>')
    film.overlay('<div id="pointer" style="position: absolute; left: 20px; top: 20px; width: 24px; height: 24px; '
                 'border-radius: 12px; background: #ff7a59"></div>')
    film.key("#pointer", left={0: "20px", 2: "300px"}, top={0: "20px", 2: "192px"})
    film.camera(zoom={0: 1, 3: 1, 4: 1.8, 6: 1.8}, x={0: 240, 3: 240, 4: 300})       # a push that cuts the headline
    for i in ("headline", "total", "pointer"):
        film.key("#" + i, opacity={0: 1, 4.9: 1, 5: 0})                                  # then an empty frame
    return film


def test_edge_cut_cover_and_empty_frame_are_said_with_their_times(session):
    out = review.notes(session, _film(), TIMES)
    said = "\n".join(out)
    assert any(n.startswith("#headline is cut by the left") and "to 4.5 s" in n for n in out), said
    assert any(n.startswith("#pointer sits on #total") and "to 2.5 s" in n for n in out), said
    assert any("at 5.5 s is almost empty" in n and "background colour" in n for n in out), said
    assert not any("#headline" in n for n in out if n.startswith("#pointer")), said    # it passes clear of it
    assert len(out) <= review.MAX_LINES


def test_only_the_requests_copy_is_tagged():
    out = render.tag_layers('<div id="a"><svg><circle id=\'c\' r="2"/></svg><p data-id="x">hi</p></div>')
    assert 'id="a" data-layer-id="a"' in out and "id='c' data-layer-id='c'" in out and out.count("data-layer-id") == 2
    assert render.tag_layers(out) == out


def test_text_without_an_id_is_named_by_its_words():
    out, labels = render.tag_texts('<div class="mono">CH 02 / ACQUIRE</div><svg><text x="1">'
                                   '<textPath href="#o">orbit words</textPath></text><g><rect/></g></svg><p id="k">kept</p>')
    assert list(labels.values()) == ["CH 02 / ACQUIRE", "orbit words"]
    assert 'class="mono" id="rostrum-text-0" data-layer-id="rostrum-text-0">' in out and 'id="k">kept' in out


def test_parked_inside_a_clipping_parent_is_not_cut(session):
    film = Film(480, 270, fps=30, duration=1, background="#0d0f14")
    film.scene('<div style="position:absolute; left:40px; top:20px; width:300px; height:200px; overflow:hidden">'
               '<div id="sheet" style="position:absolute; left:0; top:400px; font: 24px Inter; color:#fff">Parked</div></div>'
               '<div style="position:absolute; left:400px; top:-12px; font: 600 30px Inter; color:#fff">CH 02</div>')
    out = review.notes(session, film, [0.5])
    said = "\n".join(out)
    assert not any("#sheet" in n for n in out), said
    assert any(n.startswith('the text "CH 02" is cut by the top edge') for n in out), said
