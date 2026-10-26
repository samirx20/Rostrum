"""fit_loudness.landing: the one prediction the Export sheet, the export and the agents' replies use for where a file lands
against its loudness target (critic r11: "Loudness set to -14", the file measured -16.43). Numbers from that song's render."""
from rostrum_sound import fit_loudness as fit

R = {"lufs": -16.38, "master": {"limiterMaxReductionDb": 1.98, "heldDb": 2.35}}      # the hand song, master capped at 2 dB
MASTER = {"normalize": True, "loudness": -14, "gentle": True, "maxLimit": 2}


def test_capped_limiter_lands_under_and_offers_the_push():
    land = fit.landing(MASTER, R)
    assert not land["reaches"] and abs(land["lufs"] - -16.36) < 0.05 and abs(land["need_db"] - 4.36) < 0.05
    assert land["push"]["ops"][0]["args"]["maxLimit"] == 4.5        # measured after the push: -14.21 LUFS
    assert "−16.4 LUFS" in land["words"] and "4.4 dB of limiting" in land["words"] and "acoustic" in land["words"]


def test_reaches_when_allowed_and_says_nothing_without_a_target():
    assert fit.landing({**MASTER, "maxLimit": 4.5}, R)["reaches"]
    assert fit.landing({**MASTER, "gentle": False}, R)["reaches"]
    assert fit.landing({**MASTER, "normalize": False}, R) == {}


def test_beyond_the_master_is_said_not_offered():
    land = fit.landing(MASTER, {"lufs": -26.0, "master": {"limiterMaxReductionDb": 2.0}})
    assert land["impossible"] and land["push"] is None and not land["reaches"]
