"""inspect_sounds (what: soundtrack): what plays with a scene (UX_SPEC 3.28). The sound itself is RostrumSound's: its engine renders
the mix (AGENTS.md rule 9); 2D only says which Sound item plays (the scene's `soundtrack` field, set with comp.set)
and reads its facts through rostrum_sound.soundtrack. Listening is Sound's tools (its MCP server's look / ears)."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

from .pick import ITEM_COMP, doc_and_comp

tools = Tools()


@tools.tool("inspect_soundtrack", {"properties": {**ITEM_COMP}})
def inspect_soundtrack(ctx, args):
    """What plays with this composition: the RostrumSound item (the comp's `soundtrack` field; empty = the project's
    main mix), its length, tempo, beats per bar, bar start times (seconds) and markers. Pick another with
    comp.set {soundtrack: "<sound item id>"}. Time things to the music with the shared markers ("#drop") or these bars."""
    doc, comp = doc_and_comp(ctx, args)
    if not doc.folder:
        return Reply("No sound: this document is not in a project folder.", {"soundtrack": None})
    from rostrum_sound import soundtrack
    from rostrum2d import project_sound
    song = project_sound.song(doc.folder, comp.get("soundtrack", ""))
    f = soundtrack.facts(doc.folder, song["id"]) if song else None
    if f is None:
        return Reply("No sound: the project has no RostrumSound item.", {"soundtrack": None})
    meter = f"{f['bpm']:g} bpm, {f['beatsPerBar']} beats a bar" + (" (the tempo changes)" if f["tempoChanges"] else "")
    marks = ", ".join(f'"{m["name"]}" {m["at"]:g} s' for m in f["markers"]) or "none"
    return Reply(f'Plays "{f["name"]}" ({f["item"]}): {f["seconds"]:g} s, {meter}, {len(f["bars"])} bars. Markers: {marks}.',
                 {"soundtrack": f})
