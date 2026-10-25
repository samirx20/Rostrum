"""The shared `inspect_*` tools every server has (CONVENTIONS § 2). They never change anything."""
from __future__ import annotations

from .. import desk, project
from ..errors import RostrumError, codes, did_you_mean
from .reply import Reply
from .tools import Tools

_ITEM = {"item": {"type": "string", "description": "The document's project item id. Optional when only one document is open."}}
_DETAIL = {"detail": {"enum": ["short", "full"], "default": "short", "description": "full adds the structured data behind the summary."}}
NO_FOLDER = "This server was started without a project folder, so this shows the open document(s) only."


def _kind_name(doc) -> str:
    return getattr(getattr(doc, "kind", None), "name", "document")


def _summary(child: dict, lists: set) -> str:
    """A child in a few words: its name or label if it has one, else its first plain value."""
    name = child.get("name") or child.get("label")
    if name:
        return str(name)
    vals = [f"{k}={v}" for k, v in child.items() if k not in lists | {"id", "type"} and not isinstance(v, (dict, list))]
    return ", ".join(vals[:3])


def _children(part: dict, lists: set, full: bool) -> dict:
    """The part's child lists, generic from the kind's `lists`: name -> count and each child's id, type, summary."""
    out = {}
    for key in (k for k in part if k in lists and isinstance(part[k], list)):
        kids = [{"id": c.get("id"), "type": c.get("type"), "summary": _summary(c, lists), **({"values": c} if full else {})}
                for c in part[key]]
        out[key] = {"count": len(kids), "children": kids}
    return out


def _brief(change, full: bool) -> dict:
    d = change.to_dict() if full else {}
    ops = [c.get("op") for c in change.calls]
    return {**d, "seq": change.seq, "who": change.who.to_dict(), "label": change.label, "when": change.when, "group": change.session, "ops": ops}


def _markers(folder):
    """The project's marker document when it has one (its changes join every item's history)."""
    from ..markers import _exists, open_markers
    return open_markers(folder) if folder and _exists(folder) else None


