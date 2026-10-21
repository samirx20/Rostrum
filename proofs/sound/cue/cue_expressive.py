"""P4 expressive cue: P1's 60-second cue (cue.py), the same notes, form and instruments, re-written for the
app's script layer (rostrum_sound.run_source -> Document -> compile) with expressive playing turned on.

D minor, 96 bpm, one bar = 2.5 s (bar n below starts at n x 2.5 s, counting from bar 0 like cue.py).

What changed, and what to listen for (seconds):
  0-10 s   Cellos: the held low D now swells in (the sampled strings' swell) and a gentle extra vibrato grows
           over the first bars. Bass and cellos play legato: bow changes join instead of re-starting.
  2.5 s    Piano motif: slightly loose timing and a phrase-shaped touch (louder into the long D, then easing),
           instead of every note at one level.
  10 s     Cello spiccato ostinato enters; it now grows note by note across the phrase to the hit, with the
           same accents on 1 and the "and" of 2, and small seeded timing / velocity differences (less machine).
           Violin pad chords (10, 15, 20, 25 s): each chord swells in and eases off.
  15 s     Horns: the motif played legato; the long D swells (also at 25 s, then at 42.5 and 47.5 s with trumpets).
  20 s     Drums, low brass and tuba: humanized; low brass / tuba swell inside each bar during the build.
  30-42.5  The build: the violins' tremolo line is now the violin track's "tremolo" articulation, and the
           timpani roll is the timpani track's "roll" articulation (one instrument each, as a player would).
           Dynamics lanes push violins, cellos, bass, low brass and the roll up into the hit (expression,
           not just faders). New: a quiet saw synth pad under the build and climax (the hybrid layer P1 lacked).
  40-42.5  Tom fill into the hit: velocity rises along the fill (a phrase curve) instead of fixed steps.
  42.5 s   The hit (bar 17): full climax, 42.5-55 s.
  55-60 s  The release: the bass and violins fall back on their dynamics lanes; the last violin A5 gets a slow
           vibrato that fades in; piano motif again, phrased.

Run as a program (writes the compiled engine schedule; the lead renders it):
  C:\\Users\\Sam\\.t3\\worktrees\\Rostrum\\team-priyam\\.venv\\Scripts\\python.exe cue_expressive.py <schedule.json>
Run inside the app: run_script with this file; the try block below is skipped there (tempo() exists).
"""
try:
    tempo  # noqa: B018  (defined when the app runs this file as a script)
except NameError:  # run as a program: compile this file through the app's script layer
    import json
    import sys
    from pathlib import Path

    from rostrum_core import Document, Who
    from rostrum_sound import KIND, compile as compile_schedule, run_source

    _here = Path(__file__).resolve()
    _doc = Document.new(KIND)
    _doc.run_script(_here.name, run_source(_here.read_text(encoding="utf-8"), _here.name), Who.script(_here.name))
    Path(sys.argv[1]).write_text(json.dumps(compile_schedule(_doc), indent=1), encoding="utf-8")
    print(sys.argv[1])
    raise SystemExit(0)

LIB = "C:\\Users\\Sam\\.rostrum\\assets\\sounds\\"
STR, BRS, PRC, FS = LIB + "vsco2-strings\\", LIB + "vsco2-brass\\", LIB + "vsco2-percussion\\", LIB + "freesound\\"
PIANO = LIB + "salamander-piano\\SalamanderGrandPianoV3_44.1khz16bit\\SalamanderGrandPianoV3.sfz"
KIT = LIB + "muldjord-kit\\MuldjordKit SFZ+FLAC-20201018\\rostrum-gm.sfz"

BAR, BEAT, HIT = 2.5, 0.625, 17
VERSE = [("D", "F", "A"), ("Bb", "D", "F"), ("G", "Bb", "D"), ("A", "C#", "E")]
CLIMAX = [("D", "F", "A"), ("Bb", "D", "F"), ("F", "A", "C"), ("C", "E", "G")]
BUILD = list(range(8, 16)) + list(range(HIT, 22))


def b(n):
    return n * BAR


def bt(n):
    return n * BEAT


def chord_at(bar):
    return (CLIMAX if bar >= HIT else VERSE)[bar % 4]


def legato_line(t, pitches, starts, durs, overlap=0.1):
    """A held line: each note runs `overlap` s into the next when the pitch changes (legato joins them)."""
    for i, (p, at, d) in enumerate(zip(pitches, starts, durs)):
        joins = i + 1 < len(pitches) and pitches[i + 1] != p and starts[i + 1] - (at + d) < 0.2
        t.note(p, at=at, dur=d + overlap if joins else d - 0.05)


