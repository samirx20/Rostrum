"""The 3D tool list: the look family under look_frame `what`, place-by-pixel under edit_place_on, the core five first,
and every old name answering with the new tool and `what` (CONVENTIONS § 2)."""
import pytest
from rostrum_core.errors import RostrumError
from rostrum3d.mcp.server import app_tools
from rostrum3d.mcp.tool_groups import CORE

OLD = {"look_sheet": "sheet", "look_shots": "shots", "look_material": "material", "look_shape": "shape", "look_paint": "paint",
       "look_coverage": "coverage", "look_where": "where", "inspect_exposure": "exposure"}


def test_folded_names_answer_with_the_new_tool_and_what():
    tools = app_tools()
    assert tools.get("look_frame").schema["properties"]["what"]["enum"] == ["frame", *OLD.values()]
    for old, what in OLD.items():
        with pytest.raises(RostrumError) as e:
            tools.get(old)
        assert "look_frame" in str(e.value) and f'"{what}"' in str(e.value)
    for old, new, what in (("edit_place_highlight", "edit_place_on", "highlight"), ("inspect_assets", "edit_import_asset", "search"),
                           ("inspect_asset_sources", "edit_import_asset", "sources"), ("inspect_simulation", "run_simulation", "status")):
        with pytest.raises(RostrumError) as e:
            tools.get(old)
        assert new in str(e.value) and f'"{what}"' in str(e.value)


def test_core_five_first_and_descriptions_short():
    tools = app_tools()
    assert tools.core == CORE
    for t in tools.all():
        assert len(t.description.split()) <= 150, t.name


def test_width_is_one_typed_argument_across_the_looks():
    width = app_tools().get("look_frame").schema["properties"]["width"]
    assert width["type"] == "integer" and "picture's width in px" in width["description"]
