"""A small song the screen opens with when no script or document is given: a synth pad, a plucked-string melody,
synth drums and,
when the file is on this machine, one recorded clip. Markers "verse" and "drop". (A starting point to look at
and play with, not a template.)"""
from rostrum_sound import settings

DOOR = settings.assets_dir() / "sounds" / "foley-h4" / "bigsoundbank" / "0015_door.ogg"

SOURCE = '''
tempo(100); beats_per_bar(4); length(bar(9))
marker("verse", at=bar(1))
marker("drop", at=bar(5))

pad = track("pad", synth="saw", attack=0.8, brightness=1800, volume=0.55)
pad.effect("reverb", space="hall", mix=0.3)
for n, chord in enumerate([["D3", "A3", "F4"], ["Bb2", "F3", "D4"], ["F3", "C4", "A4"], ["C3", "G3", "E4"]] * 2):
    pad.chord(chord, at=bar(n + 1), dur=beats(4), vel=0.6)

lead = track("melody", model="guitar", position=0.2, damping=0.1, volume=0.8)
lead.effect("eq", bands=[{"shape": "highpass", "freq": 90}])
lead.effect("delay", time=0.3, mix=0.15)
line = ["D4", "F4", "A4", "G4", "F4", "E4", "D4", "C4", "D4", "F4", "A4", "C5", "A4", "G4", "F4", "E4"]
for n, p in enumerate(line):
    lead.note(p, at=beat(16 + n * 1), dur=beats(1), vel=0.7)
lead.note("D5", at=beat(8), dur=beats(2), vel=0.6)
lead.note("C5", at=beat(10), dur=beats(2), vel=0.55)

drums = track("drums", kit="drums", volume=0.8)
for b in range(16):
    drums.hit("hat", at=beat(b * 2 + 0.5), vel=0.4)
for b in range(16, 32):
    drums.hit("kick" if b % 2 == 0 else "snare", at=beat(b))
    drums.hit("hat", at=beat(b + 0.5), vel=0.5)
'''

if DOOR.is_file():
    SOURCE += f'''
door = track("door", volume=0.9)
door.effect("compressor", threshold=-20)
door.clip(r"{DOOR}", at=7.2)
'''
