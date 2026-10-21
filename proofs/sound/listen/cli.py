"""Command line: python -m listen <cmd> <wav> [...]  (run from proofs/sound/)."""
import argparse
import json
import sys


def floats(s):
    return [float(x) for x in s.split(",") if x.strip()]


def build():
    p = argparse.ArgumentParser(prog="listen", description="Ears for agents: WAV -> facts and pictures (JSON on stdout).")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("loudness", help="LUFS, true peak, LRA, short-term curve, clipping").add_argument("wav")
    s = sub.add_parser("spectrogram", help="log-frequency spectrogram PNG")
    s.add_argument("wav"); s.add_argument("--png", required=True)
    s.add_argument("--marks", type=floats, default=[], help="times (s) to draw lines at")
    s.add_argument("--mel", action="store_true", help="mel scale instead of log-frequency")
    o = sub.add_parser("onsets", help="onset times, tempo, beats, energy curve")
    o.add_argument("wav"); o.add_argument("--expect", type=floats, default=[], help="expected event times (s)")
    for name, h in (("bands", "energy per band per section"), ("stereo", "L/R correlation and width per section")):
        b = sub.add_parser(name, help=h)
        b.add_argument("wav"); b.add_argument("--section", type=float, default=5.0, help="section length (s)")
    lv = sub.add_parser("levels", help="per-stem levels and who dominates")
    lv.add_argument("stems", nargs="+"); lv.add_argument("--mix")
    lv.add_argument("--section", type=float, default=5.0)
    lv.add_argument("--buried-db", type=float, default=15.0, help="gap that counts as buried (dB)")
    c = sub.add_parser("compare", help="two files side by side")
    c.add_argument("a"); c.add_argument("b"); c.add_argument("--png", required=True)
    r = sub.add_parser("report", help="loudness + spectrogram + onsets + bands + stereo in one call")
    r.add_argument("wav"); r.add_argument("--dir", required=True); r.add_argument("--section", type=float, default=5.0)
    return p


def run(a):
    if a.cmd == "loudness":
        from . import loudness; return loudness.analyse(a.wav)
    if a.cmd == "spectrogram":
        from . import spectro; return spectro.make(a.wav, a.png, a.marks, a.mel)
    if a.cmd == "onsets":
        from . import onsets; return onsets.analyse(a.wav, a.expect)
    if a.cmd == "bands":
        from . import bands; return bands.analyse(a.wav, a.section)
    if a.cmd == "stereo":
        from . import stereo; return stereo.analyse(a.wav, a.section)
    if a.cmd == "levels":
        from . import levels; return levels.analyse(a.stems, a.mix, a.section, a.buried_db)
    if a.cmd == "compare":
        from . import compare; return compare.analyse(a.a, a.b, a.png)
    from . import report; return report.analyse(a.wav, a.dir, a.section)


def main(argv=None):
    a = build().parse_args(argv)
    try:
        res = run(a)
    except Exception as e:  # fail loudly: message on stderr, non-zero exit
        print(f"listen {a.cmd} failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(json.dumps(res, separators=(",", ":")))
    return 0
