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
| ≡ menu | `qml/RostrumKit/FilesMenu.qml` | The ≡ button: New, Open…, Open recent ▸, Open sample, Duplicate…, Save a version, Show folder, Start screen…, then the app's `extra` rows. The open / duplicate dialogs, "Copy made · Open the copy", and the four file keys from the key map (`new`, `open`, `duplicate_file`, `save_version`). |
| Start screen | `qml/RostrumKit/StartScreen.qml` | Fills the window: New (big), Continue <last> (at launch), Open…, Open the sample, recent projects (a picture when there is one, else a plain card with name and date; long names "…" with the whole name on hover), up to three guide cards (`guideAsked(url)`), Back (Esc) when a project is open behind it. |
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

## Left open

- Rename by clicking the project name (S35): `files.rename(name)` renames the folder beside itself and reopens it
  live; the top bar's name tab opens a field in place (AppShell wires it to the kit's `files`, no app code). An agent
  that had the old folder open is refused on its next step (its folder is gone); it opens the new one. Layout state
  `rename-name` (step `name edit`) in both apps. Report a problem (? menu): `rostrum_gui/report.py`.
- "Exactly where you left it" covers the project only; scene, selection, playhead and zoom are not restored yet.
- Missing files' **Find…** (1.19 item 6) and **Open the last version that works** on a damaged file (item 7) are not
  built; the refusal offers nothing but its words.
- The guides drawer opens under the start screen when no project is open; StartScreen moves aside by
  `shell.guidesWidth` if AppShell exposes it (it doesn't yet).