tempo(96)
length(60)
marker("hit", at=b(HIT))

# --- low strings: drone, then the ostinato ------------------------------------------------------
bass = track("contrabass", sfz=STR + "ContrabassSusVB.sfz", legato=True, volume=0.9, pan=0.1, reverb=0.25)
roots = ["D2"] * 8 + [(chord_at(n)[0] + "1" if chord_at(n)[0] in ("A", "Bb", "G") else chord_at(n)[0] + "2")
                      for n in range(8, 22)]
legato_line(bass, roots, [b(n) for n in range(22)], [b(1)] * 22)
bass.note("D2", at=b(22), dur=b(2) - 0.2, vel=0.5)
bass.phrase(0, b(4) - 0.1, vel=[(0, 0.45), (1, 0.5)])
bass.phrase(b(4), b(HIT) - 0.1, vel=[(0, 0.55), (1, 0.75)])
bass.phrase(b(HIT), b(22) - 0.1, vel=[(0, 0.88), (1, 0.8)])
bass.automate("volume", [(0, 0.0), (b(2), 0.8), (b(4), 0.9), (b(22), 0.9), (59.5, 0.0)])
bass.dynamics([(b(12), 0.9), (b(HIT) - 0.05, 1.2), (b(HIT), 1.05), (b(22), 1.0), (b(24), 0.6)])
bass.humanize(seed=11, timing=0.01, velocity=0.04)

cello = track("cello", sfz=STR + "CelloEnsSusVib.sfz", legato=True, swell=True, volume=0.75, pan=0.05, reverb=0.3)
legato_line(cello, ["D3"] * 4 + [chord_at(n)[0] + "3" for n in range(4, 8)], [b(n) for n in range(8)], [b(1)] * 8)
cello.phrase(0, b(7), vel=[(0, 0.4), (1, 0.68)])
cello.automate("volume", [(0, 0.75), (b(7), 0.75), (b(8), 0.0)])
cello.vibrato([(0, 0.0), (b(3), 0.5), (b(7), 0.35)], rate=5.2, depth=10)
cello.humanize(seed=12, timing=0.01, velocity=0.04)

spic = track("ostinato", sfz=STR + "CelloEnsSpic.sfz", volume=0.7, pan=-0.15, reverb=0.25)
grow = vel_curve([(0, 0.6), (1, 0.95)], b(4), b(HIT))
for bar in range(4, 22):
    r, t3, f5 = chord_at(bar)
    lo = "3" if r in ("D", "C") else "2"
    for i, n in enumerate([r + lo, r + lo, f5 + "3", r + lo, t3 + "3", r + lo, f5 + "3", r + "3"]):
        at = b(bar) + bt(i * 0.5)
        acc = 0.15 if i in (0, 3, 6) else 0.0
        spic.note(n, at=at, dur=bt(0.45), vel=round(min(1.0, (grow(at) if bar < HIT else 0.95) + acc), 3))
spic.dynamics([(b(12), 0.9), (b(HIT) - 0.05, 1.25), (b(HIT), 1.0)])
spic.humanize(seed=13, timing=0.008, velocity=0.05)

hi_spic = track("violins-spic", sfz=STR + "ViolinEnsSpic.sfz", volume=0.55, pan=-0.35, reverb=0.3)
for bar in BUILD:
    r, t3, f5 = chord_at(bar)
    for i, n in enumerate([f5 + "4", r + "5", t3 + "5", r + "5"] * 2):
        hi_spic.note(n, at=b(bar) + bt(i * 0.5), dur=bt(0.4))
hi_spic.phrase(b(8), b(16) - 0.1, vel=[(0, 0.5), (1, 0.74)])
hi_spic.phrase(b(HIT), b(22) - 0.1, vel=[(0, 0.88), (1, 0.82)])
hi_spic.humanize(seed=14, timing=0.008, velocity=0.05)

# --- high strings: pads, the build's tremolo (an articulation now), the release ------------------
vln = track("violins", sfz=STR + "ViolinEnsSusVib.sfz", articulations={"tremolo": STR + "ViolinEnsTrem.sfz"},
            volume=0.6, pan=-0.3, reverb=0.4)
for bar in range(4, 12, 2):
    r, t3, f5 = chord_at(bar)
    vln.chord([t3 + "4", f5 + "4"], at=b(bar), dur=b(2) - 0.1, dynamics=[(0, 0.6), (0.45, 1.0), (1, 0.8)])
