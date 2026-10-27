# The one action list: how an app plugs in

*Team Sam, S31, 2026-10-22. Builds INTERACTION.md Part 5 pieces 1–5: one action list, the context bar, menus with
keys, one key map, the selection rules. The rules themselves are INTERACTION.md 1.2, 1.3, 1.13 and Part 2.*

## The pieces

| Piece | File | Does |
|---|---|---|
| Action list | `rostrum_gui/actions.py` | `Action` (data) and `ActionList`. **One guard** for every door: too few or too many selected (`min_targets`, `max_targets`), a kind it doesn't take (`kinds`), the registry's `valid_when` on an item, `when` (a data condition on the selection's facts), `valid` (an app function, last resort), calls that would change nothing. Why-not sentences for a key pressed or a name typed. |
| Views | `rostrum_gui/action_views.py` | The same entries arranged for the context bar, right-click (edit block last, long choice sets folded into a side menu) and Ctrl+K. |
| Key map | `rostrum_gui/keymap.py` | Every shared key of Part 2. `KeyMap(app, app_keys)` refuses, at start-up, an app key that takes a shared one or one key meaning two things. An action names a shared `job` (its key comes from the map) or an app `keys`. |
| Hub | `rostrum_gui/action_hub.py` | `ActionHub`: the one adapter an app's bridge hosts. QML reads `bar`, calls `menu()`, `commands(q)`, `run(id)`, `key(job)`; `keys` and `jobs` feed `KeyMap.qml`. Every door re-reads the list when used. |
| Adapter | `rostrum_gui/action_adapt.py` | `from_dicts(dicts, keymap)`: turns the older dict shape (Sound's P27) into Actions unchanged. |
| Selection | `rostrum_gui/selection_rules.py` | `click` (lists: Ctrl adds, Shift runs; canvas: Shift adds, Ctrl deepest), `box`, `select_all`, `esc_step` (the Esc ladder). Pure; selecting is never an undo step. |
| Context bar | `qml/RostrumKit/ContextBar.qml` | Fixed top-centre of a view: count chip, up to 5 actions by rank, folds into ⋯ when narrow, hidden while dragging, `toolOptions` slot for a tool's options. |
| Menu | `qml/RostrumKit/ActionMenu.qml` | Right-click: keys on every row, dividers between groups, `openAt(x, y)` stays on screen, side menus. Every popup is sized and placed once, before it shows (`MenuPlace.settle`), and never moves while visible. |
| Keys | `qml/RostrumKit/KeyMap.qml` | One `Shortcut` per key map entry, calling `hub.key(job)`. Never write a QML Shortcut for an action. |
| Ctrl+K | `qml/RostrumKit/CommandBar.qml` | Rows show their keys. |

Test: `tests/test_actions.py` (an action needing two never shows for one, in any door; the key map refusal).
From a worktree: `PYTHONPATH="shared/gui-kit;shared/core" python -m pytest shared/gui-kit/tests/test_actions.py -q`.

## Plugging in (any app)

```python
keys = KeyMap("RostrumSound", SOUND_KEYS)                       # the app's own keys, as data
actions = ActionList(ACTIONS, keys, noun="item")                # ACTIONS: kit Actions (or from_dicts(old, keys))
hub = ActionHub(actions, facts_fn, what_fn, apply_fn, do_fn, message_fn)
#   facts_fn() -> the app's Facts (.ids, .items, optional .doc, .facts, anything its conditions read)
#   what_fn(facts) -> "3 notes";  apply_fn(calls, label) -> ONE undo step;  do_fn(name, entry) -> copy / rename …
#   message_fn(text) -> the status line.  Call hub.refresh() after any selection, playhead or document change.
```

```qml
ContextBar { hub: backend.actions; dragging: view.dragging
             anchors.top: view.top; anchors.topMargin: Theme.gap; anchors.horizontalCenter: view.horizontalCenter
             maxWidth: view.width - 2 * toolStripWidth }
ActionMenu { id: menu; onPicked: (v) => backend.actions.run(v) }
//   right-click: select the item alone if it isn't selected, then: menu.entries = backend.actions.menu(); menu.openAt(x, y)  (window coords)
KeyMap { hub: backend.actions; enabled: !typing }               // in the root window
```

Do not bind `hub: hub` when the context property is called `hub` (QML then reads the item's own empty property).

**No action is silent (INTERACTION.md 1.21 rule 9; `rostrum_gui/told.py`).** While an action runs, the hub watches its
host bridge's `docChanged` and `status` (the kit DocBridge has both). If the document changed and nothing was said,
the hub says the action's own words: its `done` (`Action(..., done="Grouped {what}")`, or `done(what) -> str`), else
"<label> · <what>" ("Auto layout · 3 layers"). An app's own sentence always wins; this is the floor, so a new action
can never act silently. Give an action a `done` when its past tense reads better than its label.

## Notes for Team Hem (Rostrum2D)

2D runs on the kit list on `team/sam` (commit 9a0ee57):
- `screen2d/actions.py`: kit Actions, `LIST = ActionList(ACTIONS, KEYS2D, noun="layer")`. Group, mask, combine and
  similar carry `min_targets`; distribute needs 3; combine is promoted for shapes. A locked layer takes only Unlock
  (a `valid` wrapper). Paste style is absent until a style is copied.
- `screen2d/keys2d.py`: 2D's own keys (P, Alt+N, Alt+Shift+N, Alt+O, Shift+A, Alt+A/D/W/S/H/V, Ctrl+Alt+M,
  Ctrl+Alt+U/S/I/X). Add a 2D key here, never in QML.
- `screen2d/action_slots.py` hosts the hub as `backend.actions`; it also keeps `actionMenu()`, `layerMenu(id)`,
  `run("layer:<name>")`, `layerCommand(how)`, `stepBack(...)`. Gone: `actionBar()`, `selectionExtent()`, 2D's
  `ActionBar.qml` and `ActionMenu.qml`.
- `Stage.qml`: the kit ContextBar at the top-centre of the canvas; canvas right-click (an unselected layer is
  selected alone first). `Main.qml`: one kit KeyMap; canvas Esc through `backend.stepBack` (the kit's Esc ladder).
  `LayerRows.qml`: the kit ActionMenu. `multi.py`: Ctrl / Shift in the rows through `selection_rules.click`.
- **H29's pure-data actions:** the kit Action now takes `when` (a data condition, checked as
  `holds(when, {}, facts.facts)`), so H29's dicts map straight onto Actions with `calls=lambda f: calls_of(spec, f, …)`.
  Replace S31's lambdas in `actions.py` with H29's data and resolver; keep the kit API.
- **H29's tool options** (Pen: Close path, Done; Paint: size, colour, opacity, eraser) go into ContextBar's
  `toolOptions` slot, not a second bar.
- **Left for Hem:** Alt+←/→ (frame step) takes the shared fine-nudge key and Alt+↑/↓ (hold longer / shorter) should be
  `=` / `−` (Part 2): move them; the canvas box doesn't get modifiers yet (Shift adds, Ctrl deepest); the right-click
  menu for two layers is 18 rows: give the three extra mask choices and the make set a `bar` to fold them; Ctrl+K's
  file commands still write keys "Ctrl N" while actions write "Ctrl+G".

## Notes for Team Priyam (RostrumSound, P27)

Proof: P27's own list (read from `team/priyam`, read only) through the adapter on a real song:
`shared/gui-kit/demo/sound_proof.py`, pictures in `C:\Users\Sam\.rostrum\waves\results\kit\s31\sound\`.

Plug in, after merging main once S31 is in:
1. Move `shared/gui-kit/demo/sound_keys.py` (`SOUND_KEYS`, the [Sound] rows of Part 2) into Sound, e.g.
   `screensound/keys.py`. `keys = KeyMap("RostrumSound", SOUND_KEYS)`.
2. `ActionList(from_dicts(ACTIONS, keys), keys, noun="item")` — your dicts load unchanged (all 37 do). Better still,
   write them as kit Actions directly later; the adapter is the bridge, not the goal.
3. Add `"min_targets": 2` to `sel:group` (send to a new group) and `sel:layer` (layer as one sound), so the kit's guard
   holds it and the why-not sentence is right. The proof does this for you in `with_counts`.
4. One `ActionHub(list, facts_fn, what_fn, apply_fn, do_fn, message_fn)`; `facts_fn` returns
   `Facts(doc, ids, playhead, range, clipboard, track)`; `what_fn` "3 notes"; `do_fn` handles copy, cut, paste,
   rename, inside. Call `hub.refresh()` on selection, playhead, range and document changes.
5. QML: the kit ContextBar at the top-centre of the focused area (arrangement or Editor), one kit ActionMenu,
   `CommandBar` rows from `hub.commands(q)`, one kit KeyMap in the root window. Delete Sound's `ActionBar.qml`,
   `ActionMenu.qml`, `HintMenu.qml` and stop reading `sel:` keys (the adapter drops the prefix).
6. **Keys the adapter mapped** (no refusals): Up / Down (half step) and Shift+Up / Down (octave) are the shared nudge
   keys (1.7: arrows move notes in pitch, same meaning); Shift+Delete (cut out and close the gap) is the shared
   `delete_close_gap`; Delete also takes Backspace; Ctrl+[ / ] (move track) are the shared back / forward; Ctrl+G,
   Ctrl+D, Ctrl+T, Ctrl+J, Ctrl+C / X / V, F2, Ctrl+Shift+L are shared; Q, Shift+M, Shift+S are Sound's own.
   Ctrl+↑ / ↓ (scale step) are in `SOUND_KEYS` but P27 has no action for them yet.
7. **Spec points:** Duplicate is in the edit block, so it never sits on the bar (1.2 point 4), though DESIGN.md 3.0 put
   it there for notes, hits and a time range. "Layer as one sound" is secondary (⋯ and menus only); make it primary
   if it belongs on the bar for two clips. Crossfade and Even out level have no keys.

## Settings row pieces: a note and a button (rows.py, InspectorRow.qml, RowButton.qml)

- **Note under a field.** An app adds `note = {"text", "kind": "hint" | "warning"}` to a param row (None = nothing to say).
  The kit row draws one short line under the field (warning colour for "warning") and grows by its height only while the
  note exists, so there is never an empty gap. Work it out live from the document when the rows are built (3D: the Bevel
  row, `actions3d.fit_note`). Not drawn on a paired row or a list / curve row.
- **Button on a row.** Give an `Action` `row="<param id>"` (and optionally `row_label`, text or a function of the facts,
  for its word on the button). It then shows as a small button at the right of that field (the field narrows inside its
  own column, so the grid holds) and no longer on the context bar, the panel's action list or the right-click menu; Ctrl+K and
  agents still reach it as the same action. Several actions on one row with the same `bar` name are one button with a menu.
  The app adds `row_buttons()` (`ActionHub.row_buttons`) to its rows as `button` and gives its bridge a `rowAction(id)` slot.
  3D: Lenses on Focal length, Pick on Focus on, Use N mm on Bevel.
- **A unit never cuts its number.** A number field keeps the unit's room out of the number's, rounds to fewer decimals when
  the field is narrow, and shows every digit again while you type.
