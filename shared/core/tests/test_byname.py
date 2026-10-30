"""Icons and Google Fonts by the names agents write in web code (rostrum_core.byname). No network: the font fetch is
served from a stand-in."""
from types import SimpleNamespace

import pytest

from rostrum_core.byname import (FontNeedsInternet, FontNotFound, IconNotFound, expand_icons, families_in_css,
                                 font_files, google_css_url, google_family, icon, icon_paths, icon_sets)
from rostrum_core.byname import fonts as fonts_mod
from rostrum_core.cache import Cache


def test_icons_by_every_name_agents_write():
    assert icon_sets() == {"lucide": "1.65.0", "tabler": "3.50.0"}
    lucide = icon("arrow-right")
    for name in ("lucide:arrow-right", "ArrowRight", "ArrowRightIcon", "LucideArrowRight", "i-lucide-arrow-right"):
        assert icon(name) == lucide
    assert icon("tabler:arrow-right") != lucide and icon("ti-arrow-right") == icon("tabler:arrow-right")
    assert icon("IconHeartFilled") == icon("tabler:heart-filled") and 'fill="currentColor"' in icon("tabler:heart-filled")
    assert icon("Trash2") == icon("trash-2")


def test_icon_colour_size_and_stroke_are_as_asked():
    svg = icon("heart", color="#ff0000", size=48, stroke_width=1.5)
    assert "currentColor" not in svg and 'stroke="#ff0000"' in svg
    assert 'width="48" height="48"' in svg and 'stroke-width="1.5"' in svg and 'viewBox="0 0 24 24"' in svg


def test_a_wrong_icon_name_answers_with_the_five_nearest():
    with pytest.raises(IconNotFound) as e:
        icon("arow-rigth")
    assert "nearest: arrow-right" in str(e.value) and str(e.value).count(",") == 4
    with pytest.raises(IconNotFound, match="the sets are lucide, tabler"):
        icon("phosphor:x")


def test_icon_paths_turn_every_element_into_path_data():
    parts = icon_paths("lucide:circle-check")            # a circle and a path
    assert len(parts) == 2 and parts[0]["d"].startswith("M2 12A10 10") and all(p["stroke"] and not p["fill"] for p in parts)
    filled = icon_paths("tabler:heart-filled")              # Tabler's invisible frame is left out
    assert len(filled) == 1 and filled[0]["fill"] and not filled[0]["stroke"]
    assert any("A" in p["d"] for p in icon_paths("lucide:square"))     # a rect with round corners


def test_icon_elements_in_html_become_inline_svg():
    page = '<p>Go <i data-lucide="arrow-right" class="big" style="color: #fff" width="56"></i> <i class="ti ti-heart x"></i></p>'
    out = expand_icons(page)
    assert "<i" not in out and out.count("<svg") == 2
    assert 'class="big"' in out and 'width="56"' in out and 'stroke="#fff"' in out and 'class="x"' in out
    assert expand_icons('<iconify-icon icon="tabler:heart"></iconify-icon>').startswith("<svg")
    assert expand_icons("<i>plain italics</i>") == "<i>plain italics</i>"


def test_google_font_names_as_agents_write_them():
    assert google_family("Playfair Display") == "Playfair Display"
    for spelt in ("playfair display", "Playfair+Display", "playfair-display", "'Playfair Display'"):
        assert google_family(spelt) == "Playfair Display"
    assert google_family("Helvetica") is None
    with pytest.raises(FontNotFound) as e:
        font_files("Interr")
    assert "nearest: Inter" in str(e.value) and str(e.value).count(",") == 4


def test_css_asks_for_families_weights_and_italics():
    url = "https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;1,700&family=Playfair+Display:wght@700&display=swap"
    assert google_css_url(url) == {"Inter": {"weights": {400.0, 700.0}, "italic": None},
                                   "Playfair Display": {"weights": {700.0}, "italic": False}}
    assert google_css_url("https://fonts.googleapis.com/css?family=Lato:400,700i")["Lato"] == {"weights": {400.0, 700.0}, "italic": None}
    css = f'@import url("{url}"); h1 {{ font-family: "Bebas Neue", sans-serif }} p {{ font-family: Georgia, serif }}'
    assert set(families_in_css(css)) == {"Inter", "Playfair Display", "Bebas Neue"}


META = '''name: "Lato"
license: "OFL"
fonts {
  name: "Lato"
  style: "normal"
  weight: 400
  filename: "Lato-Regular.ttf"
}
fonts {
  name: "Lato"
  style: "italic"
  weight: 700
  filename: "Lato-BoldItalic.ttf"
}
fonts {
  name: "Lato"
  style: "normal"
  weight: 700
  filename: "Lato-Bold.ttf"
}
'''


@pytest.fixture
def served(tmp_path, monkeypatch):
    """The shared cache in tmp_path, and the network replaced by these files (`offline`: unreachable)."""
    files = {"METADATA.pb": META.encode(), "Lato-Regular.ttf": b"r", "Lato-Bold.ttf": b"b", "Lato-BoldItalic.ttf": b"bi"}
    net = SimpleNamespace(asked=[], offline=False)

    def get(url):
        if net.offline:
            raise OSError("could not reach raw.githubusercontent.com: offline")
        net.asked.append(url)
        return files[url.rsplit("/", 1)[1]]
    monkeypatch.setattr(fonts_mod, "CACHE", Cache(tmp_path))
    monkeypatch.setattr(fonts_mod.net, "get", get)
    return net


def test_a_family_is_fetched_once_and_kept(served):
    first = font_files("lato", weights=[700], italic=False)
    assert [p.name for p in first] == ["Lato-Bold.ttf"] and first[0].read_bytes() == b"b"
    assert all("/ofl/lato/" in u for u in served.asked) and len(served.asked) == 2    # METADATA.pb and the one face
    served.offline = True
    assert font_files("Lato", weights=[700], italic=False) == first          # kept: no network needed again


def test_weights_pick_as_css_does_and_offline_says_it_needs_the_internet_once(served):
    assert [p.name for p in font_files("Lato", weights=[500], italic=False)] == ["Lato-Regular.ttf"]   # 500 -> 400 below
    assert [p.name for p in font_files("Lato", weights=[600], italic=False)] == ["Lato-Bold.ttf"]      # above 500: heavier
    assert [p.name for p in font_files("Lato", italic=True)] == ["Lato-BoldItalic.ttf"]
    served.offline = True
    with pytest.raises(FontNeedsInternet, match="fetched from the internet the first time"):
        font_files("Roboto")
