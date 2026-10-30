"""The fault check names what a listener would hear: a hit that is barely there, drums dropping early, one flat held tone
(sound-fair benchmark, 2026-10-28: the old check passed all three) and stays quiet on a clear hit."""
import numpy as np
import soundfile as sf

from rostrum_sound.listen.faults import check, held_spans
from rostrum_sound.listen.weakest import from_markers, lines

SR = 48000
NOTES = [261.6, 329.6, 392.0, 440.0, 293.7, 349.2, 493.9, 523.3]


def _note(f, amp, dur=0.45):
    t = np.arange(int(dur * SR)) / SR
    click = np.random.default_rng(int(f)).normal(0, 1, t.size) * np.exp(-t * 200)
    return amp * (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(4 * np.pi * f * t) + 0.3 * click) * np.exp(-t * 6)


def _piece(path, hit_at=10.0, hit_amp=0.2, gap_before=0.0, stop_at=20.0, length=20.0):
    """A note every 0.5 s on a moving line; at `hit_at` a note `hit_amp` loud, with `gap_before` s of silence first."""
    y = np.zeros(int(length * SR))
    for k, t0 in enumerate(np.arange(0, stop_at, 0.5)):
        if hit_at - gap_before <= t0 < hit_at:
            continue
        loud = t0 == hit_at
        n = _note(NOTES[k % len(NOTES)] * (0.5 if loud else 1), hit_amp if loud else 0.2)
        if loud and hit_amp > 0.5:                      # a big hit: a chord, bright, from several instruments
            n = n + sum(_note(f, hit_amp / 2) for f in (130.8, 196.0, 659.3, 1046.5))
        a = int(t0 * SR)
        y[a:a + n.size] += n[:y.size - a]
    y = 0.8 * y / np.abs(y).max()
    sf.write(path, np.stack([y, np.roll(y, 240)], axis=1), SR, subtype="PCM_24")
    return str(path)


def kinds(r):
    return {f["kind"] for f in r["faults"]}


def test_weak_hit_named_with_time_and_fix(tmp_path):
    r = check(_piece(tmp_path / "weak.wav", hit_amp=0.26), [{"at": 10.0, "kind": "hit"}], whole=False)
    assert "weak_hit" in kinds(r)
    assert "10.0" in r["words"] and "a normal note" in r["words"] and "bright attack" in r["words"]


def test_clear_hit_passes(tmp_path):
    r = check(_piece(tmp_path / "clear.wav", hit_amp=1.5, gap_before=0.5), [{"at": 10.0, "kind": "hit"}], whole=False)
    assert r["faults"] == [], r["words"]


def test_drums_dropping_early(tmp_path):
    r = check(_piece(tmp_path / "drop.wav", stop_at=13.3), [{"at": 14.0, "kind": "drop"}], whole=False)
    f = [f for f in r["faults"] if f["kind"] == "early_drop"]
    assert f and 0.4 < f[0]["measured"]["early_s"] < 1.0


def test_flat_held_tone(tmp_path):
    t = np.arange(20 * SR) / SR
    y = 0.2 * sum(np.sin(2 * np.pi * f * t) for f in (146.8, 220.0, 293.7))
    sf.write(tmp_path / "flat.wav", np.stack([y, y], axis=1), SR, subtype="PCM_24")
    r = check(str(tmp_path / "flat.wav"))
    assert "held_tone" in kinds(r) and "one flat tone" in r["words"]
    assert "near_mono" in kinds(r)



def _ringing(midi, dur, decay):
    t = np.arange(int(dur * SR)) / SR
    f = 440.0 * 2 ** ((midi - 69) / 12)
    return sum(np.sin(2 * np.pi * f * h * t) / h ** 1.5 for h in range(1, 6)) * np.exp(-decay * t)


