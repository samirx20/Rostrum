"""Scripted steps for the Timeline's view, automation lanes and picture (called from steps.py):

    zoom <factor> [<where 0..1>] | scroll <seconds> | fit
    lane <track> <lane> [<item id>] | lane <track> off        (the lane under the track's row; a send: its id)
    lane-point <track> <t s> <value> [<t2 s> <value2>]        (press there: grab or add a point; drag to the second spot)
    lane-delete                                               (the selected point)
    picture <video file> | picture none
    fold <group id> | fold all                                (a group's fold arrow; Alt+click = all)
    vel-fold                                                  (the velocity strip's fold arrow)
    play-lane <sustain|dynamics|bend>                         (the Editor's playing lane chip)
    group-drop <track id> <row id>                            (drag a track header onto that row: into / out of a group)
    group-toggle <group id> mute|solo                         (M / S on a group's header)
"""
from __future__ import annotations

WORDS = ("zoom", "scroll", "fit", "lane", "lane-point", "lane-delete", "picture", "fold", "vel-fold", "play-lane", "group-drop", "group-toggle")


def do_view_step(bridge, word, rest):
    if word == "zoom":
        bridge.zoomAt(float(rest[0]), float(rest[1]) if len(rest) > 1 else 0.5)
    elif word == "scroll":
        bridge.setViewStart(bridge.viewStart + float(rest[0]))
    elif word == "fit":
        bridge.fitView()
    elif word == "lane":
        off = rest[1] == "off"
        bridge.openLane(rest[0], "" if off else (rest[2] if len(rest) > 2 else rest[0]), "" if off else rest[1])
    elif word == "lane-point":
        point(bridge, rest[0], *map(float, rest[1:]))
    elif word == "lane-delete":
        bridge.removeSelected()
    elif word == "vel-fold":
        bridge.toggleVelocityFold()
    elif word == "play-lane":
        bridge.openPlayLane(rest[0])
    elif word == "group-drop":
        bridge.dropTracks([rest[0]], rest[1])
    elif word == "group-toggle":
        bridge.toggleGroupMS(rest[0], rest[1])
    elif word == "fold":
        bridge.toggleFold("" if rest[0] == "all" else rest[0], rest[0] == "all")
    elif word == "picture":
        bridge.setPicture("" if rest[0] == "none" else " ".join(rest))


def point(bridge, track, t, v, t2=None, v2=None):
    """One press (and a drag, when a second spot is given) on the open lane, as the mouse does it."""
    a = next(r for r in bridge.tracks if r["id"] == track)["auto"]
    if a is None:
        raise RuntimeError(f"lane-point: no lane is open on {track!r} (use: lane {track} <lane>)")

    def y(value):
        return 1 - (value - a["lo"]) / (a["hi"] - a["lo"])
    bridge.laneBegin(track, a["target"], a["lane"], t, y(v), 0.15, 0.1, False)
    if t2 is not None:
        for f in (0.25, 0.5, 0.75, 1.0):
            bridge.laneDrag(t + (t2 - t) * f, y(v + (v2 - v) * f), False)
    bridge.endDrag()
