"""Round sound-motion, Vault: a squash the limiter puts 0.25 s after the asked hit is still the brief's own moment, so
its keep follows the near rule (it was kept at 5.0 dB where 4 dB is the keepable bound, and the hit smeared)."""
from rostrum_sound.mcp import asked_keep


def test_a_squashed_hit_just_after_the_asked_hit_is_kept_only_near_passing():
    def run(db):
        raw = [{"kind": "squashed_hit", "at_s": 31.75, "measured": {"reduced_db": db}, "words": "squashed"}]
        found = [{"id": "squashed_hit@31.75", "what": "squashed", "when": "31.75 s", "fix": "let it ring"}]
        near = asked_keep.mark(raw, found, [{"at": 31.5, "kind": "hit"}])
        keep = asked_keep.screen(found, {"squashed_hit@31.75": "the brief asks for the loudest moment"}, {"squashed_hit@31.75"}, near)
        return found[0], keep
    f, keep = run(5.04)
    assert f.get("asked") and "keepable from 4 dB" in f["what"] and keep == {}
    f, keep = run(3.6)
    assert "squashed_hit@31.75" in keep
