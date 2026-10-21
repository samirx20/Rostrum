"""The "old way": one stock library take dropped on every move, no panning, no variation.

    python score_old.py [motion.json] [out.wav]

Reads the 2D motion facts (look_motion output), places the same whoosh at the start of every card move, the same click
at the title snap, a tick per counter step and a click at the button tap; renders one WAV at about -16 LUFS and writes
the event list (with times) next to it.
"""
import json
import sys
from pathlib import Path

from rostrum_core import Document, Who
from rostrum_sound import KIND, compile as compile_schedule, run_source
from rostrum_sound.engine import Engine

LIB = Path.home() / ".rostrum" / "assets" / "sounds"
WHOOSH = LIB / "freesound" / "171321.ogg"                      # "Fast Swoosh"
# The take is silent for its first 0.95 s: trimmed there, as an agent placing it by hand would, so the comparison is
# the sound itself, not a placement mistake.
TRIM = {WHOOSH: 0.95}
CLICK_TITLE = LIB / "kenney-interface" / "Audio" / "click_002.ogg"
TICK = LIB / "kenney-interface" / "Audio" / "tick_004.ogg"
CLICK_BUTTON = LIB / "kenney-ui" / "Audio" / "mouseclick1.ogg"

SCRATCH = Path(r"C:\Users\Sam\.rostrum\waves\scratch\priyam-P6-slides")
RESULTS = Path(r"C:\Users\Sam\.rostrum\waves\results\stage2\sound-motion")


def events(facts: dict) -> list[dict]:
    """One event per thing that moves: (time, kind, layer, stock take)."""
    out = []
    for lay in facts["layers"]:
        for m in lay["moves"]:
            i = lay["id"]
            if m["field"] in ("x", "y"):
                out.append({"t": m["start"], "layer": i, "kind": "move", "take": WHOOSH})
            elif i == "title" and m["field"] == "scale":
                out.append({"t": m["start"], "layer": i, "kind": "snap", "take": CLICK_TITLE})
            elif i.startswith("counter_") and m.get("jumps_at") is not None and m["to"] == 1:
                out.append({"t": m["jumps_at"], "layer": i, "kind": "step", "take": TICK})
            elif i == "button" and m["field"] == "scale" and m["to"] < 1:
                out.append({"t": m["start"], "layer": i, "kind": "tap", "take": CLICK_BUTTON})
    return sorted(out, key=lambda e: e["t"])


def main() -> None:
    motion = Path(sys.argv[1]) if len(sys.argv) > 1 else SCRATCH / "slides-motion.json"
    wav = Path(sys.argv[2]) if len(sys.argv) > 2 else RESULTS / "slides-old-sfx.wav"
    facts = json.loads(motion.read_text(encoding="utf-8"))
    evs = events(facts)
    for e in evs:
        if not e["take"].is_file():
            raise SystemExit(f"stock take missing: {e['take']}")
    src = ["tempo(120); length(%r)" % round(facts["time"]["duration"] + 1.0, 2)]
    for n, kind in enumerate(("move", "snap", "step", "tap")):
        src.append("t%d = track(%r)" % (n, "old_" + kind))
        for e in (e for e in evs if e["kind"] == kind):
            src.append("t%d.clip(r%r, at=%r, in_=%r)" % (n, str(e["take"]), e["t"], TRIM.get(e["take"], 0.0)))
    src.append("master(loudness=-16); master.effect('limiter', ceiling=-1)")
    source = "\n".join(src)
    (SCRATCH / "old_sfx_script.py").write_text(source, encoding="utf-8")

    folder = SCRATCH / "sound-doc"
    doc = Document.new(KIND, folder=str(folder), item="slides-old-sfx")
    doc.run_script("old_sfx.py", run_source(source, "old_sfx.py"), Who.script("score_old.py"))
    doc.save()
    wav.parent.mkdir(parents=True, exist_ok=True)
    with Engine() as eng:
        r = eng.request("render", schedule=compile_schedule(doc), out=str(wav))
    print(json.dumps({"events": len(evs), "file": r["file"], "lufs": r["lufs"], "truePeak": r["truePeak"]}))
    (SCRATCH / "old-events.json").write_text(
        json.dumps([{**e, "take": str(e["take"])} for e in evs], indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
