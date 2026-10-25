"""`track.feel`: change some of a track's performance feel (its `perform` field, perform.py) and keep the rest. It
merges: only the values named change, `null` removes one (back to the instrument family's default), so an agent
setting swing never wipes a person's looseness (AGENTS.md rule 3). `track.set {perform}` still writes the whole object.
An absent or `true` perform starts from {}; `false` (everything as written) starts from {"person": false}.
"""
from __future__ import annotations

import dataclasses

from rostrum_core import codes
from rostrum_core.edits import MISSING

from . import perform as PF
from . import values as V
from .playing import PLAYED
from .registry import REGISTRY

# (field, label, importance): the Feel group's words, most used first.
SHOWN = [("swing", "Swing", "primary"), ("swingGrid", "Swing on", "secondary"), ("person", "Played like a person", "primary"),
         ("timing", "Looseness", "secondary"), ("velocity", "Velocity spread", "secondary"), ("lean", "Lean", "secondary"),
         ("accent", "Accent", "secondary"), ("strum", "Strum", "secondary"), ("articulation", "Articulation", "secondary"),
         ("vibrato", "Vibrato", "secondary"), ("seed", "Seed", "secondary")]


def _vibrato_rule(p, v, where):
    return False if v is False else PF.BY["vibrato"].rule(p, v, where)


def _param(name, label, importance):
    p = PF.BY[name]
    kw = dict(nullable=True, required=False, importance=importance, group="Feel", label=label,
              help=p.help + " null = back to the instrument's default.")
    if name == "vibrato":
        kw.update(rule=_vibrato_rule, schema={"anyOf": [*p.schema.get("anyOf", [p.schema]), {"const": False}]})
    return dataclasses.replace(p, **kw)


PARAMS = [_param(*s) for s in SHOWN]


def merged(old, args: dict) -> dict:
    """The track's new perform object: `old` (absent / true / false / an object) with `args` merged in."""
    base = {} if old in (None, True) else {"person": False} if old is False else dict(old)
    for k, v in args.items():
        if v is None:
            base.pop(k, None)
        else:
            base[k] = v
    return base


@REGISTRY.operation("track.feel", "Change how a notes or drums track is played, keeping its other feel settings: "
                    "swing (0 … 1, 1 = triplet) on swingGrid (0.5 = 8ths, 0.25 = 16ths), person (false = the instrument's "
                    "looseness off, swing still plays), timing (ms), velocity, lean (ms), accent, strum, articulation, "
                    "vibrato, seed. Only the values named change; null puts one back to the instrument's default. "
                    "Played, never written into the notes.", target="track", params=PARAMS, label="Feel",
                    valid_when=PLAYED)
def feel(ctx, targets, args):
    if not args:
        ctx.fail(codes.BAD_ARGUMENT, "arguments", "name nothing to change", [p.name for p in PARAMS])
    for t in targets:
        new = merged(ctx.item(t).get("perform"), args)
        ctx.set(t, "perform", new if new else MISSING)
