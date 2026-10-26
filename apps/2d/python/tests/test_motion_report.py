"""look_motion's findings stay readable on a busy scene: identical findings are one line with a count, the ones that
matter first, the rest behind a cap; a key on the composition's last moment is reached."""
from rostrum2d.mcp import motion_report as R
from rostrum2d.mcp.motion_checks import dead_keys


def _overlap(a, b):
    return {"kind": "entrances_overlap", "text": f"{a} {b}", "layers": [a, b], "overlap_s": 0.5, "apart_s": 0.0}


def test_identical_findings_are_one_line_and_the_cap_says_how_to_ask_for_more():
    found = [_overlap(f"mote_{i}", f"mote_{j}") for i in range(30) for j in range(i + 1, 30)]
    found.append({"kind": "never_shown", "text": "x", "layer": "ghost", "why": "it is always outside the frame"})
    found += [{"kind": "never_shown", "text": "x", "layer": f"w{i}_{j}", "why": "w"} for i in range(5) for j in range(5)]
    found += [_overlap(f"{k}_a", f"{k}_b") for k in "pqrstuvwxyz"]
    groups = R.grouped(found)
    assert groups[0]["kind"] == "never_shown" and len(groups) < 40          # 400+ findings, a handful of lines
    assert next(g for g in groups if g["kind"] == "entrances_overlap")["count"] == 435
    shown, more = R.capped(groups, 5)
    assert len(shown) == 5 and "all: true" in more


def test_a_staggered_grid_is_one_overlapping_run_not_a_finding_per_pair():
    """Critic r10: 200 staggered dots gave 11,000+ pair findings and buried the real ones."""
    from rostrum2d.mcp.motion_checks import entrance_overlaps
    facts = [{"id": f"dot{i}", "type": "shape", "entrance": (round(i * 0.04, 3), round(i * 0.04 + 1, 3))} for i in range(200)]
    facts += [{"id": "card", "type": "shape", "entrance": (20.0, 21.0)}, {"id": "logo", "type": "text", "entrance": (20.5, 22.0)}]
    found = entrance_overlaps(facts)
    assert len(found) == 2 and len(found[0]["layers"]) == 200 and "each starts 0.04 s after the one before" in found[0]["text"]
    assert found[1]["layers"] == ["card", "logo"] and found[1]["overlap_s"] == 0.5


def test_a_key_on_the_last_moment_is_reached_one_after_it_is_not():
    layer = {"id": "a", "type": "text", "keys": [{"prop": "x", "t": 0.0, "v": 0}, {"prop": "x", "t": 2.0, "v": 5},
                                                 {"prop": "y", "t": 0.0, "v": 0}, {"prop": "y", "t": 2.5, "v": 5}]}
    out = dead_keys({"layers": [layer]}, 2.0)
    assert [f["field"] for f in out if f["kind"] == "key_after_end"] == ["y"]
