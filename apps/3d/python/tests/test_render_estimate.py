"""What agents rely on in the render time estimate: the settings reading, the kept measurement (one probe per scene), the
probe's budget (loud, nothing kept), a busy-card probe never kept as clean, and the scaling. Uses the stand-in engine, no rendering."""
import os
import sys
from pathlib import Path

import pytest

from rostrum_core.cache import Cache
from rostrum_core.errors import RostrumError

from rostrum3d import estimate_job, gpu_busy
from rostrum3d.engine import Engine
from rostrum3d.mcp.estimate import fitting_settings, scale, seconds_at
from rostrum3d.render_fields import settings

FAKE = Path(__file__).with_name("fake_core.py")
INFO = {"id": "hero", "camera": "cam", "fps": 24, "start": 0, "end": 47, "width": 1920, "height": 1080}


def engine():
    return Engine(sys.executable, dict(os.environ), args=(str(FAKE), "serve"))


FREE = lambda own=(): ""  # noqa: E731  the card as free (the real check would read this machine's card)


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
    a = estimate_job.measure(scene, INFO, s, make_engine=engine, card=FREE)
    b = estimate_job.measure(scene, INFO, s, make_engine=engine, card=FREE)
    assert (a["cached"], b["cached"]) == (False, True)
    assert estimate_job.cached(scene, s, sys.executable)
    c = estimate_job.measure({"shot": "hero", "n": 2}, INFO, s, make_engine=engine, card=FREE)
    assert c["cached"] is False


def test_probe_over_budget_fails_loudly_and_keeps_nothing(cache):
    info, scene = dict(INFO, camera="slow"), {"shot": "hero"}
    s = settings({}, info)
    with pytest.raises(RostrumError) as e:
        estimate_job.measure(scene, info, s, budget_s=0.5, make_engine=engine, card=FREE)
    assert "RENDER_FAILED" in str(e.value).upper() or "budget" in str(e.value)
    assert estimate_job.cached(scene, s, sys.executable) is None


def test_busy_card_probe_is_said_and_never_kept_as_clean(cache):
    s, scene = settings({}, INFO), {"shot": "hero", "busy": 1}
    note = "Another job is using the graphics card (90 % busy): renders are slower now, about 2× while it runs."
    a = estimate_job.measure(scene, INFO, s, make_engine=engine, card=lambda own=(): note)
    assert estimate_job.card_note(a) == note and a["cached"] is False
    assert estimate_job.cached(scene, s, sys.executable) is None             # not found as the scene's clean probe
    b = estimate_job.measure(scene, INFO, s, make_engine=engine, card=FREE)
    assert b["cached"] is False and estimate_job.card_note(b) == ""          # measured again on the free card, and kept
    c = estimate_job.measure(scene, INFO, s, make_engine=engine, card=lambda own=(): note)
    assert c["cached"] is True and estimate_job.card_note(c) == note         # a kept probe carries the card's state of now


def test_gpu_busy_threshold_and_no_tool():
    assert gpu_busy.busy(read=lambda: None, gap_s=0) == ""                    # no nvidia-smi (a Mac): silent, never a crash
    idle = iter([10, 6, 0])
    assert gpu_busy.busy(read=lambda: next(idle), gap_s=0) == ""
    hot = iter([95, 99, 3])
    assert "95 % busy" in gpu_busy.busy(read=lambda: next(hot), gap_s=0)    # the middle sample: one dip does not hide it


def test_gpu_busy_own_programs_are_not_another_job():
    hot = lambda: 97  # noqa: E731
    on_card = lambda: {501: "rostrum3d-core.exe"}  # noqa: E731
    assert gpu_busy.busy(own_pids=[501], read=hot, apps=on_card, gap_s=0) == ""                 # our own viewport
    assert "rostrum3d-core.exe" in gpu_busy.busy(own_pids=[7], read=hot, apps=on_card, gap_s=0)  # someone else's engine
    assert gpu_busy.busy(own_pids=[501], read=lambda: 5, apps=on_card, gap_s=0) == ""           # an idle viewport


