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
