# Guides drawer, key list, hover help, empty states and focus: how an app plugs in

*Team Sam, S34, 2026-10-22. Builds INTERACTION.md Part 5 pieces 16 (guides drawer and key list), 17 (hover help),
19 (empty state) and 20 (focus and areas), and their layout states (22). The rules are INTERACTION.md 1.16, 1.17 and
1.20. Files and the start screen are in `FILES.md`; the Export sheet and the Problems / job chips in `EXPORT.md`.*

## The pieces

| Piece | File | Does |
|---|---|---|
| Guides drawer | `qml/RostrumKit/GuidesDrawer.qml` (replaces `GuideDialog.qml`, deleted) | The app's guides in a drawer on the left, beside the main view (360 px, at most 30 % of the window), in the left panel's place while open, pushing the main view aside. Lists the guides; "Find in the guides" searches titles and text (`guidePages.search`) and shows the first matching line; links between guides open in it, Back returns (to the list from the first guide); pictures are scaled to the drawer's width (`guidePages.readAt(url, width)`). × or Esc closes it. |
| Faults and event filters | `rostrum_gui/qt_faults.py`, `rostrum_gui/gui_filter.py` | Qt's "not supported" warnings and every Python error that escapes into Qt (a slot, a QML call, an event filter, a worker thread) are faults: the traceback goes to the log, a person's run carries on ("FAULT: …"), a scripted run fails with exit code 6. Every Python event filter is a `GuiFilter`: installed on a window (never the whole app, whose filter Qt also calls from its own image-loading threads: the A1b crashes), runs only on the GUI thread, and an error in it is reported, never escapes. |
| Key list | `qml/RostrumKit/KeyList.qml` | Ctrl+/: every key of the app grouped by job (area), searchable, built from the same key map the shortcuts come from (`bridge.actions.keys`, else the shared map `sharedKeys`), so it can't go out of date. |
| Hover help | `qml/RostrumKit/HoverTip.qml`, `Button.qml`, `IconButton.qml`, `InspectorRow.qml` | After 500 ms: **name**, one plain sentence, and the key chip, on one line kept inside the window (too long ends in "…"). Buttons gain `help` (the sentence) and `job` (a key map job: its key is looked up, `AppShell.keyFor(job)`); Button also `tip` (a name when its text doesn't say it). A settings row's label shows its setting's own `help`. |
| Empty state | `qml/RostrumKit/EmptyHint.qml` | One centred line (`text`) and up to two `buttons` ([{value, label}], the first is the main one; `picked(value)`). The owner hides it once there is something. Used by the command box ("Nothing called "xyz". Try a shorter word."), History, the guides drawer, the key list, 2D's canvas and rows, Sound's new song. |
| Focus and areas | `qml/RostrumKit/AppShell.qml`, `rostrum_gui/focus_areas.py` | The area last pressed (guides, left, centre, right, bottom; seen by a window event filter that `start` installs, before any item can swallow the press) takes the keys. F6 moves to the next area, which then shows a 2 px accent line on its top edge (a press shows none). Ctrl+\ folds the side panels (a sheet or History unfolds them). Whenever the keys would land nowhere (a dialog or sheet closed, Esc or Enter in a field) they go back to the main view (`backToWork()`). `bridge.setFocusArea(name)` (kit DocBridge) keeps the area for `inspect_screen`, named by the app's `areaNames`. |
| ? menu | `qml/RostrumKit/TopBar.qml` | Guides (F1) · Keys (Ctrl+/) · Connect an AI agent… · the app's own entries · About and licences. F1 opens the guides drawer (it used to open About). |
| Shell keys | `qml/RostrumKit/KeyMap.qml` | The kit's KeyMap never makes the keys AppShell binds itself (`shell`: undo, redo, Ctrl+K, History, guides, the key list, F6, Ctrl+\, Export, Export again), so no app can make them ambiguous. |
| Steps | `rostrum_gui/shell_steps.py` (via `layout_run.kit_step`) | `guides open [file.md]`, `guides find <words>`, `keylist open`, `panels fold`, `area <name>`, `hover <objectName>`. |

Pictures: `C:\Users\Sam\.rostrum\waves\results\kit\s34\shell\` (the kit demo: `demo/main.py --size 1280x720 --step
"guides open easing-and-overlap.md" --shot …`; the demo lists Rostrum2D's guides).

## Plugging in (any app)

Nothing to add for the drawer, the key list, F1 / F6 / Ctrl+/ / Ctrl+\ or the accent edge: every AppShell has them,
and the guides come from the `helpEntries` the app already passes. Then:

```qml
AppShell {
    helpEntries: guides                                     // as before: the drawer lists them
    areaNames: ({ centre: "canvas", right: "settings", bottom: "timeline" })   // optional: inspect_screen's words
    // hover help: give buttons a sentence and their key map job (the key is looked up)
    actions: [ Button { text: "Import"; job: "add_file"; help: "Bring in pictures, video, sound or a Lottie file." } ]
    // an empty place: one line, at most two buttons, gone once there is something
    centre: [ Canvas { }, EmptyHint { visible: backend.layers.length === 0; text: "Draw a shape (R), type (T), paint (B), or drop a file here." } ]
}
// an app dialog of its own (not a kit one): give the keys back to the work when it closes
AskDialog { onClosed: shell.backToWork() }
```

- **Don't** make your own Shortcut for F1, Ctrl+/, F6, Ctrl+\, Ctrl+K, Ctrl+H, Ctrl+Z or Ctrl+E: the shell has them
  (two Shortcuts on one key make Qt fire neither).
- **Hover help for settings** comes from each Param's `help`: write one plain sentence there, never the label again.
- **Layout states:** `guides-list`, `guides-find`, `key-list`, `panels-folded` are in both apps' `layout_states.py`; the
  old `guide` state now shows the drawer.

## Notes for Team Hem (Rostrum2D)

- `Main.qml`: an `EmptyHint` over the canvas while the scene has no layers (Move tool only), and `areaNames`.
  `LayerTimeline.qml`: the rows' empty line is the kit's EmptyHint ("Your layers appear here as bars. Drag a bar to
  change when it shows."). Keep both when you merge H30; if the canvas moves into another item for zoom, keep the
  hint outside the zoomed item so it never scales.
- `screen_seen.py` reads `bridge._focus_area` (now set by the shell): "canvas", "settings", "timeline", "guides".
- Still to do in 2D (not kit): `help` / `job` on the tool strip and top-bar buttons (the kit's Button / IconButton
  take them; the ToolStrip's own buttons need a HoverTip with `key`).

## Notes for Team Priyam (RostrumSound)

- `Arrangement.qml`: the new song's three lines became one EmptyHint ("Start with a sound, or drop a file here.",
  Add a track · Bring in a picture).
- Sound's own Shortcut for F1 is not needed (the shell's opens the drawer); `keys.SKIP` can drop "guides".
- Sound keeps its finer focus (`select_slots.focusArea`: arrangement / editor) for `inspect_screen`; the shell's
  accent edge marks the region.
- Still to do in Sound: `help` / `job` on the header strip's buttons.
