"""P5 Voice proof: two voice-over lines of our own, each placed on a named marker, over the P4 expressive cue,
the music ducking under the voice, a little room on the voice through a reverb bus. Everything is done the way a
person or an agent does it: the cue script, then operations (marker.add, track.add, line.add, duck.add, bus.add,
send.add), then make_lines (Qwen3-TTS, once per line, cached by content), then one render of the compiled document.

    .venv\\Scripts\\python.exe proofs\\sound\\voice\\voice_over.py <out folder>
(the lead runs it inside heavy.ps1's gpu slot: the voice model and the render are heavy jobs)
"""
import json
import sys
import time
from pathlib import Path

from rostrum_core import Document, Who
from rostrum_sound import KIND, compile as compile_schedule, run_source
from rostrum_sound.engine import Engine
from rostrum_sound.voice_lines import make_lines

CUE = Path(__file__).resolve().parents[1] / "cue" / "cue_expressive.py"
MUSIC = ("contrabass", "cello", "ostinato", "violins-spic", "violins", "horns", "trumpets", "low-brass", "tuba",
         "synth-pad", "piano")


def person(doc, op, target=None, **args):
    doc.apply({"op": op, **({"target": [target]} if target else {}), "args": args}, Who.person())


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
doc = Document.new(KIND, folder=str(out / "project"), item="voice-over")   # saved: the screen opens it with --doc
doc.run_script(CUE.name, run_source(CUE.read_text(encoding="utf-8"), CUE.name), Who.script(CUE.name))

person(doc, "marker.add", name="first-words", at=3.0)       # over the piano motif's first long D
person(doc, "marker.add", name="second-words", at=12.5)     # after the ostinato enters, before the horns
person(doc, "track.add", id="vo", instrument="voice", voice="ryan", language="english",
       style="low and unhurried, close to the microphone, warm, a little tired", volume=1.0)
person(doc, "line.add", "vo", text="Every city keeps one hour for itself.", at="#first-words")
person(doc, "line.add", "vo", text="This is that hour. Listen.", at="#second-words+0.25")
for t in MUSIC:
    person(doc, "duck.add", t, under=["vo"], depth=0.5, attack=0.08, release=0.6, hold=0.4, voice=True)
person(doc, "bus.add", id="room", name="Room")
person(doc, "effect.add", "room", effect="reverb")
person(doc, "send.add", "vo", bus="room", level=0.18)

doc.save()
t0 = time.perf_counter()
made = make_lines(doc)
took = time.perf_counter() - t0
schedule = compile_schedule(doc)
(out / "voice-over-schedule.json").write_text(json.dumps(schedule, indent=1), encoding="utf-8")
r = Engine().request("render", schedule=schedule, out=str(out / "voice-over-on-cue.wav"), stems=["vo"])
print(json.dumps({"lines": made, "voiceSeconds": round(took, 1), "mix": r["file"], "lufs": r["lufs"],
                  "truePeak": r["truePeak"], "ducks": r["ducks"][:3], "buses": r["buses"],
                  "vo": next(t for t in r["tracks"] if t["id"] == "vo")}, indent=1))
