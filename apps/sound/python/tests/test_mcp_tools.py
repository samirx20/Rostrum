"""What would break silently: one badly named tool stops the whole `rostrum-sound` MCP server from starting (P23 found
`install_model` had kept it down since P21). Every tool must register under the shared naming rules."""
from rostrum_sound.mcp.server import sound_tools


def test_every_sound_tool_registers():
    sound_tools()
