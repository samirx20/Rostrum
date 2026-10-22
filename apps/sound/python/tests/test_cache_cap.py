"""RELEASE.md line 16: the engine's cache files are kept under the one cache cap (they were trimmed by nobody)."""
import os

from rostrum_sound import cache_cap


def _file(root, name, size, age_s, now):
    p = root / "sound" / "tracks" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)
    os.utime(p, (now - age_s, now - age_s))
    return p


def test_oldest_engine_files_go_until_under_the_cap(tmp_path):
    now = 1_000_000.0
    old, mid, fresh = (_file(tmp_path, n, 400, age, now) for n, age in (("a", 9000), ("b", 5000), ("c", 60)))
    tmp = _file(tmp_path, "d.f32.123.tmp", 10, 2 * cache_cap.STALE_TMP_S, now)
    freed = cache_cap.trim(tmp_path, cap=900, now=now)
    assert not old.exists() and not tmp.exists()       # least recently used, and an unfinished write
    assert mid.exists() and fresh.exists()             # 800 bytes: under the cap
    assert freed == 410
    cache_cap.trim(tmp_path, cap=0, now=now)
    assert fresh.exists()                              # used in the last 15 minutes: never removed
