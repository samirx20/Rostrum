"""P-SND cue: 60 seconds, D minor, 96 bpm (one bar = 2.5 s, 24 bars), composed through the rsnd driver.

Shape: drone + piano motif (bars 0-3) -> string ostinato and horns (4-7) -> pulse, low brass (8-11)
-> build: tremolo, timpani roll, riser (12-16) -> hit at bar 17 (42.5 s) and full climax (17-21)
-> release: low D, piano motif, high strings fading (22-23).

Run (from proofs/sound): ..\\..\\.venv\\Scripts\\python.exe cue\\cue.py <out.wav> [--stems <dir>]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rsnd import Session, effects as fx  # noqa: E402

LIB = Path(r"C:\Users\Sam\.rostrum\assets\sounds")
STR, BRS, PRC = LIB / "vsco2-strings", LIB / "vsco2-brass", LIB / "vsco2-percussion"
PIANO = LIB / "salamander-piano" / "SalamanderGrandPianoV3_44.1khz16bit" / "SalamanderGrandPianoV3.sfz"
KIT = LIB / "muldjord-kit" / "MuldjordKit SFZ+FLAC-20201018" / "rostrum-gm.sfz"
FS = LIB / "freesound"
SCRATCH = Path(r"C:\Users\Sam\.rostrum\waves\scratch\priyam-p1\cue")

# Chords per bar (root-position triads, voiced per instrument below). i-VI-iv-V, then i-VI-III-VII at the climax.
VERSE = [("D", "F", "A"), ("Bb", "D", "F"), ("G", "Bb", "D"), ("A", "C#", "E")]
CLIMAX = [("D", "F", "A"), ("Bb", "D", "F"), ("F", "A", "C"), ("C", "E", "G")]
HIT = 17


def chord_at(bar):
    return (CLIMAX if bar >= HIT else VERSE)[bar % 4]


def build(s: Session):
    b, bt = s.bar, s.beat

    # --- low strings: drone, then the ostinato --------------------------------------------------
    bass = s.track("contrabass", sfz=STR / "ContrabassSusVB.sfz", volume=0.9, pan=0.1, reverb=0.25)
    for bar in range(0, 22):
        root = chord_at(bar)[0] if bar >= 8 else "D"
        bass.note(f"{root}1" if root in ("A", "Bb", "G") and bar >= 8 else f"{root}2", at=b(bar), dur=b(1) - 0.05,
                  vel=0.45 if bar < 4 else 0.6 if bar < HIT else 0.85)
    bass.note("D2", at=b(22), dur=b(2) - 0.2, vel=0.5)
    bass.volume_automation([(0, 0.0), (b(2), 0.8), (b(4), 0.9), (b(22), 0.9), (59.5, 0.0)])

    cello = s.track("cello", sfz=STR / "CelloEnsSusVib.sfz", volume=0.75, pan=0.05, reverb=0.3)
    for bar in range(0, 8):
        cello.note(chord_at(bar)[0] + "3" if bar >= 4 else "D3", at=b(bar), dur=b(1) - 0.05, vel=0.4 + 0.04 * bar)
    cello.volume_automation([(0, 0.75), (b(7), 0.75), (b(8), 0.0)])

    spic = s.track("ostinato", sfz=STR / "CelloEnsSpic.sfz", volume=0.7, pan=-0.15, reverb=0.25)
    # The figure: 8ths, root-root-fifth-root-third-root-fifth-root, accented on 1 and the "and" of 2.
    for bar in range(4, 22):
        r, t3, f5 = chord_at(bar)
        lo = "3" if r in ("D", "C") else "2"
        figure = [r + lo, r + lo, f5 + "3", r + lo, t3 + "3", r + lo, f5 + "3", r + "3"]
        for i, n in enumerate(figure):
            acc = 0.15 if i in (0, 3, 6) else 0.0
            ramp = min(1.0, 0.6 + 0.03 * (bar - 4)) if bar < HIT else 0.95
            spic.note(n, at=b(bar) + bt(i * 0.5), dur=bt(0.45), vel=min(1.0, ramp + acc))
    hi_spic = s.track("violins-spic", sfz=STR / "ViolinEnsSpic.sfz", volume=0.55, pan=-0.35, reverb=0.3)
    for bar in list(range(8, 16)) + list(range(HIT, 22)):
        r, t3, f5 = chord_at(bar)
        for i, n in enumerate([f5 + "4", r + "5", t3 + "5", r + "5"] * 2):
            hi_spic.note(n, at=b(bar) + bt(i * 0.5), dur=bt(0.4), vel=0.5 + 0.03 * (bar - 8) if bar < HIT else 0.85)

    # --- high strings: pads, the build's tremolo, the release ---------------------------------
    vln = s.track("violins", sfz=STR / "ViolinEnsSusVib.sfz", volume=0.6, pan=-0.3, reverb=0.4)
    for bar in range(4, 12, 2):
        r, t3, f5 = chord_at(bar)
        vln.chord([t3 + "4", f5 + "4"], at=b(bar), dur=b(2) - 0.1, vel=0.45)
    for bar in range(HIT, 22):
        r, t3, f5 = chord_at(bar)
        vln.chord([r + "5", t3 + "5", f5 + "5"] + ([r + "6"] if r in ("C", "D") else []), at=b(bar), dur=b(1) - 0.05, vel=0.8)
    vln.note("A5", at=b(22), dur=b(2) - 0.3, vel=0.4)
    vln.volume_automation([(0, 0.6), (b(22), 0.6), (b(22) + 0.5, 0.5), (59.8, 0.0)])

    trem = s.track("tremolo", sfz=STR / "ViolinEnsTrem.sfz", volume=0.6, pan=-0.2, reverb=0.35)
    # Rising line over the build, one step per half bar, held under a swell.
    for i, n in enumerate(["D4", "E4", "F4", "G4", "A4", "Bb4", "C5", "C#5", "D5", "E5"]):
        trem.note(n, at=b(12) + i * b(0.5), dur=b(0.5) - 0.02, vel=0.5 + 0.05 * i)
    trem.volume_automation([(b(12), 0.55), (b(HIT) - 0.05, 1.0), (b(HIT), 0.0)])

    # --- brass: the motif, low brass weight --------------------------------------------------
    motif = [("D", 0, 1.5), ("F", 1.5, 0.5), ("E", 2, 1), ("A", 3, 1), ("D", 4, 2), ("C", 6, 1), ("Bb", 7, 1)]
    horns = s.track("horns", sfz=BRS / "FHornSus.sfz", volume=0.42, pan=0.3, reverb=0.45)
    for start, vel, octv in ((6, 0.55, "4"), (10, 0.65, "4"), (HIT, 0.95, "4"), (HIT + 2, 0.95, "4")):
        for n, at, d in motif:
            horns.note(n + octv, at=b(start) + bt(at), dur=bt(d) - 0.03, vel=vel)
    trumpets = s.track("trumpets", sfz=BRS / "TrumpetSus.sfz", volume=0.38, pan=0.15, reverb=0.45)
    for start in (HIT, HIT + 2):
        for n, at, d in motif:
            trumpets.note(n + "5" if n not in ("Bb", "C") else n + "4", at=b(start) + bt(at), dur=bt(d) - 0.03, vel=0.7)

    low = s.track("low-brass", sfz=BRS / "TromboneSus.sfz", volume=0.75, pan=-0.05, reverb=0.35)
    low.effect(fx.eq(("peak", 250, -3, 1.0)))
    tuba = s.track("tuba", sfz=BRS / "TubaSus.sfz", volume=0.7, pan=0.0, reverb=0.3)
    for bar in list(range(8, 16)) + list(range(HIT, 22)):
        r, t3, f5 = chord_at(bar)
        v = 0.55 if bar < 12 else 0.7 if bar < HIT else 0.95
        low.chord([r + "3", f5 + "3"], at=b(bar), dur=b(1) - 0.08, vel=v)
        tuba.note(r + "2", at=b(bar), dur=b(1) - 0.08, vel=v)

    # --- percussion: timpani, kit toms/kick as a pulse, recorded hits ---------------------------
    timp = s.track("timpani", sfz=PRC / "Timpani.sfz", volume=1.0, pan=0.05, reverb=0.35)
    for bar in range(4, 22):
        if bar in range(12, HIT):
            continue
        timp.note("D2", at=b(bar), dur=bt(1), vel=0.8 if bar < HIT else 1.0)
        if bar >= 8:
            timp.note("A2", at=b(bar) + bt(2.5), dur=bt(1), vel=0.5 if bar < HIT else 0.85)
    roll = s.track("timpani-roll", sfz=PRC / "TimpaniRolls.sfz", volume=0.85, pan=0.05, reverb=0.35)
    roll.note("D2", at=b(3), dur=b(1), vel=0.35)
    roll.note("A2", at=b(12), dur=b(HIT - 12) - 0.05, vel=0.9)
    roll.volume_automation([(0, 0.6), (b(12), 0.2), (b(HIT) - 0.05, 1.0), (b(HIT), 0.0)])

    drums = s.track("drums", kit=KIT, volume=0.7, reverb=0.25)
    for bar in list(range(8, 16)) + list(range(HIT, 22)):
        drums.drum("kick", at=b(bar), vel=0.8).drum("tomLow", at=b(bar) + bt(1.5), vel=0.6)
        drums.drum("tomLow", at=b(bar) + bt(2.5), vel=0.7).drum("tom", at=b(bar) + bt(3.5), vel=0.6)
        if bar >= HIT:
            drums.drum("snare", at=b(bar) + bt(1), vel=0.8).drum("snare", at=b(bar) + bt(3), vel=0.85)
    for i in range(16):  # the last build bar: 16ths on toms into the hit
        drums.drum("tomHigh" if i % 2 else "tom", at=b(16) + bt(i * 0.25), vel=0.5 + 0.03 * i)
    drums.drum("crash", at=b(HIT), vel=1.0).drum("crash", at=b(8), vel=0.6)
    drums.effect(fx.compressor(threshold=-18, ratio=3, attack=0.005, release=0.12))

    hits = s.track("hits", volume=0.8, reverb=0.2)
    hits.sample(FS / "203119.ogg", at=0.0, volume=0.35, pan=-0.2, fade_in=3.0, fade_out=4.0, duration=b(4) + 2)   # drone bed
    hits.sample(FS / "683667.ogg", at=b(HIT) - 4.0, volume=0.6, fade_in=1.0)                           # riser into the hit
    hits.sample(FS / "110218.ogg", at=b(HIT) - 3.0, volume=0.5)                                         # reverse crash
    hits.sample(FS / "431316.ogg", at=b(HIT), volume=0.75, fade_out=1.5)                                # braam
    hits.sample(FS / "428073.ogg", at=b(HIT), volume=0.7)                                               # sub drop
    hits.sample(FS / "430977.ogg", at=b(22) - 0.02, volume=0.45, fade_out=3.0)                          # last hit, the cut

    # --- piano: the motif bare at the start and in the release ----------------------------------
    piano = s.track("piano", sfz=PIANO, volume=2.0, pan=-0.12, reverb=0.5)
    for start, vel in ((1, 0.45), (22, 0.4)):
        for n, at, d in motif[:5]:
            piano.note(n + "5", at=b(start) + bt(at), dur=bt(d) + 0.4, vel=vel)
    piano.note("D4", at=b(23) + bt(2), dur=4.0, vel=0.3)
    piano.effect(fx.eq(("highpass", 120, 0, 0.7)))

    s.master(lufs=-16, true_peak=-1.0, glue=0.25)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--stems")
    a = ap.parse_args()
    s = Session(bpm=96, seconds=60, sample_rate=48000, cache_dir=SCRATCH / "pcm-cache", reverb_space="hall")
    build(s)
    st = s.render(a.out)
    print(json.dumps({"lufs": st["lufs"], "truePeak": st["truePeak"], "lra": st["lra"], "render": st["renderSeconds"],
                      "tracks": {t["name"]: round(t["lufs"], 1) if t["lufs"] is not None else None for t in st["tracks"]}}))
    if a.stems:
        s.render_stems(a.stems)


if __name__ == "__main__":
    main()
