"""Two runs of one project at once write the same cached file: both succeed, the file is whole, a real failure is loud."""
import threading

import pytest

from rostrum_core import RostrumError
from rostrum_core.cache import put_file


def test_two_writers_of_one_key_both_succeed(tmp_path):
    out = tmp_path / "mix.wav"
    both_inside = threading.Barrier(2)

    def make(tmp):
        both_inside.wait(timeout=5)                 # both are writing at the same moment
        tmp.write_bytes(b"RIFF" + b"x" * 100_000)

    results, errors = [], []

    def run():
        try:
            results.append(put_file(out, make, "soundtrack"))
        except Exception as e:                      # noqa: BLE001 — the test reports any failure
            errors.append(e)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and results == [out, out]
    assert out.read_bytes() == b"RIFF" + b"x" * 100_000
    assert not list((tmp_path / ".writing").iterdir())          # no temporary file left behind

    with pytest.raises(RostrumError, match="wrote no file"):     # an engine that writes nothing is still loud
        put_file(tmp_path / "other.wav", lambda tmp: None, "soundtrack")


def test_files_beside_the_mix_move_with_it(tmp_path):
    """The engine writes `<mix>.levels.json` beside the mix; the player refuses a mix without it (no meters)."""
    out, side = tmp_path / "mix.wav", tmp_path / "mix.levels.json"

    def make(tmp):
        tmp.write_bytes(b"RIFF" + b"x" * 100)
        tmp.with_suffix(".levels.json").write_text("{}")

    put_file(out, make, "soundtrack", beside=(".levels.json",))
    assert out.is_file() and side.is_file() and not list((tmp_path / ".writing").iterdir())
    side.unlink()                                               # an older entry made without it is made again
    put_file(out, make, "soundtrack", beside=(".levels.json",))
    assert side.is_file()
    with pytest.raises(RostrumError, match="wrote no .levels.json"):
        put_file(tmp_path / "b.wav", lambda tmp: tmp.write_bytes(b"x"), "soundtrack", beside=(".levels.json",))
