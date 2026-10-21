"""TEST SEAM, never used for real recording: speaks the engine's `record` lines (ready / level / done, stop on a
stdin line) from a WAV file instead of a microphone, so the screen's recording can be checked without one.

    python fake_mic.py <out.wav> <source.wav>
"""
import json
import shutil
import sys
import threading
import time

import numpy as np
import soundfile as sf


def say(**kw):
    print(json.dumps(kw), flush=True)


def main(out, source):
    data, rate = sf.read(source, always_2d=True, dtype="float32")
    mono = np.abs(data).max(axis=1)
    stop = threading.Event()

    def listen():
        for line in sys.stdin:
            if line.strip() == "stop":
                break
        stop.set()

    threading.Thread(target=listen, daemon=True).start()
    say(ready={"rate": rate, "channels": 1, "device": "fake"})
    step, t = rate // 10, 0
    while not stop.is_set():
        chunk = mono[(t * step) % len(mono):][:step]
        say(level={"t": (t + 1) / 10, "peakDb": round(20 * np.log10(max(float(chunk.max()) if len(chunk) else 0, 1e-6)), 1)})
        t += 1
        time.sleep(0.1)
    shutil.copy(source, out)
    say(done={"file": out, "seconds": t / 10, "peakDb": 0.0})


if __name__ == "__main__":
    main(*sys.argv[1:3])
