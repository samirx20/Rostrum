# MCP conventions

Every Rostrum app has its own MCP server (MCP is the standard way AI agents call an app's tools). The servers are named **`rostrum-2d`**, **`rostrum-sound`**, **`rostrum-3d`** and **`rostrum-editor`**. All four follow this page, so an agent that knows one knows the others.

The shared plumbing lives in the Python package **`rostrum_core`** (`shared/core/`). Each app adds only its own tools on top of it.

Related contracts:
- [`shared/core/OPERATIONS.md`](../core/OPERATIONS.md): operations, the one history, who changed what.
- [`shared/project-service/CONTRACT.md`](../project-service/CONTRACT.md): project items, markers, live links, cache, the one jobs queue.
- [`shared/HANDOFFS.md`](../HANDOFFS.md): the files apps hand to each other.

## 1. Five verbs

Every tool starts with one of five verbs. The verb tells the agent what the tool may do.

| Verb | What it does | Changes the document? | Example tools |
|---|---|---|---|
| **run** | Runs a Python script against the document, or stops a job | yes, through operations | `run_script`, `run_stop` |
| **inspect** | Reads facts: the project, an item, markers, history, the operation list, guides, a job | never | `inspect_project`, `inspect_item`, `inspect_job` |
| **edit** | Applies operations (the same ones the GUI uses) | yes, through operations | `edit_document` |
| **render** | Makes files: exports and hand-offs. Always a job | no (writes files) | `render_video`, `render_layers`, `render_stems` |
| **look** | Lets the agent see or hear the result: frames, sheets, motion, "what's here", loudness, spectrum | never | `look_frame`, `look_at`, `look_loudness` |

"Look" covers hearing too: a sound check is a look at the sound.

## 2. Tool names

- **`<verb>_<thing>`**, lower case with underscores: `look_frame`, `inspect_markers`, `render_stems`.
- **Few tools, each clear.** Aim for 10–25 per app. The experiment taught both sides of this. With hundreds of tools, agents can't find the right one. With four tools that each took 38 "targets", agents guessed target names. So one tool does one job, and its arguments pick the details.
- **Same name, same meaning in every app.** `look_frame` returns one picture in 2D, 3D and the Editor. A tool that only makes sense in one app (for example `look_spectrum` in Sound) still uses the verb rules.
- **Renames:** an old name answers for one minor version with an error that names the new tool. It never silently works.

### Tools every server has (from `rostrum_core`)

| Tool | What it does |
|---|---|
| `inspect_project` | The project: its items, its frame rate, colour settings, what is open |
| `inspect_item` | One item, by id: its parts, values and checks |
| `inspect_markers` | The project's named markers (one shared list, `shared/project-service/MARKERS.md`): id, name, seconds, who made it; `name: "drop+0.5"` gives one time |
| `edit_markers` | Add, move, rename or delete the project's markers (`marker.add` / `.move` / `.rename` / `.remove`), all or nothing, one step in their history |
| `inspect_history` | Recent changes: who, what, when, and which group they belong to |
| `inspect_operations` | The operations this app accepts, read from the one registry (name, arguments, what it does) |
| `inspect_guide` | A how-to guide by topic. With no topic, the list of topics |
| `inspect_job` | A job's status and, when it is done, its result |
| `edit_document` | Applies a list of operations, all or nothing |
| `run_script` | Runs a Python script. The script's changes are merged in and never wipe what a person moved |
| `run_stop` | Stops a job by its id |

Each app adds its own `look_*`, `render_*` and any `inspect_*` it needs.

## 3. Arguments

- Argument names are `snake_case`. Every tool has a JSON schema, and arguments are checked before anything runs.
- **Ids, not names or positions.** Every item and every part has a stable id string (for example `"title_3"`). Names are for people and can repeat. Position in a list changes. Project-level ids follow the project service contract.
- **Times:** seconds as a number (`2.5`), or a **marker reference** (`"music#drop"`, `"music#drop+0.25"`, `"#logo_lands"`; the same forms as `OPERATIONS.md` › Operations). Use a marker when lining things up across apps; don't copy numbers. Tools that work on frames also take `frame` (a whole number at the document's frame rate).
- **Files:** absolute paths in replies. A relative path in an argument is read from the project folder.
- **`detail`:** `"short"` (default) keeps the reply to a few KB. `"full"` adds the structured data behind it.

