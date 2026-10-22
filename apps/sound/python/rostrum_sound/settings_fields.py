"""The person's RostrumSound settings as field data: the same Param format the inspector is built from, so the
Settings page is `rows.layout(FIELDS)` / `rows.evaluate(...)` and an agent sets one with the same checks.

Device fields are "pick" texts ("" = Windows' default): what may be picked depends on this machine, so the page
fills them from `settings.choices(name)`. Folder fields hold a path; "" means the default shown in the help.
"""
from __future__ import annotations

import os
from pathlib import Path

from rostrum_core import Operation, Param

DEVICE, FILES, SONGS = "Sound device", "Files", "New songs"
BUFFERS = [0, 3, 5, 10, 20, 40]
RATES = [44100, 48000, 96000]
PROJECTS = Path.home() / "Documents" / "Rostrum Sound"
MODELS = Path.home() / ".rostrum" / "models"


def _set(**values):
    from . import settings
    for name, value in values.items():
        settings.set(name, value)


PARAMS = [
    Param.text("output", group=DEVICE, label="Speakers", control="pick", default="",
               help="Where you hear the song. Empty: whatever Windows uses as its default output."),
    Param.text("input", group=DEVICE, label="Microphone", control="pick", default="",
               help="What records a voice or an instrument. Empty: Windows' default microphone."),
    Param.toggle("exclusive", group=DEVICE, importance="secondary", label="Take over the speakers", default=False,
                 help="On: RostrumSound alone uses the speakers, for the shortest delay between a key and its sound. "
                      "Other programs go quiet while it plays. Off: it shares them with everything else."),
    Param.choice("buffer", BUFFERS, group=DEVICE, importance="secondary", label="Buffer", default=0,
                 valid_when={"is": ["exclusive", True]},
                 labels={0: "Automatic", **{b: f"{b} ms" for b in BUFFERS[1:]}},
                 help="How much sound is prepared ahead when it takes over the speakers. Shorter: a key sounds sooner, "
                      "but a slow machine may crackle. Automatic finds the shortest that plays cleanly and lengthens "
                      "it if the machine falls behind. A fixed buffer stays as set."),
    Param.choice("sampleRate", RATES, group=SONGS, label="Sample rate", default=48000,
                 labels={44100: "44.1 kHz (music CDs)", 48000: "48 kHz (video)", 96000: "96 kHz"},
                 help="How finely a new song's sound is stored. 48 kHz suits video; a song keeps its own once made."),
    Param.number("loudness", group=SONGS, label="Loudness target", default=-14, min=-30, max=-5, step=0.5,
                 unit=" LUFS", help="How loud a new song is made when you export it with loudness matching. "
                                    "-14 suits streaming sites; -23 is broadcast TV."),
    Param.number("truePeak", group=SONGS, importance="secondary", label="Peak ceiling", default=-1, min=-12, max=0,
                 step=0.1, unit=" dBTP", help="The loudest any moment of a new song may reach, so it never distorts "
                                              "after a video site re-encodes it."),
    Param.text("projects", group=FILES, label="Projects folder", control="folder", default="",
               help=f"Where new projects are made. Empty: {PROJECTS}"),
    Param.text("models", group=FILES, importance="deep", label="AI models folder", control="folder", default="",
               help=f"Where the voice and clean-up models are kept. Empty: {MODELS}"),
    Param.text("engine", group=FILES, importance="deep", label="Sound engine program", control="file",
               filters=["Programs (*.exe)"] if os.name == "nt" else [], default="",
               help="The rostrum-sound program to use. Empty: found automatically (the one installed with the app)."),
]

FIELDS = Operation("settings.set", "Change RostrumSound's settings.", _set, None, PARAMS, "Settings",
                   fields=True)
DEFAULTS = {p.name: p.default for p in PARAMS}
