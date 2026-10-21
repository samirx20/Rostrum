"""The new way: designed sounds shaped by the picture's motion, glued on one "ui" bus.

    python score_new.py [samples.json] [out.wav]

Reads the 2D motion samples (sample_motion.py), turns every event into designed sounds (rostrum_sound.motion), writes
them as a Sound script (so an agent or a person edits the same items afterwards), adds the glue bus, renders.
"""
import json
import sys
from pathlib import Path

from rostrum_core import Document, Who
from rostrum_sound import KIND, compile as compile_schedule, run_source
from rostrum_sound.engine import Engine
from rostrum_sound.motion import read, score

SCRATCH = Path(r"C:\Users\Sam\.rostrum\waves\scratch\priyam-P6-lead")
RESULTS = Path(r"C:\Users\Sam\.rostrum\waves\results\stage2\sound-motion")


def main() -> None:
    src_path = Path(sys.argv[1]) if len(sys.argv) > 1 else SCRATCH / "samples.json"
    wav = Path(sys.argv[2]) if len(sys.argv) > 2 else RESULTS / "slides-new-sfx.wav"
    samples = json.loads(src_path.read_text(encoding="utf-8"))
    evs = read.events(samples)
    body, tracks = score.script(evs, samples["width"], samples["height"])
    source = "\n".join([f"length({samples['duration'] + 1.0!r})", body,
                         "master(loudness=-16); master.effect('limiter', ceiling=-1)"])
    (SCRATCH / "new_sfx_script.py").write_text(source, encoding="utf-8")
    (SCRATCH / "new-events.json").write_text(json.dumps(evs, indent=1), encoding="utf-8")

    doc = Document.new(KIND, folder=str(SCRATCH / "sound-doc"), item="slides-new-sfx")
    doc.run_script("new_sfx.py", run_source(source, "new_sfx.py"), Who.script("score_new.py"))
    doc.apply(score.glue_ops(doc.data, tracks), Who.script("score_new.py"), label="UI glue bus")
    doc.save()
    with Engine() as eng:
        r = eng.request("render", schedule=compile_schedule(doc), out=str(wav))
        # The sharp sounds alone, for the sync check (in the mix a whoosh's swell can hide a click's onset from the
        # onset tool, not from the ear).
        sharp = [t for t in tracks if t != score.TRACKS["move"]]
        eng.request("render", schedule=compile_schedule(doc, solo=sharp), out=str(SCRATCH / "sharp-only.wav"))
    print(json.dumps({"events": len(evs), "sounds": body.count(".sound("), "file": r["file"], "lufs": r["lufs"],
                      "truePeak": r["truePeak"]}))


if __name__ == "__main__":
    main()
