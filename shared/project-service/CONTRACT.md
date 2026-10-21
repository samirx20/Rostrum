# Project service — the contract

*Team Sam, brief S1 · P-REPO, 2026-10-21. Draft for review. Built from the experiment's markers, cache and job code (archive `docs/MARKERS.md`, `docs/EDIT_MODEL.md`, `src/engine/cache/cache.ts`, `cacheTrim.ts`, `src/engine/native/binary.ts`, the analysis keys in `src/engine/editor/stabilise/analyse.ts`), rewritten for Python.*

The project service is **one small background program** that all four apps talk to. It keeps the project's list of items, the shared markers, the live links between apps, the shared cache, and **one jobs queue for the whole machine**. It is written in Python on `rostrum_core` (see `shared/core/OPERATIONS.md`), starts with the first app that needs it, and stops when the last app closes and no job is running. Apps reach it over a local connection with small JSON messages; the Python client is `rostrum_core.project`.

It never edits a document itself. Documents are changed only by their own app, through operations.

## 1. The project folder

People never see or name files (decided 2026-10-20: one project, files hidden, saving is automatic). Underneath, a project is one folder:

```
My Film/
  project.json        the item list and project settings (frame rate, colour setup, sample rate)
  docs/               each app's documents: <item>.mtn (2D) · .trk (Sound) · .trd (3D, USD) · .rsm (Editor)
  data/               analyses stored as editable data (tracks, transcripts, beat grids, masks a person touched up)
  media/              footage, pictures and sounds brought in
  renders/            hand-off renders, one folder per item and version: renders/<item>/v003/ (see shared/HANDOFFS.md)
  exports/            final deliveries from the Editor's Deliver page
  colour/             the project's one OpenColorIO config (shared/HANDOFFS.md › Colour)
  .rostrum/           history and script records per document (see OPERATIONS.md), document locks
```

An **item** is one thing in the Project panel:

```json
{ "id": "itm_logo", "kind": "2d", "name": "Logo sting", "file": "docs/itm_logo.mtn",
  "seq": 42, "hash": "9f2c…" }
```

- Kinds: `2d`, `sound`, `3d`, `edit`, `media`, `render`, `data`.
- The **id never changes**; the name can. Everything that points at an item (links, markers, renders) uses the id.
- `seq` and `hash` are the item's latest history step and content, so anyone can tell at a glance whether it changed.
- Brought-in media is copied into `media/` and named by its content, so the same file brought in twice is stored once and moving the project moves everything.

## 2. Shared markers: sync by name

Lining things up by copying numbers breaks the moment one thing moves. So every document **publishes its named moments**, and anything can tie a time to one by name (AGENTS.md rule 8).

