# Files and the start screen: how an app plugs in

*Team Sam, S34, 2026-10-22. Builds INTERACTION.md Part 5 piece 13 (one automatic-save model, the ≡ menu, the start
screen). The rules themselves are INTERACTION.md 1.19 (and 1.14, 1.16).*

**One model:** every project window is live. A document with a folder is opened once with `live.keep(doc)` and the
window's `LiveLink` (HISTORY.md › One live file), however it was opened (New, Open, Open recent, the sample, the start
screen, `--doc`, `--open`, a double-clicked file). Each change is on disk at once, through the same door the MCP server
uses, so an agent's change shows in the window on the next LiveLink tick. There is no Save, no unsaved dot, no
"Save changes?" and no recovery copy. A New project left untouched is removed when it is left.

## The pieces

| Piece | File | Does |
|---|---|---|
| Model | `rostrum_gui/docfiles.py` | No Qt, no app knowledge. `AppFiles` (the app's adapter, below), `projects_root(kind)` (a scripted run's scratch folder, never the person's), `new_folder(root, base)` ("Untitled", "Untitled 2" …), `clean(name)`, `recent` / `remember`, `duplicate(folder, dest)` (whole folder; refuses a full or inside folder), `version_name()` (the time), `open_whole(kind, folder, item)` (a damaged or newer file refused in words ending "Nothing was changed."), `said(e)`, `thumb(folder, item)` (`.rostrum/thumbs/<item>.png`). |
| Open recent | `shared/core/rostrum_core/recent.py` | The one list: `<userhome>/settings/<app>-recent.json`, rows {folder, item, name}. The window, the start screen and both MCP servers' `lastproject.py` read it. Scripted runs use their scratch home (`userhome.py`). |
| Files object | `rostrum_gui/project_files.py` (+ `file_menu.py`) | `ProjectFiles(kind, host)`, QML `files`. `launch(path, new)`, `put(doc)`, slots `newProject`, `openPath`, `openRecent`, `openSample`, `openCopy`, `duplicate`, `showFolder`, `saveVersion`, `setStart`, `pick(value)`, `menu()`; Ctrl+K `commands()`. Properties `name`, `hasProject`, `recent`, `startShown`, `projectsFolder`, `projectsUrl`, `hasSample`, `noun`, `keys`, `guides`, `copyName`. Every project it puts on screen is made live first. |
| ≡ menu | `qml/RostrumKit/FilesMenu.qml` | The ≡ button: New, Open…, Open recent ▸, Open sample, Duplicate…, Save a version, Show folder, Start screen… (after a divider), then the app's `extra` rows. The open / duplicate dialogs, "Copy made · Open the copy", and the four file keys from the key map (`new`, `open`, `duplicate_file`, `save_version`). |
| Start screen | `qml/RostrumKit/StartScreen.qml` | Fills the window, one three-column grid: the ways in as tiles (New, the accent; Open…; Open the sample), Continue <last> (at launch) or Back (Esc, a project open behind it) on the title's line, "Copy made · Open the copy" under the title after a Duplicate made there, recent projects (a picture when there is one, else a plain card with name and date; long names "…" with the whole name on hover), up to three guide cards (`guideAsked(url)`). |
| Versions | `HistorySheet.nameVersion(name)`, `AppShell.nameVersion(name)` | Ctrl+S opens History with the name field filled with the time and selected. |
| Core | `rostrum_core/live.py` | `live.keep(doc)` on a document already live returns its Live (the model and the bridge both ask). |
| Core | `rostrum_core/samples.py` | A scripted run's sample copies go to its scratch home, never the person's Documents. |

Test: `tests/test_docfiles.py` (a project opened through Open is live: an agent's change through its own live copy
shows after `catch_up`; the person's change is on disk with nothing saved). From a worktree:
`PYTHONPATH="shared/gui-kit;shared/core" python -m pytest shared/gui-kit/tests/test_docfiles.py -q`.
Proof: `demo/s34_files_proof.py <out>`; output and pictures in `C:\Users\Sam\.rostrum\waves\results\kit\s34\files\`.

## Plugging in (any app)

Python: an adapter of a few functions, and a host with `show(doc)` and `bridge`.

```python
from rostrum_gui.docfiles import AppFiles
from rostrum_gui.project_files import ProjectFiles

MY_FILES = AppFiles(
    app="2d", title="Rostrum2D", noun="project", ext=KIND.ext, untitled="Untitled", folder=settings.projects_dir,
    blank=blank,                 # (folder or None) -> a new blank Document, saved in folder (None: in memory)
    open=lambda f, i: Document.open(f, i, KIND),   # read whole; open_whole wraps it in plain refusals
    resolve=resolve,             # a picked file or folder -> (project folder, item)
    sample="lull",               # rostrum_core.samples name, "" for none
    guides=[(GUIDES / "first-animation.md", "Making your first animation"), ...],   # the start screen shows 3
    after_copy=repoint,          # optional: (copy Document, old folder, new folder) after Duplicate
    snapshot=lambda bridge: bridge.frames.provider.requestImage("", None, None))    # optional: the start screen's picture

class Session:                               # the host: one window per open document
    def __init__(self):
        self.bridge = None
        self.files = ProjectFiles(MY_FILES, self)
    def show(self, doc):                     # a fresh bridge + window for doc, then close the old ones
        bridge = MyBridge(doc)               # in the bridge: if doc.folder and doc.item_id: live.keep(doc); LiveLink(...)
        ...start(QML, {"backend": bridge, "files": self.files, ...})
    def close(self):
        self.files.close()                   # keeps the picture; removes an untouched New project

files.launch(args.path, args.new)            # a person's start: that project, else the last one, else the start screen
files.put(doc)                               # a window the app opened itself (--doc, --sample, --script)
```

QML, on the kit AppShell:

```qml
AppShell {
    documentName: files.hasProject ? files.name : "Untitled"
    saveWord: backend.isLive ? "Saved" : ""
    menu: FilesMenu {
        id: fileMenu
        extra: [{ value: "settings", label: "Preferences…", keys: "Ctrl+,", group: "app" }]   // the app's own rows
        onPicked: (v) => { if (v === "settings") settingsPanel.open() }
    }
    StartScreen { id: startScreen; anchors.fill: parent; z: 100; onGuideAsked: (url) => shell.openGuide(url) }
    KeyMap { hub: backend.actions; enabled: !shell.typing && !startScreen.visible }
}
```

Do not write Shortcuts for Ctrl+N / O / S / Shift+S: FilesMenu makes them from the key map. Steps for scripted runs:
`new [name]`, `openproject <path>`, `startscreen open|close`, `version [name]`, a duplicate step (2D:
`duplicateproject <name>`, since `duplicate` is its layer step; Sound: `duplicate <name>`). Layout state:
`start-screen` (two long-named copies, then the start screen).

## Notes for Team Hem (Rostrum2D)

What changed in 2D on `team/sam`:
- **Gone:** `screen2d/files.py`, `projects.py`, `recent.py`, `qml/FileFlow.qml`, `qml/FileMenu.qml`,
  `tests/test_recovery.py`; the steps `save`, `saveas`, `autosave`, `restore`, `discard`, `askclose`; `Bridge2D`'s
  `autosave` argument; `Main.qml`'s `leaving`, `onClosing` and `askClose`. `qml/AskDialog.qml` is now used by
  nothing (FileFlow and the old ExportPanel were its users): delete it unless the Export work needs it.
- **New:** `screen2d/files2d.py` (blank, resolve, repoint imported files in a copy, the canvas picture); `session.py`
  holds the kit's `ProjectFiles` as `files` and `show(doc)` only. `Bridge2D` is live for every document with a folder
  and item. `file_commands.py` hands `file:` commands to `files.pick`. `main.py`: `load_doc` only for `--doc`,
  `--script`, `--sample`; everything else is `files.launch(args.open)`.
- **Main.qml hooks:** `menu: FilesMenu { id: fileMenu }` (replaces `leading: FileMenu`), the `StartScreen` line,
  `KeyMap.enabled` also off while the start screen shows, Esc closes `fileMenu.closeMenu()`, `setFileMenuOpen`.
- **Keep:** never save after a change, never add an "unsaved" state, never write file Shortcuts in QML. A new
  start-time view state ("where it was left": scene, selection, playhead, zoom) belongs in the bridge's screen state,
  not in the document.
- The old Open recent list (2D's `settings.json` "recent") is not carried over: the list starts again in
  `settings/2d-recent.json`. `rostrum2d/lastproject.py` (the MCP server's last project) reads the new list.
- The guide `apps/2d/guides/files.md` is rewritten; its old picture `guides/pictures/file-menu.png` was deleted
  (shoot a new one of the ≡ menu, or delete it).

## Notes for Team Priyam (RostrumSound)

What changed in Sound on `team/sam`:
- **Gone:** `screensound/session.py` (`Songs`, the `songs` context property), `screensound/projects.py` (the untitled
  area, the open lock `sound-open.json`, crash recovery, Sound's own recent list code), `qml/FileMenu.qml` (with its
  refused-open and recovery prompts; a refusal now goes to the message line in words), `SoundBridge`'s `autosave`
  argument, and `Main.qml`'s Ctrl+N / O / S / Shift+S Shortcuts.
- **New:** `screensound/files_sound.py` (blank with the person's new-song defaults, resolve, song_item, title);
  `main.py`'s `Screen` holds the kit's `ProjectFiles` as `files`; `Screen.show(doc)` names the song itself and keeps the
  app from quitting while it swaps windows (it closed the only window first, so New ended a scripted run).
  `test_projects.py` keeps only the damaged-song refusal (now through the kit's `open_whole`).
- **Main.qml hooks:** `menu: FilesMenu { … extra: Preferences…, Quit }` (replaces `leading: FileMenu`), the
  `StartScreen` line, `KeyMap.enabled` off while it shows. `RecordControls.qml`: the level reads only a number (it
  printed "Unable to assign [undefined] to double" on every window).
- **Keep:** the recent list file is unchanged (`settings/sound-recent.json`), so a person's list carries over. Export
  MIDI and Move into a project don't exist yet; when they do, add them to `extra`.
- Steps: `new`, `openproject`, `duplicate`, `version`, `startscreen` (the old `file-new`, `file-open`,
  `file-duplicate` still work; `file-save-as` is gone).

## Reopen at the same place, Find…, Open the last version that works (S36)

Three more pieces of INTERACTION 1.19, in the kit; the app gives `AppFiles` a few optional hooks and gets them all.

| Piece | Where | The app gives (`AppFiles`) |
|---|---|---|
| **Reopen at the same place** | `rostrum_core/places.py` (data, in the person's home: `<userhome>/places/<app>.json`, never in the document; a scripted run's home is its scratch one), `rostrum_gui/place_keeper.py` (`files.places`) | `place(bridge) -> dict`, `restore_place(bridge, dict)` |
| **Find…** | `rostrum_gui/find_files.py` (no Qt), `file_repairs.py` (≡ row, `files.findMissing(folderUrl)`, `files.missingRows()`, `files.missing`) | `refs(doc) -> [(item id, field, path)]`, `ref_op(doc, item id) -> "layer.set"` |
| **Open the last version that works** | `rostrum_core/rescue.py` (`plan`, `rebuild`), `file_repairs.py` (`files.rescue`, `files.openRescued()`, `files.dismissRescue()`), StartScreen's banner, a ≡ row | `doc_kind=KIND` |

**Place.** A place is a plain dict the app fills: `scene`, `selection` (ids), `playhead`, `range`, the canvas view
(`CanvasView.place()` gives `{zoom, panX, panY, fitted}`; a fitted view fits again at the new window size), the time view
(`TimeView`'s start and span) … whatever it can put back. The kit saves it when the project is left, renamed (it follows the
new name) or the app closes, and a moment after the app calls `files.places.note()` (put it where the selection, playhead,
scene or view change; it is throttled, 0.6 s). It restores right after `host.show(doc)`. `places.keep_existing` drops what no
longer exists one item at a time (`scene` and `focus_item` are single ids; `selection` is a list): a deleted layer leaves the
rest of the place as it was. It is screen state: no change, no undo step, and an agent never moves it.

**Find…** The project opens with missing items marked "missing" (the app's own look). ≡ › **Find missing files…** is there only
while something is missing (rule of individuality): it asks for a folder and `find_files.relink` finds each missing file by its
name, else by its name ignoring capitals (several of one name: the one whose folders match the old path's the most; folders
starting "." are not searched), and returns every "set this field" call. `files.findMissing` applies them with ONE
`doc.apply` (one change, one undo step, "Find 3 missing files") and says what it found and what is still missing.
`files.missingRows()` gives the app's Problems list its rows (label "Missing file", message, fix, `find: True`): an app's
`jump_to(row)` for a row with `find` calls `files.pick("find")`.

**Open the last version that works.** `open_whole` still refuses a damaged or newer file in plain words. When the file's own
history can rebuild it, `files.rescue` is filled (what is wrong, "Its history can rebuild … up to step 12 of 14") and the start
screen opens with a banner: **Open the last version that works** and Not now (also a ≡ row). `rescue.rebuild` replays the history
up to the last step that applies cleanly (its edits apply, its recorded hash matches, the document check passes), keeps the
damaged document and history beside as `<name>.damaged-<time>` (never overwritten), saves the rebuilt one and says which step
it stopped at. A history that is gone or unreadable offers nothing (the refusal's words stand).

### Notes for Team Hem (Rostrum2D)

In `apps/2d/screen/screen2d/files2d.py` (I did not touch it), add to `FILES2D = AppFiles(...)`:

```python
doc_kind=KIND,                                              # Open the last version that works
place=lambda bridge: {...},                                 # scene id, selection ids, playhead, the canvas's CanvasView.place()
restore_place=lambda bridge, p: ...,                        # open the scene, select, move the playhead, view.restore_place(p["view"])
refs=lambda doc: [(it["id"], "src", it["src"]) for it in doc.items() if it.get("src")],      # imported files, as layers hold them
ref_op=lambda doc, item_id: f"{doc.item(item_id)['type']}.set",                              # the same call `repoint` makes
```

Then: call `bridge.files.places.note()` where the selection, playhead, scene or view change (one throttled call; the kit saves
it); feed `files.missingRows()` into 2D's `problems.py` rows and make `jump_to` call `files.pick("find")` for a row with `find`;
show an item whose file is missing as "missing" (its own look). Put `ViewControl { view: <the CanvasView> }` bottom-right of the stage
(replacing the hand-made `ViewControls.qml` once the lead has added the type to qmldir) and `markerSource: <MarkerWatch>` on the Ruler
for the marker menu (TIMELINE.md); handle `onMarkerShareToggled` (own ↔ shared).

### Notes for Team Priyam (RostrumSound)

Same hooks in `apps/sound/screen/screensound/files_sound.py`: `doc_kind=KIND`; `place` = the open song, selection, playhead, the
time range and `TimeView`'s start / span; `refs` = each clip's audio file (`[(clip id, "file", path), …]`), `ref_op` = the
clip operation that sets it. Call `files.places.note()` from the playhead and selection changes. Sound's own "missing" look for a
clip stays Sound's; the Problems list gets `files.missingRows()`.

## Left open

- Rename by clicking the project name (S35): `files.rename(name)` renames the folder beside itself and reopens it
  live; the top bar's name tab opens a field in place (AppShell wires it to the kit's `files`, no app code). An agent
  that had the old folder open is refused on its next step (its folder is gone); it opens the new one. Layout state
  `rename-name` (step `name edit`) in both apps. Report a problem (? menu): `rostrum_gui/report.py`.
- "Exactly where you left it", Find… and Open the last version that works are built in the kit (S36, above); the apps' hooks
  (`place`, `restore_place`, `refs`, `ref_op`, `doc_kind`) are written up for Hem and Priyam, not yet wired in their apps.
- The guides drawer opens under the start screen when no project is open; StartScreen moves aside by
  `shell.guidesWidth` if AppShell exposes it (it doesn't yet).
