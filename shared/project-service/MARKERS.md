# Shared markers — how to use them (API note for every app)

*Team Sam, S11, 2026-10-21. Code: `shared/core/rostrum_core/markers.py`. Agent tools: `inspect_markers`, `edit_markers` (every MCP server has them).*

A project has **one list of named markers** ("logo lands", "drop"). Every app reads the same list; cross-app timing ties
to a marker by name, never to a copied number (AGENTS.md rule 8). A marker is:

```json
{ "id": "mk_logo_lands_1", "type": "marker", "name": "logo lands", "at": 2.5, "owner": "2d", "colour": "#f2b33d" }
```

- **id** never changes (renaming keeps it); **name** is unique in the project (case and outer spaces ignored).
- **at** is seconds on the project timeline (0 or later), never beats: an app with a tempo map turns beats into seconds itself.
- **owner** (optional): the app it belongs to (`2d`, `sound`, `3d`, `edit`); **colour** (optional): `#rrggbb`.
- **who made it / changed it** comes from the list's own history (`by`, `changed_by` in `listing`).
- Stored as a small document of its own: `<project>/docs/markers.mkr`, history in `.rostrum/markers.history.jsonl`.
  Every change is an operation in that history: undo, who changed what, "changed outside Rostrum" all work.

## Changing markers (operations)

| Operation | Target | Args |
|---|---|---|
| `marker.add` | — | `name`, `at`, optional `id` |
| `marker.move` | marker ids | `at` |
| `marker.rename` | one marker id | `name` |
| `marker.colour` | marker ids | `colour` |
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
markers.version(folder)          # a number that changes whenever the markers change (0: none yet)
markers.refuse_clashes(times, local_names, where)   # loud error: a local marker named like a project one
markers.used(times, names)       # {name: seconds} of only the markers a document uses: its render cache key part
```

On a Qt screen, `rostrum_gui.markers.MarkerWatch(folder)` keeps `times` fresh (another app or an agent may change the
file), emits `changed`, gives `rows()` for ruler flags and `snap(t, within_s)` for anything dragged along time.

## Who uses it now

- **2D:** ruler flags on every page, a faint line through the Animate timeline, keys dragged within 6 px land on a
  marker, expressions' `marker("drop")` read the project's list (render, look_frame and the screen all pass it).
- **Sound (P14, P15):** times like `"#drop+0.5"` and note lengths `{"to": "#land"}` read the project's list
  (`rostrum_sound/doc/markers.py`, the one place Sound reads them), so a marker moved in 2D or by `edit_markers` moves
  the sound on the next render; a rename is followed as one undo step (`marker.follow`); a deleted marker the song
  uses fails the check and the render, naming item and field; a local marker named like a project one is refused.
  On the screen, project markers show dashed on the marker band and drag there (one `marker.move` per release).
- **Agents:** `inspect_markers` (all, or `name: "drop+0.5"` for one time), `edit_markers` (`ops` as above).

## Request to Team Priyam: switching `rostrum_sound/doc/markers.py`

Answers to `results\stage2\sound-p13\what-sound-needs-from-shared-markers.md`, point by point:

1. **Fields:** id, name, at (seconds), owner, colour: all there.
2. **Lookups:** `listing` (all), `find(rows, name_or_id)`, `times`; "changed": `version(folder)` or `MarkerWatch.changed`.
3. **Renames:** `marker.rename` keeps the id. Sound rewrites its `#old` references itself, as one operation in
   Sound's own history: on `MarkerWatch.changed`, compare `listing()` by id with the names you last saw.
4. **Deleted marker:** `times()` no longer has it; Sound's resolver raises not-found naming item and field (as now).
5. **Local markers stay local. A shared and a local marker with the same name is an error** (manager's decision,
   2026-10-21): call `refuse_clashes(times(folder), local_names, where)` in Sound's check and before a render.
6. **Cache key:** `used(times(folder), names_the_doc_uses)`, not the whole list.

The only change needed in Sound: `markers.items(doc)` must also see the project's markers, so the module needs the
project folder (today it gets only the document's root dict). Suggested: `items(doc, folder=None)` returns the
local markers plus `times(folder)` as `{"id", "name", "at"}` rows (project ones marked `"shared": True`), after
`refuse_clashes`; callers that have the Document pass `doc.folder`. Writes to project markers go through
`markers.edit(folder, calls, who)`. Sound's MCP server already has `inspect_markers` / `edit_markers` from
`rostrum_core`; drop any Sound-only tool of the same name.
