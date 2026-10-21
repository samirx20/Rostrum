# Shared markers — how to use them (API note for every app)

*Team Sam, S11, 2026-10-21. Code: `shared/core/rostrum_core/markers.py`. Agent tools: `inspect_markers`, `edit_markers` (every MCP server has them).*

A project has **one list of named markers** ("logo lands", "drop"). Every app reads the same list; cross-app timing ties
to a marker by name, never to a copied number (AGENTS.md rule 8). A marker is:

```json
{ "id": "mk_logo_lands_1", "type": "marker", "name": "logo lands", "at": 2.5 }
```

- **id** never changes (renaming keeps it); **name** is unique in the project (case and outer spaces ignored).
- **at** is seconds on the project timeline (0 or later).
- **who made it / changed it** comes from the list's own history (`by`, `changed_by` in `listing`).
- Stored as a small document of its own: `<project>/docs/markers.mkr`, history in `.rostrum/markers.history.jsonl`.
  Every change is an operation in that history: undo, who changed what, "changed outside Rostrum" all work.

## Changing markers (operations)

| Operation | Target | Args |
|---|---|---|
| `marker.add` | — | `name`, `at`, optional `id` |
| `marker.move` | marker ids | `at` |
| `marker.rename` | one marker id | `name` |
| `marker.remove` | marker ids | — |

```python
from rostrum_core import Who, markers
markers.edit(folder, [{"op": "marker.add", "args": {"name": "drop", "at": 12.5}}], Who.person())   # saves at once
```

`edit` opens the list fresh, applies the calls all-or-nothing as one change, and saves. A duplicate name, a negative
time or an unknown id fails loudly and nothing is saved.

## Reading markers

```python
markers.listing(folder)          # [{id, name, at, by, changed_by}] by time; [] when the project has none yet
markers.times(folder)            # {name: seconds}: cheap, re-reads the file only when it changed (fine every frame)
markers.at(folder, "drop+0.5")   # seconds of a reference: name or id, optional +/- offset; loud error naming the markers
markers.find(rows, "Drop")       # one row by name or id, loud error otherwise
markers.lookup(times, "drop")    # seconds or None, from a times() dict
```

On a Qt screen, `rostrum_gui.markers.MarkerWatch(folder)` keeps `times` fresh (another app or an agent may change the
file), emits `changed`, gives `rows()` for ruler flags and `snap(t, within_s)` for anything dragged along time.

## Who uses it now

- **2D:** ruler flags on every page, a faint line through the Animate timeline, keys dragged within 6 px land on a
  marker, expressions' `marker("drop")` read the project's list (render, look_frame and the screen all pass it).
- **Agents:** `inspect_markers` (all, or `name: "drop+0.5"` for one time), `edit_markers` (`ops` as above).

## Request to Team Priyam (P13 "one markers module in Sound")

Point Sound's markers module at this list instead of markers kept inside the Sound document:
1. Reads: `markers.listing(folder)` / `markers.times(folder)`; screen flags through `MarkerWatch`.
2. Writes (Sound's add / move / rename / delete marker actions): `markers.edit(folder, calls, who)` with the four
   operations above, so the change lands in the shared history with the right author.
3. Existing Sound documents with their own markers: copy each once into the shared list (`marker.add`, same name and
   time) on open, then stop reading the document's copy. Notes that point at `"#land"` keep working by name.
4. Sound's MCP server gets `inspect_markers` / `edit_markers` from `rostrum_core` automatically; drop any Sound-only
   marker tool of the same name.