def test_chords_every_two_beats_are_not_held():
    """Late Set (sound-rebench, 2026-10-29): a ii-V every bar at 132 BPM read as "one harmony held 22.5–45 s". Rootless
    voicings share tones and ring into each other over a walking bass, so every class carries a floor; the shape of
    what stands out still changes every two beats."""
    voicings = [[58, 62, 65, 69], [58, 64, 67, 69], [57, 60, 64, 65], [57, 60, 62, 66]]   # Gm7 C9 Fmaj7 D7, rootless
    roots, beat = [43, 36, 41, 38], 60 / 132
    y = np.zeros(32 * SR)
    for i in range(int(30 / (2 * beat))):
        a = int(i * 2 * beat * SR)
        for m in voicings[i % 4]:
            n = 0.08 * _ringing(m, 3.0, 0.8)
            y[a:a + n.size] += n[:y.size - a]
        for k in range(2):
            n, b = 0.15 * _ringing(roots[i % 4] + 7 * k, beat, 2.0), a + int(k * beat * SR)
            y[b:b + n.size] += n[:y.size - b]
    assert held_spans(y[:30 * SR, None], SR) == []


def test_one_chord_for_14_s_is_held():
    y = 0.04 * sum(_ringing(m, 14.0, 0.0) for m in (41, 53, 57, 60, 64))
    spans = held_spans(y[:, None], SR)
    assert spans and spans[0]["seconds"] >= 12.0

def test_a_steady_drum_groove_is_not_a_held_harmony():
    """Sound-as-written's left-over: a drum-only canary mix (kick, snare, a hi-hat every eighth) read as "one harmony held
    0-15.3 s". Only notes hold a harmony; the drums' leftover after they are taken out is not one."""
    rng, beat = np.random.default_rng(3), 0.5
    y = np.zeros(20 * SR)
    t = np.arange(int(0.3 * SR)) / SR
    kick = np.sin(2 * np.pi * (55 + 90 * np.exp(-t * 30)) * t) * np.exp(-t * 12)
    hat = np.diff(rng.normal(0, 1, t.size + 1)) * np.exp(-t * 60)
    snare = (rng.normal(0, 1, t.size) * 0.6 + np.sin(2 * np.pi * 190 * t)) * np.exp(-t * 18)
    for k in range(int(19.5 / (beat / 2))):
        a = int(k * beat / 2 * SR)
        y[a:a + t.size] += 0.25 * hat[:y.size - a]
        if k % 4 == 0:
            y[a:a + t.size] += 0.6 * kick[:y.size - a]
        if k % 4 == 2:
            y[a:a + t.size] += 0.4 * snare[:y.size - a]
    assert held_spans(y[:, None], SR) == []
    chord = 0.04 * sum(_ringing(m, 20.0, 0.0) for m in (41, 53, 57, 60, 64))      # the same groove under a held chord is held
    assert held_spans((y + chord[:y.size])[:, None], SR)


def test_low_boom_hit_is_weak_and_the_render_lines_say_why(tmp_path):
    """Sound-gaps brief 2: a loud low hit with no bright attack, after a breath of silence, passed the old mel check
    (2.9x) while listeners and the benchmark heard a normal note. The attack check names it and points at the crack."""
    y = np.zeros(20 * SR)
    for k, t0 in enumerate(np.arange(0, 20, 0.5)):          # a bed of bright, clicky notes
        if 9.0 <= t0 < 10.0:
            continue
        n = _note(NOTES[k % len(NOTES)] * 2, 0.2)
        y[int(t0 * SR):int(t0 * SR) + n.size] += n[:y.size - int(t0 * SR)]
    t = np.arange(int(1.5 * SR)) / SR                        # the hit: 55 Hz, 25 ms swell, no click
    boom = 3.0 * np.sin(2 * np.pi * 55 * t) * np.minimum(1, t / 0.025) * np.exp(-t * 2)
    y[10 * SR:10 * SR + boom.size] += boom
    y = 0.8 * y / np.abs(y).max()
    sf.write(tmp_path / "boom.wav", np.stack([y, np.roll(y, 240)], axis=1), SR, subtype="PCM_24")
    moments = from_markers([("Big hit", 10.0), ("verse", 2.0)])
    assert moments == [{"at": 10.0, "kind": "hit"}]
    out = lines(str(tmp_path / "boom.wav"), moments)
    assert out[0].startswith("10.0") and "weak hit" in out[0] and "bright attack" in out[0] and "fast bright attack" in out[0], out