```json
{ "tool": "look_frame", "arguments": { "item": "intro", "at": "music#drop", "width": 960, "overlays": ["ids", "grid"] } }
```

## 4. Results

Every reply has the same shape:

```json
{
  "ok": true,
  "summary": "Frame 48 (2.0 s) of intro, 960×540. 6 items visible.",
  "data": { "frame": 48, "time": 2.0, "visible": ["title_3", "bg_1"] },
  "files": ["C:\\Users\\Sam\\.rostrum\\cache\\look\\intro_f48.png"],
  "warnings": []
}
```

- `summary`: plain sentences the agent reads first.
- `data`: small structured facts. Time results always carry both `time` (seconds) and `frame`.
- `files`: absolute paths of anything written.
- Pictures also come back as MCP image content, so the agent sees them at once.
- **Edits** add `changed`: the history entry id, the operation ids, and any **new** check failures this change caused. A change that breaks something says so in its own reply.

## 5. Every change goes through operations

- `edit_document`, `run_script` and every GUI action change the document only through the shared operations in [`OPERATIONS.md`](../core/OPERATIONS.md). There is no side door.
- Each change records **who**. The MCP client's name (from the MCP handshake) becomes `who: "agent:<name>"`, for example `agent:claude-code`. An app's own AI panel can set a different name.
- All changes from one agent turn share one **group**, so the person sees them as one reviewable set in the history panel and can accept or undo them together. Pass `group` to choose it; otherwise the server makes one per turn.
- A script run again **merges**: what a person moved by hand stays where they put it.

```json
{ "tool": "edit_document", "arguments": { "item": "intro", "ops": [
  { "op": "layer.move", "target": ["title_3"], "args": { "x": 120, "y": 80 } },
  { "op": "key.add", "target": ["title_3"], "args": { "prop": "opacity", "at": "#logo_lands", "value": 1 } }
] } }
```

## 6. Errors fail loudly

A failed call returns `ok: false` and is marked as an error in MCP. It never says "done" with a broken or missing file.

```json
{
  "ok": false,
  "summary": "Error: edit_document › op 2 of 2 (key.add): \"title_33\" no item \"title_33\" in intro. Accepted: title_3, title_4, bg_1. Did you mean title_3?",
  "error": { "code": "NOT_FOUND", "where": "edit_document › op 2 of 2 (key.add)", "subject": "\"title_33\"",
             "problem": "no item \"title_33\" in intro", "accepted": ["title_3", "title_4", "bg_1"], "hint": "Did you mean title_3?" }
}
```

- **One line for people and agents:** `Error: <where>: <subject> <what is wrong>. Accepted: <…>. <what to try>.` The `error` object carries the same parts.
- **Codes** (upper case, one list in `rostrum_core`):

| Code | Meaning |
|---|---|
| `UNKNOWN_TOOL`, `UNKNOWN_OPERATION` | No such tool or operation. Says the closest names |
| `BAD_ARGUMENT` | Wrong type, missing, or out of range. Says what is accepted |
| `NOT_FOUND` | No item, marker, file or job with that id |
| `CONFLICT` | The document changed under the call (for example, a person moved it). Says what changed; read again and retry |
| `CHECK_FAILED` | The change would break a check the operation guards |
| `RENDER_FAILED` | A picture or sound could not be made. Names the frame or part |
| `JOB_FAILED`, `JOB_INTERRUPTED` | A job ended with an error, or was cut off (for example by a restart). Its output is marked incomplete |
| `MODEL_MISSING` | An AI model isn't downloaded or switched on. Says how to get it |
| `NO_MEMORY` | The machine can't fit the job now. It stays queued; this only appears if the caller asked not to wait |
| `INTERNAL` | A bug in Rostrum. Includes the log path |

- **Edits are all or nothing.** If operation 2 of 3 fails, none of them are applied.
- **Files are written whole or not at all.** Renders write to a `.partial` name, check the result (frame count, readable, no empty frames), then rename. A failed render keeps the `.partial` folder and says where it is.
- **Never guess.** An unknown colour, unit or name is an error, not a silent default.

## 7. Long work: jobs

Renders, simulations, AI models and big analyses go through the **one jobs queue** in the project service ([`CONTRACT.md`](../project-service/CONTRACT.md)), so heavy work from all four apps takes turns on the one GPU and the memory.