vln.phrase(b(4), b(10), vel=[(0, 0.4), (1, 0.55)])
for i, n in enumerate(["D4", "E4", "F4", "G4", "A4", "Bb4", "C5", "C#5", "D5", "E5"]):
    vln.note(n, at=b(12) + i * b(0.5), dur=b(0.5) - 0.02, art="tremolo")
vln.phrase(b(12), b(16.5), vel=[(0, 0.5), (1, 0.95)])
for bar in range(HIT, 22):
    r, t3, f5 = chord_at(bar)
    vln.chord([r + "5", t3 + "5", f5 + "5"] + ([r + "6"] if r in ("C", "D") else []), at=b(bar), dur=b(1) - 0.05)
vln.phrase(b(HIT), b(21), vel=[(0, 0.85), (1, 0.75)])
vln.note("A5", at=b(22), dur=b(2) - 0.3, vel=0.4, vibrato={"rate": 4.8, "depth": 14, "delay": 0.8})
vln.automate("volume", [(0, 0.6), (b(22), 0.6), (b(22) + 0.5, 0.5), (59.8, 0.0)])
vln.dynamics([(b(4), 1.0), (b(12), 0.9), (b(HIT) - 0.05, 1.5), (b(HIT), 1.0), (b(22), 1.0), (b(24), 0.7)])
vln.humanize(seed=15, timing=0.01, velocity=0.04)

# --- brass: the motif, low brass weight ----------------------------------------------------------
MOTIF = [("D", 0, 1.5), ("F", 1.5, 0.5), ("E", 2, 1), ("A", 3, 1), ("D", 4, 2), ("C", 6, 1), ("Bb", 7, 1)]
SWELL = [(0, 0.75), (0.6, 1.15), (1, 0.95)]      # the long notes of the motif swell
horns = track("horns", sfz=BRS + "FHornSus.sfz", legato=True, volume=0.42, pan=0.3, reverb=0.45)
for start, vel in ((6, 0.55), (10, 0.65), (HIT, 0.95), (HIT + 2, 0.95)):
    shape = vel_curve([(0, vel), (0.55, min(1.0, vel + 0.06)), (1, vel - 0.06)], b(start), b(start + 2))
    for n, at, d in MOTIF:
        t = b(start) + bt(at)
        horns.note(n + "4", at=t, dur=bt(d) + 0.06, vel=round(shape(t), 3), dynamics=SWELL if d >= 1.5 else None)
horns.humanize(seed=21, timing=0.012, velocity=0.03)
trumpets = track("trumpets", sfz=BRS + "TrumpetSus.sfz", volume=0.38, pan=0.15, reverb=0.45)
for start in (HIT, HIT + 2):
    for n, at, d in MOTIF:
        trumpets.note(n + "5" if n not in ("Bb", "C") else n + "4", at=b(start) + bt(at), dur=bt(d) - 0.03,
                      dynamics=SWELL if d >= 1.5 else None)
    trumpets.phrase(b(start), b(start + 2), vel=[(0, 0.7), (0.55, 0.76), (1, 0.64)])
trumpets.humanize(seed=22, timing=0.012, velocity=0.03)

low = track("low-brass", sfz=BRS + "TromboneSus.sfz", volume=0.75, pan=-0.05, reverb=0.35)
low.effect("eq", bands=[{"shape": "peak", "freq": 250, "gain": -3, "q": 1.0}])
tuba = track("tuba", sfz=BRS + "TubaSus.sfz", volume=0.7, pan=0.0, reverb=0.3)
for bar in BUILD:
    r, t3, f5 = chord_at(bar)
    v = 0.55 if bar < 12 else 0.7 if bar < HIT else 0.95
    inside = [(0, 0.7), (1, 1.2)] if 12 <= bar < HIT else None   # each build bar swells into the next
    low.chord([r + "3", f5 + "3"], at=b(bar), dur=b(1) - 0.08, vel=v, dynamics=inside)
    tuba.note(r + "2", at=b(bar), dur=b(1) - 0.08, vel=v, dynamics=inside)
for t in (low, tuba):
    t.dynamics([(b(12), 0.85), (b(HIT) - 0.05, 1.25), (b(HIT), 1.0)])
low.humanize(seed=23, timing=0.01, velocity=0.03)
tuba.humanize(seed=24, timing=0.01, velocity=0.03)

# --- percussion: timpani (hits and its roll articulation), kit, recorded hits ------------------
timp = track("timpani", sfz=PRC + "Timpani.sfz", articulations={"roll": PRC + "TimpaniRolls.sfz"}, volume=1.0,
             pan=0.05, reverb=0.35)