def test_weak_hit_with_the_build_at_the_ceiling_leads_with_headroom(tmp_path):
    """Sound-gaps 2: the build already peaked at the limiter's ceiling, and "raise the build" flattened the piece.
    The fix list starts with headroom (the build's peaks 4–6 dB under), measured from the 3 s before."""
    r = check(_piece(tmp_path / "flat.wav", hit_amp=0.2), [{"at": 10.0, "kind": "hit"}], whole=False)
    f = next(f for f in r["faults"] if f["kind"] == "weak_hit")
    assert f["measured"]["headroom_db"] < 1.5 and "fix: make headroom" in f["words"] and "raise the build" not in r["words"]


def test_dull_top_end_named_and_a_bright_mix_passes(tmp_path):
    """Sound-gaps 2: dull mixes (top end -20 dB and under against the low middle) were never named."""
    t = np.arange(12 * SR) / SR
    dull = 0.2 * sum(np.sin(2 * np.pi * f * t) for f in (220.0, 330.0, 440.0)) * (1 + 0.5 * np.sin(2 * np.pi * 0.7 * t))
    bright = dull + 0.05 * np.random.default_rng(1).normal(0, 1, t.size)
    for name, y in (("dull", dull), ("bright", bright)):
        sf.write(tmp_path / f"{name}.wav", np.stack([y, np.roll(y, 480)], axis=1), SR, subtype="PCM_24")
    r = check(str(tmp_path / "dull.wav"))
    assert "dull_top" in kinds(r) and "4–16 kHz" in r["words"] and "up an octave" in r["words"]
    assert "dull_top" not in kinds(check(str(tmp_path / "bright.wav")))


def test_a_stronger_attack_just_before_a_climax_takes_the_moment(tmp_path):
    """Deliver-clean Ascent r2: a pickup 1.9x the climax's attack, 0.93 s early, was heard as the climax arriving early."""
    path = _piece(tmp_path / "rival.wav", hit_amp=0.6, gap_before=0.5)
    y, _ = sf.read(path)
    n = sum(_note(f, 1.2) for f in (98.0, 196.0, 784.0, 1568.0))       # a loud bright stroke at 9.1 s
    a = int(9.1 * SR)
    y[a:a + n.size] += n[:, None]
    sf.write(path, 0.8 * y / np.abs(y).max(), SR, subtype="PCM_24")
    r = check(path, [{"at": 10.0, "kind": "climax"}], whole=False)
    f = [f for f in r["faults"] if f["kind"] == "early_rival"]
    assert f and abs(f[0]["measured"]["rival_s"] - 9.1) < 0.05 and "moment(" in f[0]["words"], r["words"]
    clean = check(_piece(tmp_path / "clear.wav", hit_amp=1.5, gap_before=0.5), [{"at": 10.0, "kind": "hit"}], whole=False)
    assert "early_rival" not in kinds(clean)


def test_an_asked_moment_with_nothing_weak_still_gets_its_line():
    """a1: expect ["#lift"] printed "Weakest moments (1 asked):" over an empty list; a passing lift says its rise."""
    sr = 48000
    t = np.arange(30 * sr) / sr
    y = (0.05 * np.sin(2 * np.pi * 220 * t) * (1 + 3 * (t >= 20))).astype("float32")
    said = lines((y, sr), [{"at": 20.0, "kind": "lift"}], found=[])
    assert len(said) == 1 and "lift" in said[0] and "LU" in said[0]


def test_an_auditions_offset_puts_song_time_in_the_words(tmp_path):
    """render_audition measures a stretch from 34 s: its notes say 36.00 s, not the stretch's own 2.00 s."""
    y = 0.05 * np.sin(2 * np.pi * 220 * np.arange(SR * 4) / SR)
    sf.write(tmp_path / "s.wav", np.stack([y, y], axis=1), SR, subtype="PCM_24")
    f = check(str(tmp_path / "s.wav"), [{"at": 2.0, "kind": "hit"}], whole=False, offset=34.0)["faults"][0]
    assert f["at_s"] == 36.0 and "36.00 s" in f["words"]
