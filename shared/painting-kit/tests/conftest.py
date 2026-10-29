"""The kit's tests keep what they paint on disk (kept_disk.py) in a cache of their own: in the person's cache a second run
found the drawings of the first already painted, and a test that counts what it stamps saw nothing stamped."""
import pytest
from rostrum_core.cache import CACHE
from rostrum_paint import kept_disk


@pytest.fixture(autouse=True)
def _own_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(CACHE, "root", tmp_path / "cache")
    yield
    kept_disk.flush()           # the writer's last entries land here, not in the person's cache
