# History, the top bar and the agent pieces: how an app plugs in

*Team Sam, S32, 2026-10-22. Builds INTERACTION.md Part 5 pieces 7 (top bar), 11 (History sheet) and 12 (agent
pieces). The rules themselves are INTERACTION.md 1.1, 1.9, 1.14 and 1.18.*

## The pieces

| Piece | File | Does |
|---|---|---|
| Rows | `rostrum_gui/history_rows.py` | Pure data. `rows(docs, me, show)`: every original change of the document and its partners, newest first. A person's or script's change is one "step"; an agent's changes in one session, one after another, fold into one "run" (its steps inside). Undo / redo steps are not rows; the row they took back says `undone`. `versions(doc)`, `who_name(who, me)` ("You", "Claude", "logo.py"). |
| Agent watch | `rostrum_gui/agent_watch.py` | `AgentWatch`, owned by the bridge as `bridge.agent`. Fed every change the bridge hears. `chip` (working while changes come less than 5 s apart, then done, gone after Keep or Undo all), `flash` (ids changed in the last second), `message`, `keep()`, `askHistory(session)` → `historyAsked(session)`. Never moves the selection, playhead or scroll. |
| Review slots | `rostrum_gui/bridge_review.py` | On every DocBridge: `historyRows(show)`, `undoRun(session)`, `redoRun(session)`, `undoStep(seq, doc)`, `saveVersion(name)`, `restoreVersion(name)`; properties `undoLabel`, `redoLabel`, `versions`, `agent` (declared in `bridge.py`). Each is one new change by the person; refusals go to the message line. |
| Top bar | `qml/RostrumKit/TopBar.qml` | One row, fixed order: `menu` · app name · `leading` · tab · message · "Saved · N changes" (click: History; its room held at its widest, so a new change never moves the command box) · `tools` · agent chip + `chips` · ↷ ↶ (Undo never moves) · command box · `actions` · ?. Room by priority, nothing cut: chips (`chipsNarrow`), the message whole, never dropped (the count steps back to "Saved" first; a longer message takes the command box's room, then two lines), command box, tab. |
| Agent chip | `qml/RostrumKit/AgentChip.qml` | "● Claude is working · 6 changes", then "Claude: 12 changes · Review · Keep · Undo all"; narrow: dot and count. |
| History sheet | `qml/RostrumKit/HistorySheet.qml` | The right-column sheet: Versions (Restore, Save a version), filter, rows; runs fold with Keep / Undo all / Bring back, steps have Undo this. `focusSession` shows one run. Esc closes. |
| Outline | `qml/RostrumKit/ChangeOutline.qml` | A 2 px outline in `Theme.agent` that fades over 1 s. |
| Shell | `qml/RostrumKit/AppShell.qml` | Ctrl+H, the sheet over the right column, opens on `bridge.agent.historyAsked`; new aliases `menu`, `chips`, `saveWord`. |
| Layout steps | `rostrum_gui/layout_run.kit_step` | `agent-run <n>`, `agent-say <words>`, `history open` (and `say <words>`). |

Test: `tests/test_history_rows.py` (an agent's run is one row; Undo all is one step and shows it taken back; ↶ still
takes back only the person's own step). From a worktree:
`PYTHONPATH="shared/gui-kit;shared/core" python -m pytest shared/gui-kit/tests/test_history_rows.py -q`.
Pictures: `C:\Users\Sam\.rostrum\waves\results\kit\s32\kit\` (the kit demo: `demo/main.py --size 1280x720 --step
"agent-run 6" --step "history open" --shot …`).

## Plugging in (any app)

Python: nothing to add for History, ↶ ↷ or the chip; every DocBridge has them. Two things to do:

```python
class MyBridge(DocBridge):
    def agent_demo_calls(self, n):          # only for the layout check's `agent-run n`: n harmless call lists
        return [[{"op": "layer.move", "target": [some_id], "args": {"x": 10 * i}}] for i in range(n)]
# Remove the app's own undoLabel / redoLabel (2D's undo_state.py): the kit's are the same rule (desk.undo / redo).
```

QML, on the kit AppShell (History, Ctrl+H and the chip come with it):

```qml
AppShell {
    bridge: backend
    saveWord: backend.saved ? "Saved" : "Not saved"     // the app's own save state, in a word
    menu: IconButton { glyph: "≡"; kind: "ghost"; onClicked: fileMenu.open() }   // optional
    chips: [LoudnessChip { }]                          // the app's own chips; read `narrow` from TopBar.chipsNarrow if they shrink
    actions: [Button { text: "Export" }]                // after the command box
    // remove the app's own UndoRedo from `actions`: the kit's ↶ ↷ sit before the command box
}
KeyMap { hub: backend.actions; skip: ["history", "undo", "redo"] }   // the shell makes Ctrl+H, Ctrl+Z, Ctrl+Shift+Z
```

Outlines over what an agent changed (the app knows where its items are on screen):

```qml
Repeater {
    model: backend.agent.flash                         // ids changed in the last second
    delegate: ChangeOutline { required property string modelData
                              readonly property rect r: view.rectOf(modelData)   // the app's own: item id -> rect
                              x: r.x; y: r.y; width: r.width; height: r.height }
}
```

An app not on AppShell puts `HistorySheet { bridge: backend; visible: open; onClosed: open = false }` in its right
column and opens it on `Connections { target: backend.agent; function onHistoryAsked(s) { sheet.focusSession = s; open = true } }`.

Words: the message line reads "Claude: Moved title" (`who_name`), "Undid: Move title", "Undid: Claude's 12 changes",
"Saved version "First look"". A refusal is the core's own sentence, in red.

## The core under it (shared/core, S32)

| Piece | File | Does |
|---|---|---|
| One live file | `rostrum_core/live.py` | `live.keep(doc)`: the window and an agent's server each hold a copy of the document; every change now locks the file, takes in the other program's new steps, makes the change and saves, so nobody's steps are wiped. `doc.live.catch_up()` takes in new steps between changes (as ordinary change events). A person's drag that ends after an agent's step is put on top of it. |
| The door | `rostrum_core/document.py` | Every change-making method (`apply`, `undo`, `redo`, `undo_session`, `redo_session`, `undo_changes`, `restore_version`, `mark_version`, `run_script`, `commit`) runs through `doc.live`'s door when there is one. `redo_session` is new (History's Bring back). `locked_by(id)` names who locked an item. |
| Locks | `rostrum_core/locks.py` (called by `run.plan` after each operation) | The one lock check for every app: any edit an operation makes to a locked item or to anything inside it is refused (a locked track holds its notes and clips; a clip moved onto it, a section op over every track are caught too), for people and agents alike. Setting `locked` on the item itself always passes (lock / unlock). The words: `"Background" (bg) is locked by Sam. Unlock it first, then try again.` / `"lead.n2000" (lead.n2000) is inside "lead" (lead), which is locked by Sam. …` |
| Refused undo | `rostrum_core/history.py` | Refused only when another change on the same things stands otherwise than when the step was made (made or brought back since, or taken back since); undo N then redo N in order is never refused. The words: `"Move chorus" can't be taken back: Claude changed some of the same things since ("Add 12 notes")` with the hint `Take back "Add 12 notes" first, in History.` (a redo says "brought back"; a step taken back since says "Bring back … first"). |
| Open previews | `rostrum_core/document.py`, `gesture.py` | `doc.kept` is the document as its history leaves it; every save writes it, so a drag or live-preview box (Repeat, Stagger, an amounts popover) open during a save is never saved as if kept. `doc.drop_gesture()` cancels an open one as Esc does; `LiveLink.close()` calls it before the window's last save. |
| Who in words | `rostrum_core/who.py` | `Who.words()`: "Sam", "Claude", "logo.py", "Outside Rostrum". The kit's `who_name` adds "You". |
| What the person sees | `rostrum_core/screen_state.py`, kit `rostrum_gui/live_link.py` | `LiveLink(bridge, app, state_fn)` (every 0.3 s: catch up, and write the app's `state_fn(bridge)` when it changes); `link.close()` removes it. |
| Agent tools | `rostrum_core/mcp/shared_screen.py` | Every server: `inspect_screen` (selection with ids, kind, name, time; playhead; range; scene or song; focus; view; what the person is dragging) and `edit_undo {group?}` (takes back only the calling agent's own steps). The server catches up every open document before each tool call. |

Rules for an app:
- **Open a live document once with `live.keep(doc)`**, in the window when it edits a project file directly and in the
  MCP server. Never `doc.subscribe(... doc.save())` again: a second save path outside the lock is what wiped work.
  `doc.save()` on a live document only goes through the door (it is saved already), so a stray Ctrl+S is harmless.
  Change a document only through `doc.apply`, a gesture or the history methods: they all go through the door.
- **Shared markers** are changed through `rostrum_core.markers.edit` / `open_to_change` (live too), never
  open → apply → save.
- **Never cache `doc.history`**: a catch-up that had to read the whole file makes a new History object.
- **Lock is data**: an item with `"locked": true`, set by `<kind>.lock` / `<kind>.unlock` operations. Nothing else to do.

Proof: `shared/gui-kit/demo/s32_agent_proof.py` (both apps, scratch projects; output in
`C:\Users\Sam\.rostrum\waves\results\kit\s32\proof.txt`). Test: `shared/core/tests/test_live.py`.

## Notes for Team Hem (Rostrum2D)

2D runs on all of this on `team/sam` (commits c096c36, 20fcc4b). When you merge main into H29, keep these, and build on
them instead of beside them:
- **Saving:** a live window (`--doc`, the launchers) calls `live.keep(doc)` and makes a `LiveLink(self, "2d",
  screen_seen.state)` in `Bridge2D.__init__`, closed in `close()`. The old `autosave` save in `_on_doc` is gone, and so
  is the `subscribe(... save)` in `python/rostrum2d/mcp/project_tool.py`. Never add a save after a change again. Open
  recent / Save / Save as windows (not live) still keep their unsaved dot; folding them into "always saved" is piece 13.
- **Undo / redo:** 2D's `UndoRedo.qml` and `undo_state.py`'s labels are gone; the kit's ↶ ↷ in the top bar follow the
  same one-history rule (document + markers). `undo_state.py` keeps only `_marker_saved`. `historyCount` comes from
  the kit. `Main.qml`: `saveWord: backend.isLive ? "Saved" : ""`.
- **Outlines:** `screen2d/agent_view.py` (`rectOf(id)`: a layer's canvas box, an effect / mask / key's layer;
  `agent_demo_calls(n)`). `Stage.qml` has a `Repeater` over `backend.agent.flash` inside `marks` (turned like
  `Handles`); `LayerRows.qml` outlines the row. When H29 adds zoom / pan, the outline must sit inside the same
  transformed item as the handles so it follows the view.
- **What the person sees:** `screen2d/screen_seen.py` (`state(bridge)`). Two gaps for Hem: **focus** reports
  "canvas" always (set `bridge._focus_area` to "canvas" / "layers" / "timeline" from `Main.qml` when the focused area
  changes, piece 20), and **view** has no zoom / scroll until H29's zoom / pan: add `"zoom"` and the visible rect then.
  `dragging` is the selection while `_drag` is on.
- **Lock:** `layer.lock` already refuses agents and people, now with who locked it, and covers everything inside
  the layer (its keys, effects, masks, children of a group).
- **Layout states:** `history-agent-run`, `agent-chip-long` in `layout_states.py`.

## RostrumSound (merged with P27 in S33)

Done on the merged tree: `SoundBridge` keeps the song live (`live.keep`, `LiveLink`), no save in `_on_doc`; the MCP
server `live.keep`s too. Lock: P27's `track.lock` / `track.unlock`, the header padlock and Ctrl+Shift+L, refused by
the core's one check (`rostrum_core/locks.py`; Sound's own `doc/locks.py` is gone). Outlines on the track header and
the painted lane (`LaneBlocks.qml`: an outline item only over the blocks `backend.agent.flash` names). `screen_seen.py`
reports the dock, the Library, the ruler's time range and the area last clicked (arrangement / editor).
Still open for Priyam: the agent outline in the Editor's piano roll and the Mixer strips (the same `Repeater` on
`backend.agent.flash` with a `ChangeOutline`).
