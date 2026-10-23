"""What agents rely on in the render time estimate: the settings reading, the kept measurement (one probe per scene), the
probe's budget (loud, nothing kept) and the scaling. Uses the stand-in engine, no rendering."""
import os
import sys
from pathlib import Path

import pytest

from rostrum_core.cache import Cache
from rostrum_core.errors import RostrumError

from rostrum3d import estimate_job
from rostrum3d.engine import Engine
from rostrum3d.mcp.estimate import scale
from rostrum3d.render_fields import settings

FAKE = Path(__file__).with_name("fake_core.py")
INFO = {"id": "hero", "camera": "cam", "fps": 24, "start": 0, "end": 47, "width": 1920, "height": 1080}


def engine():
    return Engine(sys.executable, dict(os.environ), args=(str(FAKE), "serve"))


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(estimate_job, "CACHE", Cache(tmp_path / "cache"))
    return estimate_job.CACHE


def test_settings_presets_custom_range_and_even_sizes():
    assert [settings({"renderQuality": q}, INFO)["samples"] for q in ("draft", "good", "final")] == [32, 128, 512]
    c = settings({"renderQuality": "custom", "renderSamples": 77, "renderDenoise": False}, INFO)
    assert (c["samples"], c["denoise"]) == (77, False)
    r = settings({"renderRange": "range", "renderStart": 1.0, "renderEnd": 99.0}, INFO)
    assert (r["start"], r["end"]) == (24, 47)
    assert settings({"renderRange": "range", "renderStart": 1.0, "renderEnd": 0.5}, INFO)["end"] == 24   # backwards: one frame
    odd = dict(INFO, width=1001, height=563)
    for size in ("full", "half", "double"):
        s = settings({"renderSize": size}, odd)
        assert s["width"] % 2 == 0 and s["height"] % 2 == 0
    assert settings({"renderSize": "half"}, INFO)["width"] == 960


def test_one_probe_per_scene(cache):
    s, scene = settings({}, INFO), {"shot": "hero", "n": 1}
    a = estimate_job.measure(scene, INFO, s, make_engine=engine)
    b = estimate_job.measure(scene, INFO, s, make_engine=engine)
    assert (a["cached"], b["cached"]) == (False, True)
    assert estimate_job.cached(scene, s, sys.executable)
    c = estimate_job.measure({"shot": "hero", "n": 2}, INFO, s, make_engine=engine)
    assert c["cached"] is False


def test_probe_over_budget_fails_loudly_and_keeps_nothing(cache):
    info, scene = dict(INFO, camera="slow"), {"shot": "hero"}
    s = settings({}, info)
    with pytest.raises(RostrumError) as e:
        estimate_job.measure(scene, info, s, budget_s=0.5, make_engine=engine)
    assert "RENDER_FAILED" in str(e.value).upper() or "budget" in str(e.value)
    assert estimate_job.cached(scene, s, sys.executable) is None


def test_more_samples_scale_only_the_per_pixel_part():
    m = {"samples": 128, "fixed_ms": 500.0, "per_px_ms": 0.001, "load_ms": 2000.0, "warmup_ms": 1000.0}
    s = settings({"renderQuality": "good"}, INFO)
    one = scale(m, s, 10, mp4=False)
    two = scale(m, settings({"renderQuality": "custom", "renderSamples": 256}, INFO), 10, mp4=False)
    px = 1920 * 1080 * 0.001
    assert one["seconds_per_frame"] == pytest.approx((500 + px) / 1000, abs=1e-3)
    assert two["seconds_per_frame"] == pytest.approx((500 + 2 * px) / 1000, abs=1e-3)
    assert two["start_s"] == one["start_s"] == 3.0
