"""Connect Rostrum2D and RostrumSound's MCP servers to a person's coding agent (see shared/mcp/AGENTS.md)."""
from .agents import AGENTS, BY_ID, Agent
from .byhand import by_hand, guide_markdown, write_guides
from .configfile import ConnectError
from .connect import Found, Result, Status, add, agents_found, entries, remove, status
from .servers import MARKER, Server, entry, launcher_cmd