def test_samples_follow_the_measured_curve_and_size_rescales():
    m = {"samples": 128, "curve": [[8, 0.25], [32, 0.5], [128, 1.0]], "fixed_ms": 500.0, "per_px_ms": 0.001,
         "load_ms": 2000.0, "warmup_ms": 1000.0}
    base = (500 + 1920 * 1080 * 0.001) / 1000
    per = lambda n, **k: scale(m, settings({"renderQuality": "custom", "renderSamples": n, **k}, INFO), 10, mp4=False)  # noqa: E731
    assert per(128)["seconds_per_frame"] == pytest.approx(base, abs=1e-3)
    assert per(32)["seconds_per_frame"] == pytest.approx(base * 0.5, abs=1e-3)
    assert per(4)["seconds_per_frame"] == pytest.approx(base * 0.125, abs=1e-3)     # below the curve: in step
    assert per(512)["seconds_per_frame"] == pytest.approx(base * 1.5, abs=1e-3)     # the last segment carried on (log scale)
    half = per(128, renderSize="half")
    assert half["seconds_per_frame"] == pytest.approx((500 + 960 * 540 * 0.001) / 1000, abs=1e-3)
    assert half["start_s"] == 3.0
    neg = dict(m, fixed_ms=-500.0, probe={"size": [960, 540]})                       # a line below 0 under the quarter size
    tiny = scale(neg, settings({"renderQuality": "good"}, dict(INFO, width=480, height=270)), 1, mp4=False)
    assert tiny["seconds_per_frame"] == pytest.approx((-500 + 960 * 540 * 0.001) / 4 / 1000, abs=1e-3)


def test_fewer_samples_never_longer_and_fits_follow_the_measurement():
    # The 13d probe of a glass + gloss scene at 1280x720 (real: 128 / 32 / 8 samples took 3.4 / 1.75 / 0.88 s a frame).
    # Its few-sample point came out at 1.02 once (noise): that must not make 8 samples cost more than 128.
    m = {"samples": 128, "curve": [[8, 1.02], [128, 1.0]], "fixed_ms": -146.0, "per_px_ms": 0.0039, "load_ms": 127.0,
         "warmup_ms": 568.0, "probe": {"size": [640, 360]}}
    s = settings({"renderQuality": "custom", "renderSamples": 128}, dict(INFO, width=1280, height=720))
    times = [scale(m, {**s, "samples": n}, 240, mp4=True)["seconds"] for n in (1, 4, 8, 12, 28, 64, 128, 512)]
    assert times == sorted(times)
    m["curve"] = [[8, 0.2521], [128, 1.0]]
    at = seconds_at(m, s, 240, True)
    est = at("samples", 128)
    fits = {f["change"]: f["to"] for f in fitting_settings(est, est / 2, "cycles", 128, 1280, at)}
    assert at("samples", fits["samples"]) <= est / 2 < at("samples", fits["samples"] + 1)   # the most samples that fit, measured
    assert at("samples", 128 // 2) > est / 2             # time grows less than in step: half the samples would not fit
    assert at("width", fits["width"]) <= est / 2


def test_a_scene_that_changes_every_frame_costs_more_per_frame_and_a_slow_render_teaches_the_next_guess(cache):
    """Round 3: a cloth drape was guessed at 2.2 s a frame and took 3.65 (each new frame sends the scene's new shape in)."""
    from rostrum3d import estimate_learn
    m = {"samples": 0, "curve": [], "fixed_ms": 500.0, "per_px_ms": 0.001, "load_ms": 0.0, "warmup_ms": 0.0}
    s = settings({}, INFO)
    plain = scale(m, s, 10, mp4=False)["seconds_per_frame"]
    assert scale({**m, "change_ms": 1400.0}, s, 10, mp4=False)["seconds_per_frame"] == pytest.approx(plain + 1.4, abs=1e-3)
    assert scale({**m, "change_ms": 1400.0}, s, 1, mp4=False)["seconds_per_frame"] == pytest.approx(plain, abs=1e-3)   # a still: no next frame
    got = estimate_job.measure({"shot": "hero", "n": 9}, INFO, settings({}, INFO), make_engine=engine, card=FREE)
    assert got["change_ms"] >= 0
    k = ("proj", "item", "hero", "cycles")
    e = scale(m, s, 10, mp4=False)
    assert estimate_learn.apply(e, k) is e                                   # nothing learned yet
    estimate_learn.record(k, 500.0, 800.0)                                    # took 1.6x its guess
    up = estimate_learn.apply(e, k)
    assert up["seconds"] == pytest.approx(e["seconds"] * 1.6, abs=0.1) and "1.6" in estimate_learn.words(up)
    estimate_learn.record(k, 500.0, 520.0)                                    # a close one forgets it: never lowered below the measurement
    assert estimate_learn.apply(e, k) is e