- **Each document keeps its own markers** (Sam's choice, 2026-10-12: no separate project marker file, so there is one source of truth). 2D publishes its timeline labels (`logo_lands`), Sound its labels (`drop`), 3D its contacts (`hit:can>table`), the Editor its markers plus every clip's start and end.
- The **music's beat grid** works as markers too (`music#bar:9`, `music#beat:9:3`), worked out from tempo and time signature, never stored.
- A reference is **item and marker**, with an optional offset: `music#drop`, `ui#press+0.5`, `music#bar:9`. The document stores the reference next to the time it last resolved to:

```json
{ "at": 12.5, "ref": "itm_music#drop" }
```

- The service keeps an index of every published marker, so an app or agent can ask:

```python
project.markers()          # [{"ref": "itm_music#drop", "name": "drop", "item": "Music", "at": 12.5}, ...]
project.marker("itm_music#drop")   # 12.5, or a loud error naming the markers that do exist
```

- **When a marker moves**, the service tells every app holding a reference to it. Following Sam's 2026-10-12 answer: single times (a sound cue, a voice line, a clip start) are **re-timed in place** as an operation by `outside: marker moved`; animation tied to it is **reported as out of date** ("music#drop moved 12.0 → 12.5; 3 cues tied to it") until its script runs again.
- A marker that is deleted or renamed leaves its references reported as broken, never silently pointing at nothing.

## 3. Live links between apps

A **live link** is one item used inside another — a 2D comp placed on the Editor's timeline, a Sound mix under a 3D shot.

```json
{ "link": "lnk_7", "from": "itm_logo", "use": "render", "into": "itm_edit", "version": "latest" }
```

- When the source item saves, the service sends `item.changed(id, seq, hash)` to everyone using it. The Editor asks for the new render through the jobs queue and swaps it in. Until it arrives, the old frames show with a clear **"updating"** mark — never stale frames passed off as current.
- `"version"` may be pinned to a named version instead of `latest`, so a locked cut doesn't change under the editor.
- **Read-only context:** any app can show the rest of the project at the same moment (the music under a 2D animation, the edit around a 3D shot) using Fast-quality renders from the cache. It cannot be edited there. Double-clicking it opens the item in its own app at that moment (decided 2026-10-21).
- A link that would make a loop (A inside B inside A) is refused with an error naming the loop.
- Frames from different apps are **combined only in the Editor** (rule 8). Other apps only show them as context.

## 4. Analyse once, store as data (AGENTS.md rule 7)

Simulations, tracking, mattes, stem separation, transcripts and beat detection are **computed once, on request**, then stored. Renders only **read** them.

- Anything a person or agent might edit, or that took real effort to get right, is stored as **data in the project** (`data/` or in the document itself): tracker points, transcript words, a detected beat grid, a mask someone touched up. It travels with the project and is never thrown away by the cache.
- Bulky results that can be made again exactly (decoded frames, a baked simulation, separated stems from the same settings) go in the **cache** (§5). The document records the job's recipe and its cache key.
- A render that finds an analysis missing **does not run it quietly**: a preview shows a "needs analysis" placeholder; an export lists the missing analyses and queues them as their own visible jobs first. Nothing renders with a step quietly skipped.
- If a cached result was thrown away, the same recipe is queued again, and the app says so.

## 5. The shared cache

One cache for the whole machine, shared by all four apps and every project.

- **Key** = a fingerprint (SHA-256) of: the job kind, the engine and its version, the content of every input, and the settings written out in a fixed order.

```python
key = cache_key(kind="track", engine="rostrum-track@3", inputs=[clip_hash], settings={"from": 1.0, "to": 4.0})
```

  A new engine version means a new key, so an old result is never used by mistake.
- **Where:** `C:\Users\<user>\.rostrum\cache\` on Windows, `~/Library/Caches/Rostrum/` on Mac; one folder per kind, one entry per key, each with a small `entry.json` (what made it, inputs, when, size, how long it took).
- **Written safely:** an entry is written under a temporary name and renamed when complete, so a half-made entry is never visible. A failed or cancelled job leaves nothing.
- **Size cap:** one cap for the whole cache, set in settings (default 20 GB). When over the cap, the **least recently used** entries go first. An entry used in the last 15 minutes, or used by a running job, is never removed.
- The same job asked for twice — by two apps, or twice by one — runs **once**; both get the result.

## 6. One jobs queue for the machine

The laptop has 16 GB of memory and one 4 GB graphics card, shared by every app. Every heavy job from every app takes its turn in **one queue**.

```json
{ "job": "job_118", "kind": "ai.voice", "app": "sound", "item": "itm_vo", "label": "Voice line 3",
  "needs": { "ram_gb": 1.8, "gpu_gb": 3.0 }, "lane": "background",
  "state": "running", "progress": 0.4, "note": "line 3 of 8", "timeout_s": 600 }
```

- **Job kinds** include: `render.preview` (light, a frame or two), `render.final` (exports and hand-off renders), `sim` (cloth, fluids, particles), `track` and `stabilise`, `ai.voice`, `ai.stems`, `ai.mask`, `ai.depth`, `ai.transcribe`, `encode`. Each kind declares what it needs; AI models use the measured numbers from the models doc (`docs/AI_MODELS.md`).
- **Memory gate:** a job starts only when the machine really has the memory it needs, read from the system and the graphics card, not just from our own bookkeeping (other programs use memory too).
- **One graphics-card job at a time.** Heavy computer-only jobs run at most two at a time.
- **Two lanes:** quick `interactive` jobs (the frame a person is looking at) go ahead of long `background` ones, so the screen never waits behind an export.
- Each job runs in **its own worker process**. Models load for the job and are released when it ends; the memory comes back because the process ends.
- **Waiting is shown:** "waiting for memory: needs 3.0 GB on the graphics card, 1.2 GB free". A job that can never fit (needs more than the machine has) fails at once and says so.
- **Progress** goes to the app that asked and to MCP (`0.4`, "line 3 of 8").
- **Cancel** ends that job's worker process by its own process id, and removes its partial output.

### Fail loudly
- Every job has a time limit for its kind, plus a watchdog: no progress for too long counts as stuck.
- A job that fails, times out or crashes ends as **failed**, with the reason, what it was doing and its last log lines. Its partial output is deleted. **Nothing goes into the cache or the document**, and the operation waiting on it is not applied.
- An export never reports success with a missing frame or a cut-short sound file. It reports which frame or job failed.
- If the service itself stops, jobs that were running are marked failed ("service stopped") when it comes back, never quietly resumed or dropped. Running them again is one click or one call.

## 7. What apps and agents can ask

Over the client in `rostrum_core.project`, and the same through each app's MCP server (tool names and reply shapes follow `shared/mcp/CONVENTIONS.md`):

| Ask | Answer |
|---|---|
| `items()` / `item(id)` | the item list; one item with its kind, name, latest step |
| `markers()` / `marker(ref)` | every published marker; one marker's time |
| `link(from, into)` / `links(item)` | make a live link; what an item uses and is used by |
| `context(item, time_range, quality="fast")` | read-only frames or sound for showing context |
| `job.submit(...)` / `job.status(id)` / `job.cancel(id)` / `jobs()` | the queue |
| `cache.get(key)` / `cache.stats()` | a cached result; the cache's size and cap |

How renders are handed between apps (EXR layers, WAV stems, frame numbering) is in `shared/HANDOFFS.md`.

## Settled defaults (lead, 2026-10-21)

- **Projects carry their renders.** Each project keeps its finished hand-off renders in `renders/` (old versions are cleared by the service's clean-up, never by an app), so it opens on another computer (or after the cache is cleared) without re-rendering everything. Bigger folders, but nothing breaks when a project moves.
- **Default cache cap: 20 GB** (the experiment used 10 GB). A setting; change it in settings.
