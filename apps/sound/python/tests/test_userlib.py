"""The user's sound library: indexed once by content (an unchanged folder is read back from the cache, a new file
re-reads only itself), and search filters by kind and shape."""
import numpy as np
import soundfile as sf

from rostrum_sound.userlib import index
from rostrum_sound.userlib.search import search as find

SR = 48000


def _click(seconds=0.08):
    t = np.arange(int(SR * seconds)) / SR
    return (np.sin(2 * np.pi * 5000 * t) * np.exp(-t * 80)).astype(np.float32)


def _whoosh(seconds=0.5):
    n = int(SR * seconds)
    env = np.sin(np.linspace(0, np.pi, n)) ** 2                    # slow swell to a middle peak
    return (np.random.default_rng(1).standard_normal(n) * env * 0.3).astype(np.float32)


def _library(folder):
    folder.mkdir()
    sf.write(folder / "ui_click_01.wav", np.concatenate([np.zeros(2400, np.float32), _click()]), SR)
    sf.write(folder / "whoosh_fast.wav", _whoosh(), SR)


def test_index_is_cached_by_content(tmp_path):
    lib, cache = tmp_path / "lib", tmp_path / "cache"
    _library(lib)
    first = index.index_folder(lib, cache)
    assert not first["from_cache"] and first["files_from_cache"] == 0 and len(first["sounds"]) == 2
    index.forget()
    again = index.index_folder(lib, cache)
    assert again["from_cache"] and again["sounds"] == first["sounds"]
    sf.write(lib / "zz_click_02.wav", _click(0.05), SR)              # one new file: only it is analysed
    grown = index.index_folder(lib, cache)
    assert not grown["from_cache"] and grown["files_from_cache"] == 2 and len(grown["sounds"]) == 3


def test_search_filters_by_kind_and_shape(tmp_path):
    lib = tmp_path / "lib"
    _library(lib)
    sounds = index.index_folder(lib, tmp_path / "cache")["sounds"]
    names = lambda r: [s["path"].rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for s in r["sounds"]]  # noqa: E731
    assert names(find(kind="click", sounds=sounds)) == ["ui_click_01.wav"]
    assert names(find(kind="whoosh", length="short", sounds=sounds)) == ["whoosh_fast.wav"]
    assert names(find(kind="whoosh", length="long", sounds=sounds)) == []
    assert names(find(seconds=[None, 0.2], sounds=sounds)) == ["ui_click_01.wav"]
    assert names(find(attack="sharp", brightness="bright", sounds=sounds)) == ["ui_click_01.wav"]
    click = find(kind="click", sounds=sounds)["sounds"][0]
    assert abs(click["start"] - 0.05) < 0.01                         # the silence before it is trimmed
