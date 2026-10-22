"""The harmless calls the layout check's `agent-run n` makes on a song (a mix-in for SoundBridge)."""
from __future__ import annotations


class AgentDemo:
    def agent_demo_calls(self, n):
        """n lists of calls, each setting the first track's volume a little lower than the step before."""
        track = self.doc.data["tracks"][0]["id"]
        return [[{"op": "track.set", "target": [track], "args": {"volume": round(0.8 - 0.02 * (i + 1), 2)}}] for i in range(n)]
