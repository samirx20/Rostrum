# Export, Problems and the job chip: how an app plugs in

*Team Sam, S34, 2026-10-22. Builds INTERACTION.md Part 5 pieces 14 (Export sheet frame) and 21 (Problems and job
chips). The rules themselves are INTERACTION.md 1.1 (sheets take the settings panel's place), 1.14 (chips), 1.15
(errors and Problems) and 1.19 item 8 (Export).*

## The pieces

| Piece | File | Does |
|---|---|---|
| Sheet model | `rostrum_gui/export_sheet.py` | `ExportSheet(bridge)`, the flow every app shares: `open` / `setOpen`, What for (`choices`, `choice`, `setChoice`), `ranges` / `setRange` / `range_times()`, where (`folder` "" = the app's default, `setFolder` from Browse, `where` in words, `fileName`), `request()` (Export: asks first when the file is there: `asked(name, canReplace)` → `answer("replace" \| "both" \| "cancel")`; Keep both = "name 2.ext", `free_path`), the job off the GUI thread (`state` "" / running / done / failed / cancelled, `progress` 0..1 or −1, `note`, `cancel()`, `dismiss()`), done: the message line says "Exported Main.mp4", `doc.mark_version("Exported v003")`, `play()`, `showInFolder()`; `again()` (Ctrl+Shift+E). A failure is the bridge's red error; the old file stays. |
| Sheet | `qml/RostrumKit/ExportSheet.qml` | The right-column panel, titled Export: WHAT FOR (each with its file type, one way for all: MP4, PNG …; the chosen row highlighted, never repeated as the title) · the app's `settings` slot · RANGE (only with more than "everything") · WHERE (file name, folder, Browse…, Renders folder) · Export (Cancel and a progress line while it runs) · "Exported · Play · Show in folder" or the red sentence · the one blocking question "… is already there": Cancel / Keep both / Replace (a folder of frames: no Replace). Export follows the rows and stays in sight once they scroll. Esc or × closes. |
| Shell | `qml/RostrumKit/AppShell.qml` | `exporter`, `exportSettings`, `problems`. One sheet at a time in the right column (History or Export); Ctrl+E opens / closes, Ctrl+Shift+E exports again without opening. |
| Top bar | `qml/RostrumKit/TopBar.qml` | `problems`, `job`; the chips row is agent · Problems · job · the app's own; "Play · Show in folder" after the message while it still says "Exported …". Narrow: every chip is a dot and a count. |
| Job chip | `qml/RostrumKit/JobChip.qml` | "● Exporting Main.mp4 · 42 %" while it runs; red "Export failed" until read. Click: what it is doing or why it failed, Open Export, Cancel / Dismiss. Absent otherwise. |
| Problems chip | `qml/RostrumKit/ProblemsChip.qml` | "● 2 problems" (red dot when one is damage), only while there are any. Click: the list in words, each with what to do; click one: `source.jump(row)`. |
| Problems list | `rostrum_gui/problems.py` | `ProblemsList(jump_to)`: `rows`, `show_rows(rows)`, `pin(rows)` (scripted), `jump(row)`. For an app with no list of its own. |
| Steps | `rostrum_gui/export_steps.py` (from `layout_run.kit_step`) | `exportsheet open [what]\|close`, `exportwhere <folder>` (_ for spaces; `default`), `exportnow [replace\|both\|cancel]` (waits, fails loudly), `problems open\|close`, `problems-demo` (long texts), `job-show <percent>`, `job-failed <words>`. They find `bridge.exporter` and `bridge.problems`. |

Test: `tests/test_export_sheet.py` (a file there is never replaced without asking: Cancel writes nothing, Keep both
writes "Main 2.txt" and leaves the old one, Replace only once asked; the export marks "Exported v001"). From a worktree:
`PYTHONPATH="shared/gui-kit;shared/core" python -m pytest shared/gui-kit/tests/test_export_sheet.py -q`.
Proof: `shared/gui-kit/demo/s34_export_proof.py` (both apps from the sheet into a scratch folder, read back; a heavy
job: run it through the lock). Output: `C:\Users\Sam\.rostrum\waves\results\kit\s34\export\`.

## Plugging in (any app)

Python: subclass `ExportSheet` and answer its questions; put it and the Problems source on the bridge.

```python
from PySide6.QtCore import Property, Signal, Slot
from rostrum_gui.export_sheet import ExportSheet

class MyExport(ExportSheet):
    own = Signal()                       # your own properties notify on this, never on ExportSheet.changed:
                                         # PySide6 crashes when a subclass property notifies on its parent's signal
    def __init__(self, bridge):
        super().__init__(bridge)
        self.changed.connect(self.own)
        self._choice = "mp4"                                   # the first choice
    def choices_list(self):      return [{"value": "mp4", "label": "Video to share", "type": ".mp4"}]
    def ranges_list(self):       return [{"value": "all", "label": "Everything · 6 s", "start": 0, "end": 6}]   # [] = no range row
    def default_folder(self):    return r"…\renders\main (a new version folder)"
    def file_name(self):         return "Main.mp4"
    def replaceable(self):       return True                   # False: a folder of frames (Keep both / Cancel only)
    def chose(self):             ...                           # reset the new choice's own settings
    def begin(self, out, overwrite):                           # GUI thread: snapshot; raise with a sentence to refuse
        return {"scene": snapshot(self.bridge.doc), "out": out, "overwrite": overwrite}
    def work(self, plan, progress):                            # worker thread: write under a temporary name, then rename
        ...; progress(0.5); ...
        return {"files": [path], "file": path, "version": "v003", "summary": "150 frames at 25 fps · 1920×1080"}
    def stop(self):              self._engine.kill()           # optional: without it there is no Cancel

    @Property(str, notify=own)
    def quality(self): ...                                     # the app's own settings for its `settings` rows

bridge.exporter = MyExport(bridge)        # a Qt property the QML reads (and the kit's steps find it here)
bridge.problems = ProblemsList(jump_to=lambda row: bridge.select(row["item"]))   # or the app's own {rows, jump(row)}
```

QML, on the kit AppShell (the sheet, Ctrl+E / Ctrl+Shift+E, the job chip and "Play · Show in folder" come with it):

```qml
AppShell {
    exporter: backend.exporter                    // null hides it (Sound: until the song makes a sound)
    exportSettings: MyExportSettings { }          // a Column of kit rows: only the chosen item's settings
    problems: backend.problems                    // {rows, jump(row)}: the Problems chip
    actions: [Button { text: "Export"; kind: "primary"; down: backend.exporter.open
                       onClicked: backend.exporter.setOpen(!backend.exporter.open) }]
}
```

Remove the app's own Ctrl+E / Ctrl+Shift+E shortcuts and put `"export", "export_again"` in its KeyMap `skip` (the kit's
KeyMap already leaves them to the shell). An app not on AppShell puts `ExportSheet { model: …; settings: … }` in its
right column and `JobChip` / `ProblemsChip` in its top bar's `chips`.

A problem row: `{label: "Missing file", message: "… isn't there any more.", fix: "Use Find… …", item: "<id>", time: 2.4,
danger: true}`; `danger` is red (damage, clipping), else amber. Words: one sentence of what is wrong naming the thing,
one of what to do (INTERACTION.md 1.15).

Layout states (every app): `export-sheet` (a long file name and folder), `problems-chip` (`problems-demo`, then
`problems open`), `job-chip` (`job-show 42`); 2D also `job-failed`.

## Notes for Team Hem (Rostrum2D)

On `team/sam`: `qml/ExportPanel.qml`, `qml/ProblemsPanel.qml` and `screen2d/export_job.py` are gone.
- `screen2d/exporter.py` is now `Exporter(ExportSheet)`: the same `exporting.run` / `snapshot` / `settings` (the files and
  manifests agents get from `render_export`). What for in words is `export_rows.WHAT_FOR`; the From / To seconds became the
  sheet's range (everything, or marker to marker from the project's markers). 2D's own rows (composition, transparency, bit
  depth, quality; the readback and Lottie's "couldn't carry" once done) are `qml/ExportSettings.qml`.
- `Main.qml`: `exporter`, `exportSettings`, `problems` on the shell; Export is a primary button; `setExportOpen(open)` stays
  for the steps; the Problems button and both panels are gone.
- `screen2d/problems.py`: `show(item)` became `jump(row)` (selects the item; goes to `row.time` when there is one) and
  `show_rows(rows)`; rows carry `danger` for "Can't be drawn". If `inspect_diagnose` learns a moment for a problem (a
  missing font at 2.4 s), add `time` to its row and the jump goes there.
- Steps: `export <format> [alpha=…] [depth=…] [quality=…] [range=<a→b>]` (start= / end= are gone with From / To),
  `exportto <folder> [answer]` (a folder now, not a file), `exportcancel`, `exportpanel` (= the sheet), `exportshow`.

## Notes for Team Priyam (RostrumSound)

- `screensound/export.py` is now `RenderExport(ExportSheet)`; the app's frame (`qml/ExportSheet.qml`) is gone and its rows
  are `qml/ExportSettings.qml` (pass / miss, File, Quality, Stems, Cut the silence). What for = the delivery targets
  (`delivery.TARGETS`, each with the file type); choosing one is still the one `master.set` (`mixer.loudness.choose`), and the
  list follows the master when it changes (undo, an agent). Browse copies the mix into that folder under the song's name
  (Replace / Keep both asked there); the version folder keeps the mix and stems. `setDialogOpen` / `dialogOpen` are now the
  kit's `setOpen` / `open` (`setDialogOpen` still works for old scripts).
- `Main.qml`: `exporter: shell.hasSound ? mixer.export : null`, `exportSettings`, `problems: mixer.problems`; the right
  column no longer hides itself for Export (the shell does); Ctrl+E / Ctrl+Shift+E come from the shell. The Loudness chip
  is unchanged.
- Problems (`screensound/problems.py`, `mixer.problems`, `bridge.problems`): today only clipping (the newest render's
  loudest peak over 0 dBTP, red). Missing files, missing models and "Render failed" should be added as rows there.
- Still open: **"+ Another version"** (several deliveries in one Export, job H): the render takes the master's own target,
  so a second version with another target needs a render-time target override in `handoff.render`. **Cancel**: the
  render engine can't be stopped from the screen yet (no `stop()`), so the job chip offers no Cancel. **Range**: the render
  has no time range, so the sheet shows no range row.
