"""The model gate agents rely on (2D final critic F5-1): a model job short of memory waits, bounded, instead of failing
at once; one waiting for its turn waits while another holds it; both fail plainly when the wait runs out."""
import pytest

from rostrum_core import memory
from rostrum_core.errors import RostrumError


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def test_waits_until_memory_frees():
    c, frees, said = Clock(), iter([1.0, 1.5, 3.0]), []
    got = memory.gate("voice", "voice generation", 2.5, wait=60, waiting=said.append,
                      free=lambda: next(frees), sleep=c.sleep, clock=c)
    assert got == 3.0 and len(said) == 2 and "waiting for memory" in said[0]


def test_fails_plainly_when_memory_never_frees():
    c = Clock()
    with pytest.raises(RostrumError) as e:
        memory.gate("voice", "voice generation", 2.5, wait=10, waiting=lambda w: None,
                    free=lambda: 1.9, sleep=c.sleep, clock=c)
    assert "NO_MEMORY" in str(e.value.code) and "1.9 GB" in str(e.value) and c.t >= 10


def test_turn_waits_for_the_other_job_then_fails_plainly(tmp_path):
    lock = tmp_path / "turn.lock"
    with memory.turn("a", "the phone model", 0.1, wait=5, lock_file=lock, free=lambda: 9.0):
        c = Clock()
        with pytest.raises(RostrumError) as e:
            with memory.turn("b", "voice generation", 0.1, wait=6, lock_file=lock, free=lambda: 9.0,
                             waiting=lambda w: None, sleep=c.sleep, clock=c):
                pass
        assert "another model job" in str(e.value) and c.t >= 6
    with memory.turn("b", "voice generation", 0.1, wait=1, lock_file=lock, free=lambda: 9.0):
        pass                                     # free again once the first job is done