timp.note("D2", at=b(3), dur=b(1), vel=0.35, art="roll")
for bar in range(4, 22):
    if bar in range(12, HIT):
        continue
    timp.note("D2", at=b(bar), dur=bt(1), vel=0.8 if bar < HIT else 1.0)
    if bar >= 8:
        timp.note("A2", at=b(bar) + bt(2.5), dur=bt(1), vel=0.5 if bar < HIT else 0.85)
timp.note("A2", at=b(12), dur=b(HIT - 12) - 0.05, vel=0.9, art="roll")
# The roll at bar 3 sits low; the long roll swells from almost nothing into the hit.
timp.dynamics([(b(3), 0.5), (b(4) - 0.05, 0.5), (b(4), 1.0), (b(12) - 0.05, 1.0), (b(12), 0.2),
               (b(HIT) - 0.05, 0.95), (b(HIT), 1.0)])
timp.humanize(seed=31, timing=0.008, velocity=0.04)

drums = track("drums", kitSfz=KIT, volume=0.7, reverb=0.25)
for bar in BUILD:
    drums.hit("kick", at=b(bar), vel=0.8)
    drums.hit("tomLow", at=b(bar) + bt(1.5), vel=0.6)
    drums.hit("tomLow", at=b(bar) + bt(2.5), vel=0.7)
    drums.hit("tom", at=b(bar) + bt(3.5), vel=0.6)
    if bar >= HIT:
        drums.hit("snare", at=b(bar) + bt(1), vel=0.8)
        drums.hit("snare", at=b(bar) + bt(3), vel=0.85)
for i in range(16):  # the last build bar: 16ths on toms into the hit, rising along the fill
    drums.hit("tomHigh" if i % 2 else "tom", at=b(16) + bt(i * 0.25))
drums.phrase(b(16), b(16) + bt(3.75), vel=[(0, 0.5), (1, 0.95)])
drums.hit("crash", at=b(HIT), vel=1.0)
drums.hit("crash", at=b(8), vel=0.6)
drums.effect("compressor", threshold=-18, ratio=3, attack=0.005, release=0.12)
drums.humanize(seed=32, timing=0.006, velocity=0.05)

hits = track("hits", volume=0.8, reverb=0.2)
hits.clip(FS + "203119.ogg", at=0.0, volume=0.35, pan=-0.2, fadeIn=3.0, fadeOut=4.0, length=b(4) + 2)  # drone bed
hits.clip(FS + "683667.ogg", at=b(HIT) - 4.0, volume=0.6, fadeIn=1.0)   # riser into the hit
hits.clip(FS + "110218.ogg", at=b(HIT) - 3.0, volume=0.5)               # reverse crash
hits.clip(FS + "431316.ogg", at=b(HIT), volume=0.75, fadeOut=1.5)       # braam
hits.clip(FS + "428073.ogg", at=b(HIT), volume=0.7)                     # sub drop
hits.clip(FS + "430977.ogg", at=b(22) - 0.02, volume=0.45, fadeOut=3.0)  # last hit, the cut

# --- the hybrid layer P1 lacked: a quiet, dark saw pad under the build and the climax -----------
pad = track("synth-pad", synth="saw", attack=1.5, release=2.0, brightness=900, resonance=0.15, voices=5, detune=14,
            volume=0.22, pan=0.0, reverb=0.45)
for bar in range(12, 22, 2):
    r, t3, f5 = chord_at(bar)
    pad.chord([r + "3", f5 + "3", t3 + "4"], at=b(bar), dur=b(2) - 0.2, vel=0.6)
pad.dynamics([(b(12), 0.4), (b(HIT) - 0.05, 1.1), (b(HIT), 1.0), (b(21), 0.8), (b(22), 0.0)])
pad.effect("eq", bands=[{"shape": "highpass", "freq": 110, "q": 0.7}])

# --- piano: the motif bare at the start and in the release --------------------------------------
piano = track("piano", sfz=PIANO, volume=2.0, pan=-0.12, reverb=0.5)
for start, top in ((1, 0.5), (22, 0.44)):
    for n, at, d in MOTIF[:5]:
        piano.note(n + "5", at=b(start) + bt(at), dur=bt(d) + 0.4)
    piano.phrase(b(start), b(start) + bt(4), vel=[(0, top - 0.06), (0.6, top), (1, top - 0.1)])
piano.note("D4", at=b(23) + bt(2), dur=4.0, vel=0.3)
piano.effect("eq", bands=[{"shape": "highpass", "freq": 120, "q": 0.7}])
piano.humanize(seed=41, timing=0.014, velocity=0.04)

master(loudness=-16, truePeak=-1, glue=0.25)
