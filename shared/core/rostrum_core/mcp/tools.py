"""Tool registration: a name (`<verb>_<thing>`), an argument schema and a function (CONVENTIONS § 2, § 3, § 11).

    tools = Tools()
    @tools.tool("look_frame", schema=LookFrameArgs)          # a JSON-schema dict or a pydantic model class
    def look_frame(ctx, args) -> Reply: ...

`from rostrum_core.mcp import tool` registers on the shared default set (`default_tools`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

import jsonschema

from ..errors import RostrumError, codes, did_you_mean
from . import job_wait

VERBS = ("run", "inspect", "edit", "render", "look")
_NAME = re.compile(r"^(" + "|".join(VERBS) + r")_[a-z][a-z0-9]*(_[a-z0-9]+)*$")


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    schema: dict            # JSON schema of the arguments (an object)
    model: Any              # a pydantic model class when the app gave one, else None
    fn: Callable
    origin: str = "builtin"   # "builtin" or a plugin's id; shown by inspect_tools only when it isn't a built-in

    @property
    def verb(self) -> str:
        return self.name.split("_", 1)[0]

    def check(self, args: dict | None):
        """Check arguments before anything runs. Returns the model instance, or the plain dict."""
        args = {} if args is None else args
        if not isinstance(args, dict):
            raise _bad(self, "arguments", f"must be an object, not {type(args).__name__}", [])
        props = self.schema.get("properties", {})
        for key in args:
            if key not in props:
                raise _bad(self, f'"{key}"', "is not an argument of this tool", sorted(props), did_you_mean(key, props))
        errors = sorted(jsonschema.Draft202012Validator(self.schema).iter_errors(args), key=lambda e: list(map(str, e.path)))
        if errors:
            e = errors[0]
            where = ".".join(str(p) for p in e.path)
            accepted = e.validator_value if e.validator == "enum" else (
                [k for k in self.schema.get("required", []) if k not in args] if e.validator == "required" else [])
            subject = f'argument "{where}"' if where else "arguments"
            raise _bad(self, subject, e.message, accepted)
        return self.model.model_validate(args) if self.model is not None else args


def _bad(tool: Tool, subject: str, problem: str, accepted, hint: str | None = None) -> RostrumError:
    return RostrumError(codes.BAD_ARGUMENT, tool.name, subject, problem, accepted, hint)


def _schema_of(schema) -> tuple[dict, Any]:
    if isinstance(schema, dict):
        out, model = dict(schema), None
    elif hasattr(schema, "model_json_schema"):
        out, model = schema.model_json_schema(), schema
    else:
        raise TypeError("schema must be a JSON-schema dict or a pydantic model class")
    out.setdefault("type", "object")
    out.setdefault("properties", {})
    out.setdefault("additionalProperties", False)      # never guess: an unknown argument is an error
    return out, model


class Tools:
    """A set of tools. One per server; apps register theirs and the server adds the shared ones."""

    def __init__(self, origin: str = "builtin"):
        self.origin = origin                  # what a tool added without its own origin comes from
        self._tools: dict[str, Tool] = {}
        self._renamed: dict[str, tuple[str, str | None]] = {}   # old name -> (new tool, the argument to pass)

    def add(self, name: str, fn: Callable, schema=None, description: str | None = None, origin: str | None = None) -> Tool:
        if not _NAME.match(name):
            raise RostrumError(codes.BAD_ARGUMENT, "tool registration", f'"{name}"', "is not a valid tool name; use <verb>_<thing>, lower case",
                               VERBS, "Example: look_frame, inspect_markers, render_stems.")
        if name in self._tools:
            raise RostrumError(codes.BAD_ARGUMENT, "tool registration", f'"{name}"', "is already registered")
        spec, model = _schema_of(schema or {})
        spec = job_wait.with_wait_schema(name, spec)       # look_/render_: `wait` for a job in the same call (the server does it)
        text = (description or fn.__doc__ or "").strip()
        if not text:
            raise RostrumError(codes.BAD_ARGUMENT, "tool registration", f'"{name}"', "has no description; agents choose tools by it")
        self._tools[name] = Tool(name, text, spec, model, fn, origin or self.origin)
        return self._tools[name]

    def tool(self, name: str, schema=None, description: str | None = None, origin: str | None = None):
        def register(fn):
            self.add(name, fn, schema, description, origin)
            return fn
        return register

    def renamed(self, old: str, new: str, how: str | None = None):
        """An old name answers with an error that names the new tool, and `how` its argument (CONVENTIONS § 2):
        it never silently works."""
        self._renamed[old] = (new, how)

    def take(self, name: str) -> Tool:
        """Remove a registered tool and return it (combine.py builds one tool from several)."""
        return self._tools.pop(name)

    def get(self, name: str) -> Tool:
        if name in self._tools:
            return self._tools[name]
        if name in self._renamed:
            new, how = self._renamed[name]
            raise RostrumError(codes.UNKNOWN_TOOL, name, f'"{name}"', "was renamed", [new],
                               f"Use {new}" + (f" with {how}" if how else "") + ".")
        raise RostrumError(codes.UNKNOWN_TOOL, name, f'"{name}"', "is not a tool of this server", sorted(self._tools), did_you_mean(name, self._tools))

    def described(self, name: str, more: str):
        """Add an app's own words to a shared tool's description (run_script: what the app's script layer offers)."""
        t = self._tools[name]
        self._tools[name] = Tool(t.name, f"{t.description} {more}", t.schema, t.model, t.fn, t.origin)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def merged_with(self, other: "Tools") -> "Tools":
        out = Tools()
        for t in [*self._tools.values(), *other._tools.values()]:
            if t.name in out._tools:
                raise RostrumError(codes.BAD_ARGUMENT, "tool registration", f'"{t.name}"', "is already registered")
            out._tools[t.name] = t
        out._renamed = {**self._renamed, **other._renamed}
        return out


default_tools = Tools()
tool = default_tools.tool
