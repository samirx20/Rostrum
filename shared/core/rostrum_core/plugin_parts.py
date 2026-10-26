"""Names and parts that come from a plugin (OPERATIONS.md § 11). A plugin's names carry its prefix and a colon (an item
kind "wiggle:generator", a field "wiggle:amount", an operation "wiggle:shake.add"); Rostrum's own names never hold a
colon, so the two can't clash. A file holding parts this Rostrum doesn't have opens: they are kept untouched (saved
back as they were), never sent to an engine, and named in words (`missing`). A plugin's id is "vendor.name";
"rostrum.*" is Rostrum's own."""
from __future__ import annotations

import re

from .tree import child_keys

PREFIX = re.compile(r"^[a-z][a-z0-9_-]*$")
PLUGIN_ID = re.compile(r"^[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)+$")
RESERVED = "rostrum"                      # the vendor part of Rostrum's own (built-in) plugins


def is_plugin(name) -> bool:
    """A plugin's name: "<prefix>:<name>" (an item kind, a field, an operation)."""
    return type(name) is str and ":" in name


def prefix(name: str) -> str:
    return name.split(":", 1)[0]


def id_problems(plugin_id: str, builtin: bool = False) -> list[str]:
    """What is wrong with a plugin id in words (empty: fine). Only Rostrum's own plugins may use "rostrum.*"."""
    if not PLUGIN_ID.match(plugin_id or ""):
        return [f'plugin id "{plugin_id}" must be vendor.name, lower case (like "hiremylens.wiggle-tools")']
    if (plugin_id.split(".", 1)[0] == RESERVED) != builtin:
        return [f'plugin id "{plugin_id}": "{RESERVED}." is for Rostrum\'s own plugins only' if not builtin
                else f'built-in plugin id "{plugin_id}" must start with "{RESERVED}."']
    return []


class Table(dict):
    """An app's table by item kind (its fields, its labels) that answers a plugin's kind with `plugin(kind)` (no fields;
    "Wiggle item") instead of a KeyError, so a screen listing a document's items lists a plugin's item as a plain row
    it can select, move or delete. Any other unknown kind is still a KeyError (a bug, loud)."""

    def __init__(self, table: dict, plugin):
        super().__init__(table)
        self._plugin = plugin

    def __missing__(self, kind):
        if is_plugin(kind):
            return self._plugin(kind)
        raise KeyError(kind)


def label(kind: str) -> str:
    """What a plugin's item is called on screen: "Wiggle item (needs its plugin)"."""
    return f"{prefix(kind).replace('-', ' ').replace('_', ' ').capitalize()} item (needs its plugin)"


def found(data: dict, lists: dict) -> dict[str, dict]:
    """The plugin parts a document holds, by prefix: {"wiggle": {"items": [ids], "fields": [names]}}. A plugin item is
    opaque: what it holds inside is its own (never walked)."""
    out: dict[str, dict] = {}
    stack = [data]
    while stack:
        item = stack.pop()
        for k in item:
            if ":" in k:
                out.setdefault(prefix(k), {"items": [], "fields": []})["fields"].append(f'{item.get("id")}.{k}')
        for key in child_keys(item, lists):
            for child in item.get(key, ()):
                t = child.get("type") if type(child) is dict else None
                if is_plugin(t):
                    out.setdefault(prefix(t), {"items": [], "fields": []})["items"].append(child.get("id"))
                elif type(child) is dict:
                    stack.append(child)
    return out


def missing(data: dict, lists: dict, uses: dict | None = None) -> list[str]:
    """One plain sentence naming the plugins this document needs and this Rostrum doesn't have (none load yet), from
    the file's `uses` table (plugin id -> {"version", …}) and the parts it holds; [] when it needs none."""
    parts = found(data, lists)
    named = [f'"{pid}"' + (f" {u['version']}" if isinstance(u, dict) and u.get("version") else "") for pid, u in sorted((uses or {}).items())]
    if not named and not parts:
        return []
    n = sum(len(w["items"]) for w in parts.values())
    f = sum(len(w["fields"]) for w in parts.values())
    what = " and ".join([f"{n} item{'s' * (n != 1)}"] * bool(n) + [f"{f} setting{'s' * (f != 1)}"] * bool(f)) or "its parts"
    who = ", ".join(named) if named else ", ".join(f'"{p}:"' for p in sorted(parts))
    ids = [i for w in parts.values() for i in w["items"]] + [x for w in parts.values() for x in w["fields"]]
    return [f"This file uses the plugin{'s' * (len(named or parts) > 1)} {who}, not installed here: {what} "
            f"({', '.join(map(str, ids[:4]))}{' …' if len(ids) > 4 else ''}) kept as they are when you save, but not shown or played."]


def engine_tree(item: dict, lists: dict) -> dict:
    """The tree an engine may be sent: plugin items left out at every depth (plugin fields stay: engines read only
    the fields they know). The same objects where nothing was left out (only the path down to a plugin item is
    copied), so a document without plugin items costs one look at each item's kind (~0.3 ms for 4,000 notes)."""
    out = None
    for key in child_keys(item, lists):
        kids = item.get(key)
        if not kids:
            continue
        types = {c.get("type") for c in kids}
        if any(map(is_plugin, types)):
            new = [c for c in kids if not is_plugin(c.get("type"))]
        elif any(lists.get(t) for t in types):
            new = kids
        else:                           # leaves only (notes, keys): nothing to leave out, nothing inside
            continue
        if any(lists.get(t) for t in types):
            new = [engine_tree(c, lists) if lists.get(c.get("type")) else c for c in new]
        if len(new) != len(kids) or any(a is not b for a, b in zip(new, kids)):
            if out is None:
                out = dict(item)
            out[key] = new
    return item if out is None else out


def without(item: dict, lists: dict) -> dict:
    """`item` as an engine may see it: plugin fields and plugin children left out (a shallow copy when it held any;
    the item itself when not). Children's own insides are not visited: an engine builder calls this per item."""
    drop = [k for k in item if ":" in k]
    keys = [k for k in child_keys(item, lists) if any(is_plugin(c.get("type")) for c in item.get(k, ()))]
    if not drop and not keys:
        return item
    out = {k: v for k, v in item.items() if k not in drop}
    for k in keys:
        out[k] = [c for c in item[k] if not is_plugin(c.get("type"))]
    return out


def missing_of(doc) -> list[str]:
    """`missing` for an open Document, worked out once per state of its tree (a tree is never changed in place:
    edits.fork), so a reply or a screen may ask after every change without walking the whole document again."""
    kept = getattr(doc, "_plugins_missing", None)
    if kept is None or kept[0] is not doc.data:
        kept = doc._plugins_missing = (doc.data, missing(doc.data, doc.kind.lists, getattr(doc, "uses", None)))
    return kept[1]
