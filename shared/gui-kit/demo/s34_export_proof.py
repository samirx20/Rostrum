"""Proof (S34): the kit's Export sheet in both apps, from the screen, read back from the files.

For each app, offscreen, in a scratch project: open the Export sheet, pick what it is for, Browse to a scratch folder,
press Export (the sheet's own flow: a background job, Keep both if a file is already there), take a picture of the
window with the sheet open at 1646x900, then READ THE FILE BACK:
  2D   MP4: ffprobe (size, frames, duration); PNG frames: the frame count and a frame's size
  Sound WAV at the Streaming target: its length, rate and measured loudness / loudest peak (must pass −14 ±1, ≤ −1 dBTP)
and that the export marked a version ("Exported v001") in the document. Exits nonzero on any failure.

    python shared/gui-kit/demo/s34_export_proof.py
Exports are heavy: run it through the lock (heavy.ps1 run "sam: s34 export proof" gpu …). Output:
C:\\Users\\Sam\\.rostrum\\waves\\results\\kit\\s34\\export\\ (proof.txt and the pictures). Scratch: C:\\Users\\Sam\\.rostrum\\scratch\\s34-export\\.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRATCH = Path(r"C:\Users\Sam\.rostrum\scratch\s34-export")
OUT = Path(r"C:\Users\Sam\.rostrum\waves\results\kit\s34\export")
ENGINES = {"ROSTRUM2D_ENGINE": r"C:\Users\Sam\Documents\CODE\Rostrum\apps\2d\engine\target\agent\rostrum2d-render.exe",
           "ROSTRUM_SOUND_ENGINE": r"C:\Users\Sam\Documents\CODE\Rostrum\apps\sound\engine\target\agent\rostrum-sound.exe"}
KIT_QML = ("ExportSheet.qml", "JobChip.qml", "ProblemsChip.qml", "TopBar.qml", "AppShell.qml", "ExportSettings.qml")
for p in ("shared/core", "shared/gui-kit", "apps/2d/python", "apps/sound/python"):
    sys.path.insert(0, str(ROOT / p))

lines: list[str] = []
failed: list[str] = []
sys.stdout.reconfigure(encoding="utf-8", errors="replace")      # "−14 LUFS" on a cp1252 console


def say(text=""):
    print(text, flush=True)
    lines.append(text)


def check(ok, what):
    say(f"  {'ok  ' if ok else 'FAIL'} {what}")
    if not ok:
        failed.append(what)


def run_app(app, args, steps, shot):
    """The app's own window, offscreen, through its scripted steps; its words back. A crash or a step that fails is a
    failure (the app exits nonzero)."""
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QPA_FONTDIR": "C:/Windows/Fonts", "PYTHONFAULTHANDLER": "1"}
    for k, v in ENGINES.items():
        env.setdefault(k, v)
    cmd = [sys.executable, str(ROOT / "apps" / app / "screen" / "main.py"), *args, "--size", "1646x900"]
    for s in steps:
        cmd += ["--step", s]
    cmd += ["--shot", str(shot)]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    say(f"  ran {app} in {time.time() - t0:.0f} s, exit {p.returncode}")
    for ln in (p.stdout + p.stderr).splitlines():
        if ln.strip():
            say(f"    | {ln[:300]}")
    warnings = [ln for ln in p.stderr.splitlines() if "QML" in ln and any(f in ln for f in KIT_QML)]
    check(p.returncode == 0, f"{app}: the window ran every step and saved its picture")
    check(not warnings, f"{app}: no QML warnings from the Export sheet, the chips or the top bar")
    check(shot.is_file(), f"{app}: picture {shot}")


def newest(folder: Path, pattern):
    found = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime)
    return found[-1] if found else None


def ffprobe(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                        "stream=codec_name,width,height,nb_read_frames,avg_frame_rate:format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {p.stderr.strip()}")
    j = json.loads(p.stdout)
    return {**j["streams"][0], "duration": float(j["format"]["duration"])}


def versions(folder, item, kind):
    from rostrum_core import Document
    return Document.open(folder, item, kind).versions()


def two_d():
    from rostrum2d import KIND
    say("\n== Rostrum2D ==")
    proj, out = SCRATCH / "2d project", SCRATCH / "2d out"
    out.mkdir(parents=True)
    doc = ["--doc", str(proj), "main", "--sample"]
    run_app("2d", doc, ["exportsheet open mp4", f"exportwhere {out}", "exportnow both"], OUT / "2d-mp4-sheet.png")
    mp4 = newest(out, "*.mp4")
    check(mp4 is not None, f"2D MP4 written into {out}")
    if mp4:
        f = ffprobe(mp4)
        say(f"  readback {mp4.name}: {f['codec_name']} {f['width']}x{f['height']}, {f['nb_read_frames']} frames at "
            f"{f['avg_frame_rate']}, {f['duration']:.3f} s, {mp4.stat().st_size} bytes")
        check(int(f["nb_read_frames"]) > 0 and f["width"] > 0 and f["duration"] > 0, "2D MP4 has frames, a size and a length")
    run_app("2d", doc, ["exportsheet open png", f"exportwhere {out}", "exportnow both"], OUT / "2d-png-sheet.png")
    seq = newest(out, "*/")
    pngs = sorted(seq.glob("*.png")) if seq else []
    check(len(pngs) > 0, f"2D PNG frames written into {seq}")
    if pngs:
        from PySide6.QtGui import QImage
        img = QImage(str(pngs[0]))
        say(f"  readback {seq.name}: {len(pngs)} frames, first {pngs[0].name} {img.width()}x{img.height()}"
            f"{' with transparency' if img.hasAlphaChannel() else ''}")
        check(not img.isNull() and img.width() > 0, "2D PNG frame reads back as a picture")
    v = versions(str(proj), "main", KIND)
    say(f"  versions in the document: {sorted(v)}")
    check(sum(1 for k in v if k.startswith("Exported v")) >= 2, "2D: each export marked a version (Exported v…)")


def sound():
    import soundfile
    from rostrum_sound import KIND
    from rostrum_sound.listen.loudness import loudness
    say("\n== RostrumSound ==")
    proj, out = SCRATCH / "sound project", SCRATCH / "sound out"
    out.mkdir(parents=True)
    run_app("sound", ["--doc", str(proj), "song", "--sample"],
            ["exportsheet open streaming", "export-as wav24 48000", f"exportwhere {out}", "exportnow both"],
            OUT / "sound-wav-sheet.png")
    wav = newest(out, "*.wav")
    check(wav is not None, f"Sound WAV written into {out}")
    if wav:
        i = soundfile.info(str(wav))
        m = loudness(str(wav))
        say(f"  readback {wav.name}: {i.samplerate} Hz, {i.channels} channels, {i.subtype}, {i.frames} samples = "
            f"{i.duration:.3f} s; loudness {m['integrated_lufs']} LUFS, loudest peak {m['true_peak_dbtp']} dBTP, "
            f"{m['clipped_samples']} clipped samples")
        check(i.samplerate == 48000 and i.duration > 1, "Sound WAV is 48 kHz and has the song's length")
        check(abs(m["integrated_lufs"] - (-14)) <= 1.0, "Sound WAV meets Streaming: −14 LUFS ±1")
        check(m["true_peak_dbtp"] <= -1 + 0.3, "Sound WAV's loudest peak is under −1 dBTP (0.3 dB measuring margin)")
    v = versions(str(proj), "song", KIND)
    say(f"  versions in the document: {sorted(v)}")
    check(any(k.startswith("Exported v") for k in v), "Sound: the export marked a version (Exported v…)")


def main():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)          # our own scratch only
    SCRATCH.mkdir(parents=True)
    OUT.mkdir(parents=True, exist_ok=True)
    say(f"S34 export proof, {time.strftime('%Y-%m-%d %H:%M')}; scratch {SCRATCH}")
    for part in (two_d, sound):
        try:
            part()
        except Exception as e:  # noqa: BLE001  one app's failure is reported, the other still runs
            check(False, f"{part.__name__}: {type(e).__name__}: {e}")
    say(f"\n{'PASS' if not failed else 'FAIL: ' + '; '.join(failed)}")
    (OUT / "proof.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written {OUT / 'proof.txt'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
