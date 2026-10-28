"""A character with one swapped-out part costs the export's checks a few engine asks per time, not one per part
(showreel 2026-10-28: each failed ask was retried part by part, and a finished export sat 15 minutes in its checks)."""
from rostrum2d.mcp.edge_cut import ask_drawn


def test_an_undrawn_part_is_dropped_by_name_not_asked_part_by_part():
    parts = [f"body_{i}" for i in range(250)]
    hidden = {"body_7", "body_200"}
    asks = []

    def ask(t, ids):
        asks.append(len(ids))
        for i in ids:
            if i in hidden:
                raise ValueError(f'place: "{i}" is not drawn at this time (no such layer, hidden, out of its time or fully see-through)')
        return {i: {"w": 1, "h": 1} for i in ids}

    places = ask_drawn(ask, 1.0, parts)
    assert set(places) == set(parts) - hidden
    assert len(asks) == 3


def test_a_failure_naming_no_part_still_measures_what_is_drawn():
    def ask(t, ids):
        if len(ids) > 1 or ids == ["b"]:
            raise RuntimeError("engine said something else")
        return {ids[0]: {"w": 1, "h": 1}}

    assert set(ask_drawn(ask, 0.0, ["a", "b", "c"])) == {"a", "c"}