def register(tools: Tools):
    @tools.tool("inspect_project", {"properties": {"kind": {"enum": ["2d", "sound", "3d", "edit"], "description": "Only items of this kind."}, **_DETAIL}})
    def inspect_project(ctx, args):
        """The project: every item (any app's: kind, name, finished renders, newest first) and what is open here."""
        docs = [{"item": i, "kind": _kind_name(d), "seq": d.seq, "items": sum(1 for _ in d.items())} for i, d in ctx.app.documents.items()]
        names = ", ".join(f'{d["item"]} ({d["kind"]}, step {d["seq"]})' for d in docs) or "nothing"
        if not ctx.app.folder and not docs:           # a server started before the person opened any project
            text = " ".join(x for x in ("No project is open.", ctx.app.no_project_hint) if x)
            recent = ctx.app.recent() if ctx.app.recent else None
            return Reply(text, {"app": ctx.app.name, "open": [], "items": None,
                                **({"recent": recent} if recent is not None else {})})
        if not ctx.app.folder:
            return Reply(f"{ctx.app.name}: open: {names}. {NO_FOLDER}", {"app": ctx.app.name, "open": docs, "items": None},
                         warnings=[NO_FOLDER])
        found = project.items(ctx.app.folder, args.get("kind"))
        if args.get("detail") != "full":
            found = [{**it, "renders": [{k: r[k] for k in ("version", "kind", "path", "files")} for r in it["renders"]]}
                     for it in found]
        listed = "; ".join(f'{it["name"]} ({it["kind"]}, {len(it["renders"])} render(s))' for it in found) or "no items"
        return Reply(f"{ctx.app.name}: project items: {listed}. Open here: {names}.",
                     {"app": ctx.app.name, "folder": str(ctx.app.folder), "items": found, "open": docs})

    @tools.tool("inspect_item", {"properties": {**_ITEM, "id": {"type": "string", "description": "A part's id inside the document. Without it, the whole document outline."}, **_DETAIL}})
    def inspect_item(ctx, args):
        """One document, or one part of it by id: its values, who last changed it, the operations that fit it now."""
        doc = ctx.document(args.get("item"))
        if "id" not in args:
            outline = [{"id": it["id"], "type": it.get("type")} for it in doc.items()]
            warn = doc.kind.warnings(doc.data)
            return Reply(f"{len(outline)} items in {_kind_name(doc)} document, history step {doc.seq}."
                         + (f" {len(warn)} things it holds are no longer made (see warnings)." if warn else ""),
                         {"seq": doc.seq, "items": outline, "no_longer_made": warn})
        part = doc.item(args["id"])
        lists = {k for ks in getattr(doc.kind, "lists", {}).values() for k in ks}
        values = {k: v for k, v in part.items() if k not in lists}
        ops = [o.name for o in doc.kind.registry.available(doc, [args["id"]])]
        who = {f: (c.who.to_dict() if (c := doc.who_changed(args["id"], f)) else None) for f in values if f not in ("id", "type")}
        checks = [str(p) for p in doc.kind.check(doc.data) if args["id"] in str(p)]
        children = _children(part, lists, args.get("detail") == "full")
        data = {"id": args["id"], "type": part.get("type"), "values": values, "children": children, "operations": ops, "checks": checks}
        if args.get("detail") == "full":
            data["last_changed_by"] = who
        lists_said = "".join(f" {k}: {v['count']} ({', '.join(c['id'] or '?' for c in v['children'][:5])}{', …' * (v['count'] > 5)})." for k, v in children.items())
        return Reply(f'{part.get("type")} "{args["id"]}": {len(values) - 2} values, {len(checks)} check problems.{lists_said} '
                     f"Operations that fit now: {', '.join(ops) or 'none'}.", data)

    @tools.tool("inspect_history", {"properties": {**_ITEM, "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 20}, "group": {"type": "string"}, **_DETAIL}})
    def inspect_history(ctx, args):
        """Recent changes, newest last: step, who (kind and name), label, when, group, operations, and which
        document (`doc`): the item's own, or the project's shared markers, which share one history (desk.py)."""
        doc = ctx.document(args.get("item"))
        docs = [doc] + [m for m in [_markers(ctx.app.folder)] if m is not None and m.item_id != doc.item_id]
        changes = [(d, c) for d, c in desk.changes(docs) if not args.get("group") or c.session == args["group"]]
        shown = [{**_brief(c, args.get("detail") == "full"), "doc": d.item_id or "open document"}
                 for d, c in changes[-args.get("limit", 20):]]
        last = shown[-1] if shown else None
        tail = f" Latest: {last['doc']} step {last['seq']} by {last['who']['kind']}:{last['who']['name']} ({last['label'] or ', '.join(last['ops'])})." if last else ""
        return Reply(f"{len(shown)} of {len(changes)} changes shown.{tail}", {"seq": doc.seq, "changes": shown})

    @tools.tool("inspect_operations", {"properties": {**_ITEM, "name": {"type": "string", "description": "One operation, for its full argument schema."}, **_DETAIL}})
    def inspect_operations(ctx, args):
        """The operations this app accepts, read from the one registry (name, arguments, what it does)."""
        docs = [ctx.document(args["item"])] if "item" in args else list(ctx.app.documents.values())
        ops = {o.name: o for d in docs for o in d.kind.registry.ops()}
        if "name" in args:
            if args["name"] not in ops:         # an alias answers as the operation it stands for
                for d in docs:
                    real = d.kind.registry.resolve([{"op": args["name"], "target": [], "args": {}}])[0]["op"]
                    if real in ops and real != args["name"]:
                        op = ops[real]
                        return Reply(f'{args["name"]} is written {op.name} here. {op.name}: {op.summary}', {"operations": [op.schema()]})
                raise RostrumError(codes.UNKNOWN_OPERATION, "", f'"{args["name"]}"', "is not an operation of this app", sorted(ops),
                                   did_you_mean(args["name"], ops))
            op = ops[args["name"]]
            return Reply(f"{op.name}: {op.summary}", {"operations": [op.schema()]})
        full = args.get("detail") == "full"
        rows = [o.schema() if full else {"name": o.name, "summary": o.summary, "target": o.shown_targets()} for o in ops.values()]
        return Reply(f"{len(ops)} operations: {', '.join(ops)}. Ask with name for one's arguments.", {"operations": rows})

    @tools.tool("inspect_guide", {"properties": {"topic": {"type": "string"}, "section": {"type": "string", "description":
            'Only the section whose heading has these words (e.g. "Scripts"), or "all" for the whole guide. Default: start-here '
            "whole; a long guide's first sections, then the headings of the rest."}}})
    def inspect_guide(ctx, args):
        """A how-to guide by topic; read 'start-here' first. With no topic, the list of topics (also served as MCP resources rostrum://guide/<topic>).
        A long guide comes as its first sections and the headings of the rest; ask for one with `section`."""
        g = ctx.app.guides
        if "topic" not in args:
            return Reply(f"{len(g.topics())} guides: {', '.join(g.topics())}.", {"topics": [{"topic": t, "title": g.title(t)} for t in g.topics()]})
        return Reply(g.part(args["topic"], args.get("section")), {"topic": args["topic"], "section": args.get("section")})
