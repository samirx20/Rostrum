# Settings panel extras and NameLabel (S35 piece B3; INTERACTION.md 1.3, 1.4, 1.5, 1.10, Part 5 rows 8 and 18)

Kit pieces: `qml/RostrumKit/Inspector.qml`, `InspectorRow.qml`, `NumberField.qml`, `Slider.qml`, `NameLabel.qml`;
`rostrum_gui/many.py`, `rows.py`, `bridge_select.py`. Every GUI action here is an operation or a selection change first.

## What it does
- **Narrowing lines.** Several items of different kinds selected: under the title a "Show only" list, one line per kind
  ("3 layers ›"). A click calls `bridge.narrowTo(kind)` → `selectMany` of that kind (a selection change, never an undo
  step). Data: `bridge.narrowLines()` (`many.by_kind`). The kind's words come from the app's `kind_label` hook, plural by "s".
- **Last changed by.** Bottom line of the panel: "Last changed by Claude · 2 min ago" (hover: what they did). Data:
  `bridge.lastChanged()` → `many.last_change` (newest done original change whose edits touch a selected item) and
  `history_rows.who_name`. A click opens History through `bridge.agent.askHistory(session)` (the agent's run when it was
  one, else everything). Absent when the selection has no change yet. Ages every 30 s.
- **◇ key mark** is faint at all times (`Theme.fg4`), `fg3` while the row is hovered, `fg2` on the mark itself (already so
  in `InspectorRow`; unchanged).
- **Reset by double-click.** `NumberField.defaultValue` and `Slider.defaultValue` (null = no default = nothing happens).
  The row's `default` role (`rows.ROLES`) feeds the inspector's number fields. Double-click writes `edited(default)` — one
  `setValue`, one undo step. A Slider's first click of the double-click already jumped it; that change and the reset are
  quick repeats of one field, which the core merges (nudge).
- **Wheel** changes a number or slider only while it has keyboard focus; otherwise the panel scrolls.
  A notch = one step (Shift ×10, Alt ÷10).
- **Scrub modifiers.** NumberField: Alt = fine (a tenth of a step), Shift = coarse (×10); the speed counts from where the
  key went down (no jump). Slider: Alt = the drag moves at a tenth of the speed from where it was (no jump on press),
  Shift = lands on every 10th step. Left / Right keys the same. A fine value shows one more digit.
- **NameLabel** = a Text that elides with "…" and shows the whole name in a `HoverTip` when it is cut. `tip` (other words)
  and `help` (a sentence) optional. The layout checker accepts its elision. Used now in `ItemList` and the Inspector title.

## Adoption notes: swap `Text { … elide: … }` for `NameLabel { … }` (drop `elide`, `font.family`, `color` if default)
**Team Hem (apps/2d/screen/qml/)** names: `LayerName.qml:99` (the layer's own name; keep its rename editor),
`PaintOn.qml:54` (layer names), `SoundRow.qml:22` (the sound's name), `CurveEditor.qml:52`, `ImportPanel.qml:65`
(file name: `elide: Text.ElideMiddle`, keep it), `ExportSettings.qml:16`.
**Team Priyam (apps/sound/screen/qml/)** names: `TrackHeader.qml:41`, `GroupHeader.qml:45`, `MixStrip.qml:27`,
`MixRowHeader.qml:20`, `MixSends.qml:21`, `Library.qml:86` and `LibraryPanel.qml:66` (sound names), `PluginList.qml:18`,
`SectionBand.qml:42`, `SongSettings.qml:12`, `VoiceLines.qml:51`, `PictureCorner.qml:26` (middle elide).
Not names (leave): wrapped help, status or sentences (`ExportSettings.qml:46`, `VoiceLines.qml:76`).
A name inside a small clipped box (a strip or band) still needs the tip to be reachable; check it with the layout check.