- `render_*` tools always return a job at once. Other tools try to finish within about 20 seconds, then hand the rest to a job. MCP clients give up on a call after about 60 seconds, so no call may outlast that.

```json
{ "ok": true, "summary": "Rendering intro (240 frames). Job job_7f3a is queued, 1 ahead of it.",
  "data": { "job_id": "job_7f3a", "status": "queued", "position": 1 } }
```

- `inspect_job { "job_id": "job_7f3a", "wait_s": 20 }` waits up to `wait_s` (at most 25) and returns the result, or how far it has got (`"frames 120 of 240"`).
- Jobs live in the project service, not in the MCP server, so they survive a server restart. A job that was cut off says so; it is never just "unknown".
- Asking for the same work again joins the running job instead of starting a second one.
- The CLI (`rostrum-2d render …`) waits and prints progress instead of returning a job id.

## 8. How agents see

Every `look_*` tool draws through the **same render path as export** (preview ≡ export). `quality: "fast" | "final"` picks the same Fast / Final as the GUI.

| Tool | Returns |
|---|---|
| `look_frame` | One picture at a time or marker. Optional `overlays`: item ids, bounding boxes, a coordinate grid, safe areas. Optional `region` to zoom in |
| `look_sheet` | A contact sheet: several frames over a range in one image, each tile labelled with its time and frame |
| `look_motion` | What moves and how: each move's start, landing, ease and speed; pacing findings; optional curve chart or motion sheet (ghosts of earlier frames and arrows showing where things go next) |
| `look_at` | "What's here": given `x, y` (pixels) and a time, the items under that point, top first, with ids and bounds |
| `look_compare` | Two pictures side by side with a difference view: a version against an earlier one, or our shot against a private reference |

- **Painting:** the grid overlay and `look_at` let an agent know exactly where a stroke will land, and a frame after the stroke shows what it did. The painting kit's tools use the same coordinates.
- **3D** looks through the **shot camera** (built for the camera, not a game). It adds coverage maps (what the camera sees) where useful.
- **The Editor** adds scopes (waveform, vectorscope, histogram) and cut checks.

## 9. How agents hear

Agents can't listen directly, so sound is turned into things they can check.

| Tool | Returns |
|---|---|
| `look_loudness` | Integrated loudness (LUFS), a short-term loudness curve, true peak, and every clipped or near-clipping moment with its time |
| `look_spectrum` | A spectrogram picture, with time and frequency labelled, for the whole piece or a range |
| `look_waveform` | A waveform picture with peaks marked, per track or for the mix |
| `look_events` | Onsets, beats, bars and the tempo map, as times, usable as markers |
| `look_clip` | A short preview WAV (up to about 10 seconds) for clients that can play sound, plus its path |
| `look_describe` | A written description of a stretch of sound from a vetted local AI audio model (loaded on demand) |

Sound has these first. The Editor uses the same tools on its mix. 2D and 3D use them only on their sync sound.

## 10. Help and discovery

- `inspect_operations` lists every operation from the **one registry**: the same list the GUI's inspector and command bar are built from. Nothing is listed by hand.
- `inspect_guide` returns how-to guides: techniques and how tools work, never style rules or finished pieces to copy.
- The MCP handshake's `instructions` hold a short "start here" for the app. The guides are also published as MCP resources (`rostrum://guide/<topic>`).

## 11. What `rostrum_core` provides and what each app adds

**`rostrum_core` provides:** the MCP server (stdio), tool registration from a name, a schema and a function; argument checking; the error type, codes, the one-line format and "did you mean"; the reply shape; who and group for every change; handing work to the jobs queue and checking on it; the shared tools in §2; guide resources.

**Each app adds:** its tools, as plain functions:

```python
from rostrum_core.mcp import tool, Reply

@tool("look_frame", schema=LookFrameArgs)
def look_frame(ctx, args: LookFrameArgs) -> Reply:
    picture = ctx.app.render_frame(args.item, ctx.time(args.at), quality=args.quality)
    return Reply(summary=f"Frame {picture.frame} of {args.item}.", data=picture.facts, images=[picture.png])
```

An app never writes its own error format, job handling or author tracking. If it needs something new there, Team Sam adds it to `rostrum_core` first.
