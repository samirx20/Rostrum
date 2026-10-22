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

# S36 panel pieces: Effects row, right-click Reset, snap colour, Popover

Kit files: `qml/RostrumKit/EffectsRow.qml`, `Inspector.qml`, `InspectorRow.qml`, `Popover.qml`, `Theme.qml`, `SnapLine.qml`;
`rostrum_gui/effects.py`. Look harness and layout check: `python shared/gui-kit/demo/panel_preview.py` (7 states × 4 sizes,
pictures in `C:\Users\Sam\.rostrum\waves\results\kit\s36\panel\`; set `QT_QPA_FONTDIR=C:/Windows/Fonts`). Demo document with
effects: `demo/effects_demo.py`; the guards: `tests/test_effects.py`.

## Effects (n) +  (INTERACTION 1.4, the rule of individuality)
A layer's effects are child items with their own settings. In the panel they sit under the layer's own rows:
"Effects (2)" with a **+**, then each effect as a folded group (chevron, name, **×**, its settings under it). The + lists
only the effects that apply to this layer now (never greyed). One item selected only; nothing to add and nothing added:
no row. Every click is an operation: + → the add operation, × → the remove operation, a setting → the effect's own field
operation (`bridge.edit_call`), each one change (undo, History, who changed what). A new effect opens at once.

The app gives **data** (`EffectsSpec`) and two operation names; the kit has no effect code:
```python
from rostrum_gui import effects
effects.attach(bridge, effects.EffectsSpec(
    types=[effects.EffectType("blur", "Blur"),
           effects.EffectType("gradient", "Gradient", valid=lambda it: it["type"] in FILLS)],
    key="effects", add_op="effect.add", remove_op="effect.remove", kinds=None))   # kinds: layer types that take effects
```
Per type `valid_when` (a registry condition on the layer's values and `doc.kind.facts`) or `valid(item) -> bool`.
Add calls `{"op": add_op, "target": [layer], "args": {"type": type}}`; remove calls `{"op": remove_op, "target": [effect]}`.
Each effect's settings are its kind's field operation (`registry.field_op(effect type)`), laid out as for any item.
In QML the app turns it on: `Inspector { effects: true … }` (the Inspector reads the part with `bridge.invoke("effects", [])`;
a dynamic property from `bridge.attach` cannot be read from QML, so `attach` is not used).

### Adoption: Team Hem (2D) moves the context bar's Effects ▾ into the panel
Today: `apps/2d/screen/screen2d/actions.py` lines 103–106 make `effect_<type>` actions with `bar="Effects"` (and
`effect_grain`); `_EFFECT_WHEN` is at line 50.
1. In `bridge2d.py`, once the bridge exists (for example at the end of `Bridge2D.__init__`):
   ```python
   from rostrum_gui import effects
   FILLS = {"shape", "text", "path"}
   effects.attach(self, effects.EffectsSpec(
       types=[effects.EffectType(e, F.LABELS[e],
                                 valid=(lambda it: it["type"] in FILLS) if e == "gradient"
                                 else (lambda it: it["type"] != "camera")) for e in F.EFFECTS],
       kinds=F.LAYERS, label=lambda eff: F.LABELS[eff["type"]]))
   ```
   2D's `FACT("fills")` and `has_camera` are facts of the *selection* (`action_rules.py`); the row judges one layer, so the same
   rule is written on the layer's type, as above. A camera takes none, so its + list is empty and the row is absent.
2. In `Main.qml` line 140: `Inspector { id: settingsMove; … effects: true … }` (the Brush Inspector `settingsDraw` stays).
3. In `actions.py` remove the `effect_<type>` actions (lines 103–104) from the context bar and menus. Keep `effect_grain`
   ("Grain (whole picture)": the composition's, not a layer's) where it is, or give it a home on Scene settings.
   In `layout_states.py` replace the `effects-menu` state (line 137) with one that opens the + list
   (`select card`, then click the item whose `objectName` is "addEffect").
4. An effect already on a layer is a settings group now; it is removed with its ×.
5. The effects' rows carry no ◇ key mark yet (`keyMarks` is off in them). If 2D needs keys on effect settings, report it:
   a small follow-up (`EffectGroup` would pass `anim_state` / `toggleAnimate` through).

## Right-click › Reset (INTERACTION 1.4)
Every param row of the panel: right-click puts the setting back to its default (`model.default`, from the param's
`default`) through the same `setValue`: one undo step (several selected: one change on all). A row at its default, with
no default, or driven by an expression has no menu (absent, not greyed); a Mixed row offers it. Nothing for apps to do
except give params a `default` (2D: `Param(default=…)` in `fields.py`; the double-click on a number already used it).
Inside Effects groups the same rows reset the same way. Rows have an `objectName` "row:<param>" for scripted steps.

## The snap colour
`Theme.snap` ("#ff2fd0") and `Theme.snapText` (the name on the chip); `SnapLine.qml` reads them. `DragLabel.qml` had no
literal colour. **Finding:** `Stage.qml` has no colour constant: it uses 2D's own `apps/2d/screen/qml/SnapLine.qml` (a
plain Rectangle with `color: "#ff2fd0"`, which shadows the kit's `SnapLine`). Sound has two more:
`PianoRoll.qml:94` (`"#ff4fd8"`) and `Timeline.qml:141` (`snapColour: "#ff4fd8"`, a slightly different magenta).
- **Team Hem, one line:** in `apps/2d/screen/qml/SnapLine.qml` add `import RostrumKit` and change the colour to
  `color: Theme.snap`. (Later, optional: use the kit's `SnapLine` for the canvas lines too; it adds the name chip, and its
  geometry is `at / vertical / from / to`.)
- **Team Priyam:** `PianoRoll.qml:94` → `color: Theme.snap`; `Timeline.qml:141` delete `snapColour` and use `Theme.snap`.

## Popover
`Popover { title: "…"; focusItem: someField; <content> }`, then `pop.openAt(button)` (under it, left edges together, above it
when there is no room, always inside the window) or `pop.openAtPoint(x, y)` (window px). Closes on Esc (`escaped()` first,
so an app can take the change back; typing is dropped with it) and on a click outside; `modal: true` makes the closing
click do nothing else. `accepted()` is Enter pressed where no field used it (the app decides: `pop.close()`). Focus goes into
`focusItem` (else the popover) and back to whatever had it. It is a `QQC.Popup` (`opened`, `open()`, `close()`, `onClosed`
work as usual; the app's `onClosed` runs beside the popover's own). The optional `title` shortens with … and shows whole on hover.
Esc does not close it while a list opened from inside (a ChoiceField's) has the keys; that list takes the Esc.

### Adoption: Team Hem, 2D `StaggerPopover.qml` (opened by `backend.stagger`; Esc takes back, a click away keeps)
Replace `QQC.Popup { … }` with the kit's and keep the content rows:
```qml
Popover {
    id: pop
    readonly property var st: backend.stagger
    property bool cancelled: false
    title: "Stagger " + pop.st.what
    modal: true                         // as before: the closing click does nothing else
    focusItem: byField
    onEscaped: cancelled = true         // was the Escape Shortcut
    onAccepted: close()                 // was the Return / Enter Shortcut
    onOpened: cancelled = false
    onClosed: cancelled ? st.cancel() : st.end()
    Connections { target: pop.st
        function onOpened() { pop.openAtPoint((shell.width - pop.width) / 2, 104) }    // was x / y in Main.qml
        function onChanged() { if (!pop.st.open && pop.opened) pop.close() } }
    // the two Rows ("Each starts [NumberField id: byField] after the one before", "Order" [ChoiceField]) unchanged
}
```
Delete: `padding`, `closePolicy`, `background`, the title `Text`, both `Shortcut`s, and the `x:` / `y:` on the instance in
`Main.qml:121`. `pop.width` is the real width after the first open (the popover re-places itself when its size settles).

### Adoption: Team Priyam, Sound `AskPopover.qml` ("Land a bar": one number; Enter or the button answers, Esc closes)
Today opened by `backend.askWanted` through `Timeline.qml:185` (`AskPopover { id: ask; parent: cbar; x: …; y: cbar.height + 2 }`):
```qml
Popover {
    id: ask
    property string key; property string label; property real value
    focusItem: field
    onOpened: { field.text = String(value); field.selectAll() }       // Popover has put the keys in `field`
    function go() { const v = Number(field.text); if (!isNaN(v) && field.text !== "") { close(); backend.landBar(key, v) } }
    // the Row (label, the TextInput box with onAccepted: ask.go(), the Land button) unchanged
}
```
Delete: `padding`, `closePolicy`, `background`, and on the instance in `Timeline.qml` the `parent: cbar` and `x` / `y`. Where it opens:
`ask.openAt(<the item it belongs under>)` or `ask.openAtPoint(x, y)` instead of the fixed `x` / `y` (the popover lives on the
window's overlay, so it can never leave the window). Esc needs no code (it closes; `escaped()` if the app wants it).
