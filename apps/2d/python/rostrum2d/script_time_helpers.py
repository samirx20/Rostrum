"""The script calls `marker()`, `after()` and `stagger()` (script_time.py says how times on markers work). They give
times; what they give is written as plain keys, so the document holds only normal keys.

    reveal = marker("reveal", 3)                 # "#reveal"; at may be a marker time too: marker("out", "#reveal+4")
    after(title, gap=0.2)                         # title's last key + 0.2 s ("#reveal+1.1" when it was on reveal)
    stagger(cards, every=0.5, start="#in")        # [("#in", card0), ("#in+0.5", card1), …]; floats from a number start
"""
from __future__ import annotations

from rostrum_core.marker_times import lookup, split

from . import script_time as T


def _time(build, value, where):
    """A start time as given: a Time when it names a marker (checked now), else seconds."""
    if isinstance(value, str):
        T.seconds(build, value, where)
        return T.Time(value)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{where}: {value!r} is not a time; seconds (2.5) or a marker ("#in", "#in+0.5")')
    return float(value)


def _latest(build, node: dict, base: float, own):
    """(seconds, written) of the latest key in `node` and inside it; `base`: where its plain times count from."""
    marks, best = T.times(build), None
    for k in node.get("keys", []):
        t = k["t"]
        s = T.seconds(build, t, f'{node["id"]} key') if isinstance(t, str) else base + float(t)
        got = (s, T.Time(t) if isinstance(t, str) else T.Time(own) + (s - lookup(marks, split(own)[0])) if own else s)
        best = got if best is None or got[0] > best[0] else best
    for key in T.KEYED:
        for c in node.get(key, []):
            if c.get("marker") and c["id"] not in T._state(build).time_from:
                b, o = lookup(marks, c["marker"]) or 0.0, "#" + c["marker"]
            else:
                b, o = base, own
            got = _latest(build, c, b, o)
            best = got if best is None or (got and got[0] > best[0]) else best
    return best


def helpers(build) -> dict:
    st = T._state(build)

    def marker(name, at):
        """A shared project marker named `name` at `at` (seconds or "#other+1"), published when the script has run.
        Returns "#name", a time that adds like a number."""
        if not isinstance(name, str) or not name.strip().lstrip("#").strip():
            raise ValueError(f"marker({name!r}, …): the first argument is the marker's name, words like \"reveal\"")
        name = name.strip().lstrip("#").strip()
        if split("#" + name) is None or split("#" + name)[1]:
            raise ValueError(f'marker("{name}", …): a name may not end in "+number" or "-number" (that reads as an offset)')
        if lookup(st.time_marks, name) is not None:
            raise ValueError(f'marker("{name}", …) is made twice in this script; one name is one marker')
        at = T.seconds(build, at, f'marker("{name}") at')
        if at < 0:
            raise ValueError(f'marker("{name}", {at:g}): a marker sits at 0 s or later')
        st.time_marks[name] = round(at, 6)
        return T.Time("#" + name)

    def after(item, gap=0.0):
        """When `item`'s last key lands (its start when it has none) + `gap` seconds: a marker time when that key or
        the item is on a marker, so it moves with the marker; else seconds."""
        node = getattr(item, "node", None)
        if node is None:
            raise ValueError(f"after({item!r}): give an item the script made (text(…), layer(\"id\"))")
        marks, ours = T.times(build), st.time_from.get(node["id"])
        if ours is not None:
            base, own = 0.0, "#" + node["marker"]
        elif node.get("marker"):
            base, own = lookup(marks, node["marker"]) or 0.0, "#" + node["marker"]
        else:
            base, own = 0.0, None
        got = _latest(build, node, base, own)
        if got is None:                                          # no keys: its entrance
            start = float(node.get("start", 0.0))
            got = (None, T.Time(own) + start if own else start)
        return got[1] + float(gap)

    def stagger(items, every=0.1, start=0.0):
        """[(time, item), …]: the first at `start`, each next `every` seconds later (marker times when start is one)."""
        t0 = _time(build, start, "stagger(start=…)")
        return [(t0 + round(i * float(every), 6) if isinstance(t0, T.Time) else round(t0 + i * float(every), 6), it)
                for i, it in enumerate(items)]

    return {"marker": marker, "after": after, "stagger": stagger}
