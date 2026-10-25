# `rostrum_sound`: RostrumSound's Python layer

The Sound document (items and operations on `rostrum_core`), its script layer for `run_script`, and the compiler to
the engine's schedule (`../ENGINE_CONTRACT.md`, `rostrum-sound-schedule/1`). Listening tools: `listen/`, `sfx/`.

## Install and test

```
uv pip install --python C:\Users\Sam\.t3\worktrees\Rostrum\team-priyam\.venv\Scripts\python.exe -e "apps\sound\python[test]"
C:\Users\Sam\.t3\worktrees\Rostrum\team-priyam\.venv\Scripts\python.exe -m pytest -q apps\sound\python\tests\test_sound_doc.py
```

Extras: `listen` (numpy, scipy, soundfile, librosa, pyloudnorm, matplotlib, opencv), `mcp`, `test`.

## Modules

| Module | Does |
|---|---|
| `names` | every accepted name (tones, spaces, EQ shapes, built-ins, kits, drums). The engine's `describe` is the authority |
| `doc/times` | times: seconds, `{"beat": n}`, `"#drop"`, `"#drop+0.5"`; lengths: seconds, `{"beats": n}`; marker resolution |
| `doc/values` | Params for times, lengths, pitches, drums, envelopes and lists |
| `doc/effects` | each effect type's fields, defaults and ranges (contract § Effects) and their Params |
| `doc/fields` | each item type's Params (importance, `valid_when`) and what a new item stores |
| `doc/ids` | content ids: `pad.n1500`, `drums.kick0`, `door.c3000`, `pad.eq_1`, `pad.auto_volume`, `marker.drop` |
| `doc/registry` | the one operation list and where items live |
| `doc/ops_tracks`, `ops_timed`, `ops_mix` | the operations |
| `doc/check` | the whole-document check (instruments, drums, automation order, marker references, effect ranges) |
| `doc/kind` | `KIND`: the document kind (`.trk`) |
| `builder`, `script` | the script layer: Python source -> document tree |
| `compile` | document -> schedule dict (`solo=`, `mute=`, `master=`) |

## The document

```
root (tempo, length, beatsPerBar, sampleRate)
  tracks[]  track (instrument, volume, pan, reverb, tone, mute, solo)
              notes[] hits[] clips[] (clip: effects[]) effects[] automation[]
  markers[] marker (name, at)
  master[]  the one master, id "master" (volume, normalize, loudness, truePeak, glue, spaces, fades)
              effects[] automation[]
```

Operations: `doc.set`, `track.add/set/remove`, `note.add/add_many/set/remove`, `hit.add/add_many/set/remove`,
`clip.add/set/remove`, `effect.add/set/remove/move` (on a track, clip or the master; `effect.move {to}` reorders a chain), `track.move {by | after}`, `track.set {sound}` (changes a track's sound, keeping its notes: doc/sounds.py), `automation.set` (replace a lane;
empty points remove it), `marker.add/set/remove`, `master.set`.

## Script API

```python
tempo(96); length(bar(9)); beats_per_bar(4)         # bar(1) is the start of the song
marker("drop", at=bar(5))
s = track("strings", sfz=r"C:\...\Violins.sfz", volume=0.8)   # instrument from sfz= / builtIn= / kit= / kitSfz=
s.note("D4", at=beat(0), dur=beats(4), vel=0.7)
s.chord(["D3", "A3", "F4"], at="#drop", dur=beats(2))
d = track("drums", kit="synth"); d.hit("kick", at=beat(0)); d.hit("snare", at="#drop+0.5")
v = track("door"); v.clip(r"C:\...\door.wav", at=3.0, in_=0.42, length=1.2).effect("eq", bands=[{"shape": "highpass", "freq": 80}])
s.effect("reverb", space="hall", mix=0.3)
s.automate("volume", [(0, 0.2), ("#drop", 0.9)])
master(loudness=-16)                                 # a loudness target turns normalize on
master.effect("limiter", ceiling=-1)
```

Every name and value is checked by the operations' own Params; an unknown one fails with the script's line. The
same script gives the same ids every run, so a re-run merges and keeps what a person changed.

```python
from rostrum_core import Document, Who
from rostrum_sound import KIND, compile, run_source
doc = Document.new(KIND)
doc.run_script("cue.py", run_source(source, "cue.py"), Who.script("cue.py"))
schedule = compile(doc, solo=["strings"])
```
