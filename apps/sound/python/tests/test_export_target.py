"""An export lands on its master's loudness target without an extra round (3E audit: -14 asked, -16.9 delivered; the
next render raced the edit_loudness job): the render is pushed to the target at render time while the song keeps its
own limit, a render waits for the song's edit jobs asked before it, and "wav" means 24-bit WAV."""
import threading
from types import SimpleNamespace

import pytest
from rostrum_core import RostrumError
from rostrum_sound import deliver
from rostrum_sound.mcp import export_target, pending_edits

NEED = 5.0      # the fake song needs this much limiting to reach its target


class Engine:
    """Measures a song as the real one does in shape: short of the target by what its maxLimit leaves of NEED."""
    def can(self, what):
        return what == "measure"

    def request(self, what, schedules):
        out = []
        for s in schedules:
            m = s["master"]
            pulls = min(NEED, m.get("maxLimit", 99))
            out.append({"lufs": m["loudness"] - (NEED - pulls), "master": {"limiterMaxReductionDb": pulls}})
        return {"results": out}


def song(max_limit=2.0):
    return SimpleNamespace(folder=None, data={"type": "sound", "tempo": 120, "tracks": [], "master": [
        {"id": "master", "normalize": True, "loudness": -14, "gentle": True, "maxLimit": max_limit}]})


def test_a_render_with_a_target_is_pushed_onto_it_and_the_song_keeps_its_limit(tmp_path):
    doc = song()
    state = SimpleNamespace(engine=Engine(), renders=lambda item: tmp_path)
    got, schedule = export_target.push(state, doc, "song", {})
    assert got["reaches"] and got["max_limit_db"] >= NEED and schedule["master"]["maxLimit"] == got["max_limit_db"]
    assert doc.data["master"][0]["maxLimit"] == 2.0                          # the everyday master stays as written
    assert "dB of limiting" in export_target.words(got)
    assert export_target.push(state, song(NEED + 1), "song", {}) == ({}, None)   # already on target: nothing pushed


class Job:
    def __init__(self, label, status="running"):
        self.id, self.label, self.status, self.owner, self.reason = "job_x", label, status, None, ""
        self.finished = threading.Event()


def test_a_render_waits_for_the_songs_edit_jobs_and_fails_loudly_past_the_wait():
    edit, other = Job("edit_loudness song"), Job("edit_loudness other")
    jobs = SimpleNamespace(listing=lambda: [edit, other, Job("render song")])
    found = pending_edits.pending(jobs, "song")
    assert found == [edit]
    threading.Timer(0.05, lambda: (setattr(edit, "status", "done"), edit.finished.set())).start()
    assert pending_edits.wait(found, "render_mix", wait_s=5) == []
    stuck = Job("cleanup song")
    with pytest.raises(RostrumError, match="still running"):
        pending_edits.wait([stuck], "render_mix", wait_s=0.01)


def test_plain_wav_is_24_bit_wav():
    assert deliver.Options.read({"format": "wav"}).format == "wav24"
