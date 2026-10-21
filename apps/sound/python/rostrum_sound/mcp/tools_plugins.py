"""Plug-ins (CLAP / VST3): what is installed and what each one can be set to. Reads the machine; the document is
changed with the usual `edit_document` operations: `effect.add` with effect "plugin", `track.set` with instrument "plugin"."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools


def register(tools: Tools):
    @tools.tool("inspect_plugins", {"properties": {
        "path": {"type": "string", "description": "A plug-in file or a folder to scan; left out = the usual install folders."},
        "find": {"type": "string", "description": "Words that must appear in the name, vendor or id (case-insensitive)."},
        "kind": {"type": "string", "enum": ["effect", "instrument"], "description": "Only effects, or only instruments."},
        "params": {"type": "boolean", "default": False, "description": "List every plug-in's parameters (id, name, range, default), not just their count."}}})
    def inspect_plugins(ctx, args):
        """Installed CLAP / VST3 plug-ins with their parameters. To use one: effect.add {effect: "plugin", plugin: {format, path, id, name, params}} (an effect), or track.set {instrument: "plugin", plugin: {...}} (an instrument). `params` maps a parameter id to a number, or to [[time, value], …] to automate it."""
        scan = ctx.app.state.engine.plugins(args.get("path"))
        words = (args.get("find") or "").lower().split()
        out = []
        for p in scan["plugins"]:
            text = f"{p.get('name', '')} {p.get('vendor', '')} {p.get('id', '')}".lower()
            if (not args.get("kind") or p.get("kind") == args["kind"]) and all(w in text for w in words):
                out.append(p if args.get("params") else {**{k: v for k, v in p.items() if k != "params"},
                                                          "paramCount": len(p.get("params", []))})
        lines = [f"{p['name']} ({p['format']}, {p.get('vendor', '?')}, {p['kind']})" for p in out[:12]]
        failed = scan.get("failed", [])
        broke = f" {len(failed)} could not be loaded: " + "; ".join(f"{f['path']}: {f['error']}" for f in failed[:5]) if failed else ""
        return Reply(f"{len(out)} plug-ins" + (": " + "; ".join(lines) + (" …" if len(out) > 12 else "") if out else
                     " found (none installed here, or none match).") + broke,
                     {"plugins": out, "failed": failed, "folders": scan.get("folders", [])})
