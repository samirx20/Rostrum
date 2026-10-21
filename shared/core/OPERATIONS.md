# Operations and history — the contract

*Team Sam, brief S1 · P-REPO, 2026-10-21. Draft for review. Built from the experiment's edit model (archive `docs/EDIT_MODEL.md`, `src/core/ops/registry.ts`, `context.ts`, `describe.ts`, `src/core/edits/`), rewritten for Python.*

This is how every change to a Rostrum document is made, recorded and undone, in all four apps. A person dragging in the GUI, a script, and an agent over MCP all go through the same door.

## 1. Who owns the document

- Every app's document (2D `.mtn`, Sound `.trk`, 3D `.trd`, Editor `.rsm`) is owned by that app's **Python layer**, through one shared package: **`rostrum_core`** (in `shared/core/`). Every app's Python imports it.
- The **engines** (Rust for 2D and Sound, C++ for 3D and the Editor) **never own or write the document**. They get a read-only copy (or a stream of changes) and turn it into pictures and sound. What an engine works out (a simulation, a track, an analysis) comes back as a **job result**, and is written into the document only by an operation (see the project service contract, `shared/project-service/CONTRACT.md`).
- One writer per document: the app's Python process. Its GUI and its MCP server both talk to that process. When the app is not open, the CLI or MCP server opens the document itself and takes the document's lock from the project service, so two writers never interleave.

## 2. The document: items with stable ids

A document is a tree of **items**. Every item that can be changed has an **id** that never changes.

- An id written by the author wins (`id="logo"`).
- A script that doesn't name things gets ids counted **per type, in creation order**: `text_1`, `text_2`, `rect_1`. Adding a rectangle never renumbers the texts. Every quoted word in the script is reserved, so a counted id never steals a written one.
- Things inside a timeline get ids **from their content**: a note `chords.n1500` (starts at 1500 ms in its clip), an effect `pad.eq_1`, a character's pose key `act_hero_pose_1500`. Inserting one earlier shifts no other id.
- Ids made by the GUI are random (they only need to be unique).
- Ids are kept once given: a moved key keeps its id.

Each app tells `rostrum_core` **where its lists of items are** (2D: screens › layers › children; Sound: tracks › clips; Editor: sources, tracks, clips, markers) and what kind each list holds. That small table is all the shared code needs to find, diff and merge any app's document.

## 3. Edits and changes

Everything comes down to four small **edits**, each addressed by id, never by position in a list:

```python
Set(id="logo", path=["x"], value=620, before=400)          # change a field (value missing = remove it)
Insert(id="card_3", parent="screen_1", key="layers", index=2, item={...})
Remove(id="card_2", parent="screen_1", key="layers", index=1, item={...})
Move(id="card_3", from_=("screen_1", "layers", 2), to=("screen_2", "layers", 0))
```

Each edit carries what was there before, so it can be reversed without an old copy of the document. Because edits name ids, changes from different people commute unless they touch the same field.

Edits are grouped into a **change** — one step in the history, one undo:

```json
{ "seq": 42, "based_on": 41,
  "who": { "kind": "person" | "agent" | "script" | "outside", "name": "agent:claude-sonnet" },
  "label": "Move logo", "when": "2026-10-21T14:03:11Z",
  "session": "ai-run-7",                      // optional: an agent's run, shown as one reviewable group
  "calls": [{ "op": "layer.move", "target": ["logo"], "args": { "x": 620 } }],
  "edits": [ ... ], "hash_after": "9f2c…" }
```

**Who** is filled in by `rostrum_core`, never by the caller: the GUI is `person`, an MCP call is `agent` named by its MCP client, a script run is `script` named by its file, and a file changed by something without history is `outside`.

## 4. Operations: one format, one registry

An **operation** is a named, checked action. Every GUI button, menu item and drag is an operation first (AGENTS.md rule 4). A call looks the same from everywhere:

```json
{ "op": "layer.move", "target": ["logo"], "args": { "x": 620, "y": "+=20" } }
```

