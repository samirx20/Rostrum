"""An asset source that is off never reaches the network: not through a search, a download, a thumbnail or an agent
tool (the person alone switches a source on; whether those sites are asked at all is their choice)."""
import urllib.request

import pytest

from rostrum3d import assets
from rostrum3d.assets import settings, thumbs


@pytest.fixture
def no_network(monkeypatch, tmp_path):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path / "home"))      # every source off: a fresh settings home

    def refuse(*a, **k):
        raise AssertionError("an off source opened the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    return tmp_path


@pytest.mark.parametrize("source", ["polyhaven", "ambientcg"])
def test_off_source_makes_no_network_call(no_network, source):
    assert not settings.is_on(source)
    for call in (lambda: assets.search(source, "chair"),
                 lambda: assets.bring_in(source, "ArmChair_01", no_network / "project"),
                 lambda: assets.source(source).search("chair", 0),          # the source's own methods too
                 lambda: assets.source(source).files("ArmChair_01"),
                 lambda: thumbs.fetch(source, "ArmChair_01", "https://example.com/t.png")):
        with pytest.raises(assets.AssetError) as e:
            call()
        assert e.value.off and "Import › Asset library" in str(e.value)
    assert not (no_network / "project").exists()


def test_agent_tool_fails_plainly_while_off(no_network):
    from rostrum_core.errors import RostrumError
    from rostrum3d.mcp import assets_tools

    class Ctx:
        tool = "inspect_assets"
    with pytest.raises(RostrumError) as e:
        assets_tools.asset_search(Ctx(), {"source": "polyhaven", "query": ""})
    assert "Poly Haven is off; the person switches it on in Import › Asset library" in str(e.value)
