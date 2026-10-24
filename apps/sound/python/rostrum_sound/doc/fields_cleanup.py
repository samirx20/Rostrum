"""A clip's cleanup fields (group "Cleanup"): what the cleaned take is made of (`cleanup/`, CLEANUP.md) and whether
the clip plays it. The clip keeps its original `media`; compile plays the cleaned take while `useCleaned` is on.

`useCleaned` shows only while a step is set, and `isolate` is absent while a stem is chosen (a stem already
separates). Both are conditions on the clip's own fields, so a call that sets a step and `useCleaned` together is
valid. They mirror `cleanup.recipe_of` (a stem, isolate on, denoise / dereverb above 0).
"""
from __future__ import annotations

from rostrum_core import Param

from ..cleanup import STEMS
from . import values as V

N = V.N
NO_STEM = "none"
STEM_CHOSEN = {"any": [{"is": ["stem", s]} for s in STEMS], "say": ["a stem is chosen", "no stem is chosen (Play one stem is Whole clip)"]}


def _amount_on(name):
    """A 0..1 step that is on: set and not 0 (a clip saved before these fields had none)."""
    return {"all": [{"not": {"is": [name, 0]}}, {"not": {"is": [name, None]}}]}


HAS_CLEANUP = {"any": [STEM_CHOSEN, {"is": ["isolate", True]}, _amount_on("denoise"), _amount_on("dereverb")]}

PARAMS = [
    Param.choice("stem", (NO_STEM, *STEMS), group="Cleanup", importance="secondary", label="Play one stem",
                 labels={NO_STEM: "Whole clip"},
                 help="Play one stem of this clip: the voice, drums, bass or everything else, separated from the rest."),
    Param.toggle("isolate", group="Cleanup", importance="secondary", label="Dialogue only",
                 valid_when={"not": STEM_CHOSEN},
                 help="The voice separated from music and effects; the rest is left out."),
    N("denoise", 0, 1, "Cleanup", imp="secondary", label="Less noise", display="percent",
      help="Takes out steady background noise (hiss, hum, room tone); 0 = off."),
    N("dereverb", 0, 1, "Cleanup", imp="secondary", label="Less echo", display="percent",
      help="Takes out the room's echo; 0 = off."),
    Param.toggle("useCleaned", group="Cleanup", label="Use cleaned take", valid_when=HAS_CLEANUP,
                 help="Play the cleaned take (made once with the render_cleanup tool); off = the original file."),
]
# What a new clip stores, so valid_when reads real values.
DEFAULTS = dict(stem=NO_STEM, isolate=False, denoise=0, dereverb=0, useCleaned=True)
