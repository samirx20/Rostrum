"""Every markup tool reply ends with the session clock, and render_film's time shows as exporting (round 3's re-bench:
the wrapper read its start as a list and every 2D call failed before it ran)."""
from rostrum_core.mcp import Reply, Tools

from rostrum2d.markup import loop


def test_every_reply_ends_with_the_clock_and_exports_are_counted():
    tools = Tools()
    tools.add("run_film", lambda ctx, args: Reply("ran"), description="run")
    tools.add("render_film", lambda ctx, args: Reply("wrote"), description="render")
    loop.wrap(tools, lambda name: ("sheet.png", [0.0, 2.5], []))
    ran = tools._tools["run_film"].fn(None, {"name": "a"})
    assert ran.summary.splitlines()[-1].startswith("Session ") and "1 calls" in ran.summary and "exporting" not in ran.summary
    wrote = tools._tools["render_film"].fn(None, {"name": "a"})
    assert "Review sheet" in wrote.summary and "2 calls" in wrote.summary
