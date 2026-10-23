"""A keyed colour keeps its alpha between two keys, the same numbers as the 2D engine's `mix` (a see-through key
must never come out solid)."""
from rostrum_core.keys.evaluate import mix_color


def test_alpha_is_blended_and_written_only_while_see_through():
    assert mix_color("#ff000000", "#ff0000ff", 0.5) == "#ff000080"
    assert mix_color("#ff0000", "#ff000080", 1.0) == "#ff000080"
    assert mix_color("#ff0000", "#0000ff", 0.5) == "#bc00bc"      # both solid: still #rrggbb
