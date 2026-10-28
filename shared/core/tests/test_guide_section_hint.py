"""An agent asking a guide for a section that is really another guide's topic is told so (it tried section "voice" in "script")."""
import pytest

from rostrum_core.errors import RostrumError
from rostrum_core.mcp.guides import Guides


def test_section_named_like_a_topic_points_to_that_topic():
    g = Guides()
    g.add("script", "# Script\n\n## Notes\nx\n")
    g.add("voice", "# Voice\n\nlines\n")
    with pytest.raises(RostrumError) as e:
        g.part("script", "voice", cap=1)
    assert 'topic "voice"' in e.value.hint
