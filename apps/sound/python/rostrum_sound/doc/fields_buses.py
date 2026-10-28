"""Fields of the mix's routing items: buses, a track's sends to them, and a track's ducks (engine contract
`rostrum-sound-schedule/1`: buses, track `output`, `sends`, `ducks`). Merged into `fields.FIELDS` / `DEFAULTS`.

A bus id, a track's `output` and a send's `bus` point at other items; which ids are valid depends on the document,
so they are text here and `check_mix.py` checks them loudly.
"""
from __future__ import annotations

from rostrum_core import Param

from .. import names
from . import values as V

N = V.N
PAN = dict(lo=-1, hi=1, display="pan")

OUTPUT = Param.text("output", group="Mix", importance="secondary", label="Output", control="pick",   # screens: Master / the buses
                    help='Where it plays to: "master" or a bus id (the bus takes the whole track after its fader).')

ROLE = Param.choice("role", ["music", "dialogue"], group="Mix", importance="secondary", label="Role",
                    labels={"music": "Music or effects", "dialogue": "Dialogue (speech)"},
                    help='Dialogue: speech (a voice-over file, an interview). A duck with no tracks named dips under every '
                         'dialogue track, for whole lines. A voice track (it speaks lines) is dialogue already. Left out = music.')

FIELDS = {
    "bus": [
        Param.text("name", group="Group", importance="secondary"),
        V.volume("volume", "Mix", help="Bus fader gain (1 = unchanged)."), N("pan", **PAN, group="Mix"),
        Param.toggle("mute", group="Mix"),
        Param.text("output", group="Mix", importance="secondary", label="Output", control="pick",
                   help='"master" or another bus id (a bus can feed a bus, never in a loop).'),
    ],
    "send": [
        Param.text("bus", group="Send", label="Group", control="pick", help="The bus id this send feeds."),
        N("level", 0, 4, "Send", help="How much of the track goes to the bus (1 = as loud as the track).", display="db"),
        Param.toggle("pre", group="Send", importance="secondary", label="Before fader",
                     help="On: the send ignores the track's fader. Off: it follows it."),
    ],
    "duck": [
        Param.list("under", "id", group="Duck", kind="track", label="Under",
                   help="Track ids that push this track down while they sound; empty = every dialogue track "
                        '(role "dialogue", or a voice track).'),
        N("depth", 0, 1, "Duck", display="percent", help="How far it dips: 0 = not at all, 1 = silent."),
        N("attack", 0.001, 2, "Duck", "s", "secondary", help="How fast it dips."),
        N("release", 0.01, 5, "Duck", "s", "secondary", help="How fast it comes back."),
        N("hold", 0, 2, "Duck", "s", "secondary", help="How long it stays down after the others stop. Left out: "
          "0.3 s in whole-line mode (it bridges the gaps between words), else 0."),
        Param.toggle("voice", group="Duck", importance="secondary", label="Whole lines",
                     help="Dialogue mode: dips for the whole line and keeps the bass. Left out: on when every track it is "
                          "under is dialogue, else a short pump per hit. Off by hand: a pump even under speech."),
        N("lookahead", 0, 0.1, "Duck", "s", "deep", help="Starts dipping this early, so the dip lands before the sound."),
    ],
}
DEFAULTS = {
    "bus": dict(volume=1, pan=0, mute=False, output=names.MASTER_OUT),
    "send": dict(level=0.3, pre=False),
    "duck": dict(under=[], depth=0.5, attack=0.02, release=0.3, lookahead=0.01),   # voice, hold: worked out unless written (dialogue.py)
}