- **Name** is `area.verb` (`layer.move`, `clip.trim`, `marker.add`, `key.ease`).
- **Target** is the id(s) it acts on. **Args** are everything else.
- Times may be written the way scripts write them: seconds, `"12f"` (frames), `"bar:9"`, `"#drop"` (a marker), `"music#drop+0.5"` (another item's marker, half a second after it), `"+=0.5"` (relative to the current value).

An app registers its operations once, in Python:

```python
@operation("layer.move", summary="Move layers to a position or by an offset.", target="layer")
class Move(Args):                      # typed arguments: types, ranges, defaults, a line of help each
    x: Length | None = None
    y: Length | None = None

    def plan(self, doc, targets, ctx) -> list[Edit]: ...   # pure: reads, returns edits, writes nothing
```

- `plan` never writes files and never builds an item by hand: a new item comes from a small piece of script run through the app's own script layer (`ctx.fragment(...)`), so new items look exactly like scripted ones.
- An operation that needs heavy work (a track, a mask, a measurement) sends a job to the project service's queue first and plans with its result. It never blocks the GUI.
- **Argument types:** `number`, `toggle`, `choice`, `text`, `color`, `id`, `points`, plus two for lists and timing. `time` is exactly one of `{"seconds": 1.5}`, `{"beats": 4}` or `{"marker": "drop"}` (seconds and beats are 0 or more; `min`/`max` bound seconds; default `{"seconds": 0}`). `list` (`Param.list("gains", "number", min=-60, max=12)`) is `[value, …]` of one item type, each element checked like that type (`min_items` / `max_items` bound the count). A bad value is refused with the element's position, never clamped. `inspect_item` also lists each item's child lists (name, count, each child's id, type and a short summary).
- **One registry, many readers.** The same list feeds: the MCP server (`ops.list` and the schema an agent builds calls from — see `shared/mcp/CONVENTIONS.md`), the CLI help, the GUI command bar (Ctrl+K), the inspector (built from the argument types), and the guides. There is no second list anywhere.

## 5. Running a call: all or nothing, and loud

A call is a **list** of operations, run in order against the document as the ones before it left it, then saved as **one change**.

1. Each operation's arguments are checked against its types.
2. Each target must exist and be the right kind; a locked item refuses every operation except unlock.
3. All plans run; then the app's own whole-document check runs (for example 3D re-solves cameras).
4. If **anything** fails, **nothing** is applied or saved. The error says which operation (its place in the list), which argument, what was given, and what would work:

```json
{ "code": "NOT_FOUND", "where": "op 2 of 2 (layer.move)", "subject": "target \"logoo\"",
  "problem": "no layer \"logoo\" in this document", "accepted": ["logo", "logo_glow"], "hint": "Did you mean logo?" }
```

The error codes and the one-line message format are defined once, in `shared/mcp/CONVENTIONS.md` › Errors; the GUI, CLI and MCP all show the same error. There is no "warn and carry on": a value out of range is an error, not a clamp.

## 6. One history per document

- Stored beside the document, append-only: `.rostrum/<item>.history.jsonl` in the project folder. Line 0 is the document when history began; every later line is one change, with the document's hash after it. The document file itself stays a plain, readable snapshot.
- Every save writes atomically (temp file, then rename; retried while Windows holds the file).
- On open, if the file's hash doesn't match the history's last line, the difference is recorded first as a change by `outside`, so history never silently disagrees with the file. A damaged history line stops the save and names the file and line.
- Save stamps (save time, generator) are not tracked, so a save that changes nothing records nothing.
- Kept whole; no trimming until a real project shows it is too big.

### Undo and redo
- Undo is a **new change** that applies the reverse of an earlier one (`"Undo: Move logo"`). History only grows, so undo itself can be undone and every step stays visible.
- **Undo is per author.** A person's Ctrl+Z undoes that person's last change, never the agent's (like a shared online document). An agent's `undo` undoes its own. The history panel can undo any single change, or a whole agent session at once.
- Undo refuses, changing nothing, when a later change touched the same thing, and says which change.

### A drag is one step
- The GUI opens a **gesture** when a drag (or a slider scrub) starts. While it moves, the document updates live in memory and the viewer redraws; on release the gesture is saved as **one** change.

```python
with doc.gesture("Move logo"):         # person drags; many small updates
    doc.preview({"op": "layer.move", "target": ["logo"], "args": {"x": x}})
# released: one change, one undo step. Escape during the drag: nothing is recorded.
```

- Repeated small nudges by the same person on the same fields (arrow keys, typing in a number box), with nothing else in between, within about a second, are merged into the last change.

### Named versions and who changed what
- A **version** is a name on a point in history (`"before client notes"`). Restoring is a new change back to that point, so it can be undone.
- `history.who(id, field)` gives the last change that touched a value: who, when, the label. The history panel shows each change as you / agent / script.

## 7. Re-running a script never wipes a person's work

A script is one way of writing into the document, not its master copy. When a script runs again, `rostrum_core` compares three things:

```
B = what this script produced last time (stored: .rostrum/<item>.script.json)
N = what it produces now
C = the document now (the script's output plus everyone's changes since)

script's changes  = diff(B, N)      # what the script itself changed
others' changes   = diff(B, C)      # what people and agents changed
apply the script's changes to C, except where they collide with others' changes
```

- The first run creates the document from N.
- **Collision** (the script changed a field someone else also changed): the other author's value is **kept**, and the reply lists it: `logo.x: script says 400, kept 620 (person, "Move logo")`. The agent decides: change it with an operation, or run again with `force=["logo.x"]` (or `force=True` for everything).
- An item the script deletes but someone edited is kept and reported the same way.
- B only moves forward by what was applied, so a held-back change is reported again next run, or applied when forced.
- Stable ids (§2) are what make this possible: the same script gives the same ids every run.
- An open GUI receives the run as a change, not a reload, so its undo history survives.

## 8. Two writers at once

Each change records the history step it was based on (`based_on`). If the document moved on meanwhile (the person saved while the agent was planning), the edits are re-applied on the newer document — they name ids, so they usually still fit — and any collision is reported, never lost.

## 9. What lives in `rostrum_core`

Small modules, each under ~200 lines, each the only home of its idea:

| Module | Does |
|---|---|
| `ids` | stable ids: written, counted per type, from content, random |
| `edits` | the four edits; apply, reverse, diff two documents |
| `registry` | `@operation`, the one list, descriptions and schemas for MCP / CLI / GUI |
| `run` | run a call: check, plan, app check, all-or-nothing, one change |
| `history` | the history file, safe saving, outside changes, undo / redo, versions, who |
| `merge` | script re-run (three-way) and late changes (`based_on`) |
| `errors` | the one error type and its plain-language messages |
| `kind` | a document kind: its lists, check, and `facts(item, doc)` for valid_when (doc: a read-only `View`, so a child can ask its parent) |
| `params` | parameters: type, range, help, importance, valid_when; a choice's plain-word labels |
| `cache` | the shared content-keyed cache (project-service contract § 5) |
| `project` | a project's items and their finished renders (contract § 7, read from the folder until the service exists) |

Each app adds only its own operations, its table of where items live, and its whole-document check.

## Settled default

- **Undo is per author** (as in the experiment): a person's Ctrl+Z never undoes an agent's work; agent changes are undone from the AI panel or the history panel, one change or a whole agent run at a time. If Sam prefers one shared undo for everyone, only `history` changes.
