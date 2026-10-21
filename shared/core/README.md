# shared/core — `rostrum_core`, the shared Python core

What all four apps' Python layers share, so each idea has one source of truth. Contract: [`OPERATIONS.md`](OPERATIONS.md).

- **Documents** of items with stable ids; each app says where its child lists live (`DocKind.lists`).
- **Operations** in one registry, with parameters that carry `valid_when` and `importance`; the MCP tool list, the command bar and the inspector all read it.
- **One door in:** `Document.apply(calls, who)`, all or nothing, loud errors naming the operation.
- **One history:** undo / redo per author (new steps, never a rewind), a drag is one step, quick nudges merge, named versions, who changed what.
- **Script re-runs merge** and never wipe what a person changed (§ 7). A script's values obey the same parameter rules as operation arguments.
- **MCP plumbing** in `rostrum_core.mcp` (conventions: `../mcp/CONVENTIONS.md`; demo server: `../mcp/demo/`).
- Later: the project-service client (`../project-service/CONTRACT.md`).

## Install and test

```
uv pip install --python <worktree>\.venv\Scripts\python.exe -e "shared\core[mcp,test]"
<worktree>\.venv\Scripts\python.exe -m pytest -q shared\core\tests
```

## Using it (an app's view)

```python
from rostrum_core import DocKind, Document, Param, Registry, Who

ops = Registry()

@ops.operation("camera.set", "Change a camera's settings.", target="camera", fields=True, params=[
    Param.toggle("dof", label="Depth of field", group="Lens"),
    Param.number("focusDistance", min=0.1, max=50, unit="m", group="Lens",
                 valid_when={"is": ["dof", True]}),          # on screen, and accepted, only when dof is on
])
def camera_set(ctx, targets, args):                          # pure: reads ctx, records edits through it
    for t in targets:
        for k, v in args.items():
            ctx.set(t, k, v)

KIND = DocKind("3d", ".trd", ops, lists={"doc": ["layers"]})  # where child items live, per item type

doc = Document.new(KIND, folder=r"C:\...\My Film", item="itm_shot")
doc.apply({"op": "camera.set", "target": ["cam_1"], "args": {"dof": True}}, Who.person())
doc.undo(Who.person())                                       # a person's Ctrl+Z never undoes an agent's work
with doc.gesture("Focus", Who.person()) as g:                # a scrub: many previews, one undo step
    g.preview({"op": "camera.set", "target": ["cam_1"], "args": {"focusDistance": 3.2}})
report = doc.run_script("shot.py", produced_tree, Who.script("shot.py"))   # merges; report.held = kept values
doc.save()                                                   # docs/itm_shot.trd + .rostrum/itm_shot.history.jsonl
```

`rostrum_core.toy` is a small stand-in document (camera, light, rectangle, text with the S3 mockup's controls) shared by the tests, the MCP demo server and the GUI kit demo.

## Keys (`rostrum_core.keys`)

The one animation model, shared by every app: `easing.py` (the easing table), `evaluate.py` (`keys_of`, `track_value`,
`mix_color`, `key_value`, `animated`), `fields.py` (`KEY_FIELDS`, the fields table of a "key" item: use it as your
`FIELDS["key"]`) and `ops.py`. An app gets `key.add`, `key.remove`, `value.set` and `key.clear` with one call:

```python
put_key = register_key_ops(REGISTRY, owners=ITEMS, check_key=..., check_still=...,
                           settable=None, value_params=[V, C])
```

`check_key(ctx, owner, prop, args)` returns `(key field "v"|"c"|"d", checked value)`; `check_still(...)` returns the
checked value of a field with no keys (and refuses one that doesn't apply now); `settable` refuses a field that can't
change now (2D: driven by an expression); `value_params` are the value params a key takes (2D adds `d`). Extras
(2D's path morph and curve handles, expressions) stay in the app. The same screen rules for "edit at the playhead goes
through keys" are `shared/gui-kit/rostrum_gui/route.py` (`KeyRoute`).

**Keys on a marker** (`marked.py`): a key's `t` may be a shared marker reference, `"#drop+0.2"` (read by
`marker_times.split / seconds`, the one reader Sound uses too). The document keeps it as written; the app turns it
into seconds once where its document becomes times (`marked.resolve`; 2D: `retime.timed` / `retime.placed`), so a
moved marker moves the key and a missing one fails loudly naming the key. `track_value` refuses an unplaced marker key
rather than give a wrong value. Raw readers use `marked.order`, `same_time`, `label`; a drag writes `marked.moved`.
Key ids: `title.opacity.k1500`, `title.opacity.k_drop_p200`. 3D: call `marked.resolve(owner, times, 0)` in its compile.

## Modules (each < 200 lines, each the only home of its idea)

| Module | Does |
|---|---|
| `errors` | the one error type, its codes and the one-line message; "did you mean" |
| `who` | person / agent / script / outside |
| `conditions` | the `valid_when` language: `is / not / all / any / fact` |
| `params` | parameter types, ranges, checking (out of range is an error, never a clamp), JSON schema |
| `registry` | `@operation`, the one list, `field_op(kind)` for the inspector, `available()` for the command bar |
| `tree` | finding items through the kind's list table |
| `edits` | the four edits (Set, Insert, Remove, Move): apply, reverse, what each touches |
| `diff` | the edits that turn one tree into another |
| `run` | checking and planning a call: targets, arguments, `valid_when`, the app's whole-document check |
| `document` | the door (`apply`), undo / redo, versions, listeners |
| `gesture` | a drag or scrub as one step |
| `history` | the change list, per-author undo state, conflicts, who changed what |
| `merge` | the script re-run three-way merge |
| `storage` | atomic save, open, outside changes, damaged-line errors |
| `ids` | written, counted, from-content and random ids |
| `toy` | the stand-in document kind |
| `mcp/` | the MCP server every app's server builds on: tools, replies, errors, who / group, jobs stand-in, guides |

## Where the code differs from the contract's sketches

- Operations are registered as **functions** (`def plan(ctx, targets, args)`) with a list of `Param`s, not classes: same facts, less code.
- Insert and Move carry `after` (the sibling they follow) as well as an index, so an edit replayed onto a document others changed still lands in the right place.
- An argument whose `valid_when` is false after the call is refused (`BAD_ARGUMENT`: "focusDistance only applies when dof is True"), so agents meet the same rule of individuality as the screen.
- While a person is dragging, other writers get `CONFLICT` ("try again in a moment") instead of interleaving with the drag.
- MCP groups: MCP has no "turn" signal, so a group lasts while one client's calls keep coming within 20 s; `group=` always wins.
- Time arguments are `{"seconds": s}` / `{"beats": b}` / `{"marker": name}` (`Param.time`); `Param.list` holds a list of one item type.
- Not built yet: times written as `"12f"`, `"#drop"`, `"+=0.5"` (they need the project service's markers); `ctx.fragment` (needs an app's script layer); document locks across processes, the real jobs queue, `inspect_project` / `inspect_markers` beyond the open documents (all project service).
