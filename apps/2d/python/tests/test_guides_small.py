"""Version B's guides (guides_small.py): the shared guide body read with B's four tools. Silent breakage: a guide line
teaching a call B does not have (the agent calls a tool that isn't there), or a hidden tool missing from the
generated tool reference (B knows less than A)."""
from rostrum2d.mcp import guides_small as g
from rostrum2d.mcp.server import GUIDES, app_tools


def test_b_text_rewrites_calls():
    assert g.b_text('`look_frame {"what": "sheet"}`') == '`look {"check": "look_frame", "what": "sheet"}`'
    assert g.b_text('`edit_markers {"ops": []}`') == '`run_script {"do": "edit_markers", "ops": []}`'
    assert g.b_text('`render_export {"format": "mp4"}`') == '`export {"format": "mp4"}`'
    assert g.b_text('`render_export {"what": "video"}`') == '`export {"what": "video"}`'
    assert g.b_text('`look_frame` with `what: "review"`') == '`look` check `look_frame` with `what: "review"`'


def test_b_guides_name_only_b_tools_and_reference_every_hidden_tool():
    tools = app_tools()
    names = {t.name for t in tools.all()}
    guides = g.load_b_guides(GUIDES, tools)
    assert g.GAPS == []                  # a new A call line the rewrite misses
    reference = guides.get("tool-reference")
    assert all(f'## look {{"check": "{c}"}}' in reference for c in g.CHECKS if c in names)
    assert all(f'## run_script {{"do": "{d}"}}' in reference for d in g.DOES if d in names)
    assert "inspect_tools" not in guides.get("start-here")
