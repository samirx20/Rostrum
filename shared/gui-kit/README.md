# shared/gui-kit

The one Qt Quick UI kit all four apps use, so they look and behave alike and stay Figma-simple. Qt is LGPL,
dynamically linked (PySide6); no GPL-only Qt add-ons, and no Qt Quick Controls styles: every control is drawn
here (`QtQuick.Controls` is used only for `Popup` and the window, under the Basic style, fully covered by our drawing).
Shaped by the GUI proofs (`proofs/gui-qt/`, `proofs/gui-mock/`) and the experiment's `docs/GUI_DESIGN.md`.

**How every app behaves:** [`INTERACTION.md`](INTERACTION.md), the shared interaction spec (S30). It covers the
regions, select first then act, selection, the settings panel, the diamond, the timeline, keys, words, and the kit
pieces still to build (its Part 5). It wins over the app specs where they differ.

**Actions, keys and selecting:** [`ACTIONS.md`](ACTIONS.md) (S31): the one action list, the context bar, menus,
Ctrl+K and the key map, and how an app plugs in.

**First layer (S4):** tokens, controls, the inspector built from operation schemas, the Ctrl+K command bar, the
app shell, a demo. Not yet: history / AI panels, Fast / Final viewers, the native viewport slot, a colour picker
popup, a real timeline.

## Layout

```
qml/RostrumKit/         the QML module (import RostrumKit; add shared/gui-kit/qml to the import path)
  Theme.qml             every token: colours, type sizes, spacing, sizes, radii, motion (160 ms reveal)
  FieldFrame.qml        THE field box: background, underline, hover/focus look, padding, text style and alignment
  NumberField / TextField / ChoiceField / ColorField   all a FieldFrame; nothing else draws a field
  Toggle / Slider / Button / KeyHint / Chevron         the other controls (Chevron = the drawn dropdown arrow)
  IconButton / LevelMeter / VScrollBar                 square glyph button; sideways level meter (value, peak); thin scroll bar
  Button has `danger: true` (red text, Theme.danger); Inspector scrolls when long (VScrollBar, in the panel margin)
  Panel / ItemList / Inspector / InspectorRow / CommandBar / TopBar / AppShell
  BlockView (+ BlockItem / BlockPort / BlockWire / BlockAddList, Blocks.js)   blocks joined by wires, data in, requests out (BLOCKS.md)
  ToolRail / ToolFlyout / RailIcon   the tool rail: icons only; the app gives `groups` (id, items with icon / key job / tool or act;
                        `panel: true` opens the app's own panel; `kind` for icons the app draws), `current`, `iconKinds`; it picks
                        by signal. 2D: apps/2d/screen/qml/Rail2D.qml; the small 3D-style list: demo/rail_preview.py
rostrum_gui/            the Python side (uv pip install -e shared/gui-kit)
  rows.py               the inspector's rows from a field operation: order, groups, More, validity (no Qt)
  sections.py           opt-in rows by importance (`sections = True` on a bridge): essentials, every other group
                        folded to its name, the "Find a setting" search; bridge_sections.py: toggleGroup / setSearch /
                        revealField (open its group, scroll to it, focus it) and the `search` property. Open-if-changed groups are
                        this same layout: `sections.OWN[kind] = group` makes that group always open (the thing itself);
                        every other group opens when changed from its start. 3D-style light: demo/groups_preview.py
  many.py               several items selected (`selectMany`): the settings they share, "Mixed" values; an edit is
                        one change on all of them
  edits.py              screen edit -> operation call, its history label, the scrub gesture (no Qt)
  commands.py           the command bar's list from the registry, and the one search (word starts, label first, then
                        each command's `words`; most used first) (no Qt)
  model.py              list model for QML; values change in place so rows animate
  bridge.py             DocBridge: selection, rows, edits, scrubs, undo / redo, commands, status
  parts.py              slots and handlers from outside the bridge class (see below)
  frames.py             PictureWorker: the background picture thread both canvases (2D frames, 3D viewport) use
  app.py                start(): Qt app, import path, fonts, the bridge as `backend`
demo/                   main.py (the kit on rostrum_core.toy.sample()), qml/ stand-ins, make_shots.sh
tests/                  test_bridge.py (one scrub = one change; one edit = one change; undo reverts)
```

## The rules it builds in

- **Rule of individuality.** The inspector is one generic `InspectorRow` per param of the selected item's field
  operation (`registry.field_op(kind)`). A row is shown only while its `valid_when` holds
  (`rostrum_core.conditions.holds(valid_when, item, kind.facts(item, doc))`; `doc` lets a child ask its parent, e.g.
  a note its track's instrument); otherwise it is **absent**, never greyed.
- **Choices show plain words.** A choice row's `options` is `[{value, label}]`: the label is the param's
  `labels={value: words}` if given, else the value in plain words ("warmPad" → "Warm pad"). ChoiceField shows the
  label and sends the value (plain strings still work). A long list (over 8) or a list of fonts (options with `face`:
  each drawn in its own face) opens with a search line; options with `section` sit under a small heading per run (a font list: "In Rostrum", "On this computer"), and the list scrolls only past 20 rows or the window's height. A field that names one of a list the app knows (a font, an item,
  a marker: control "pick", rows.py) is that list, never a text box to type a name or id into.
- **A group you add is added in one click.** A folded group a toggle switches on (`sections.switch_of`: an Outline, a
  Background) is "+ Outline" in the row of names: the click sets the toggle on (one change) and the group shows open; its
  heading's − sets it off. The toggle itself is never a row there. A number can be the switch too: its `words` call its
  default "Off" and the param's `on` says what "+ name" sets (motion blur: 180°); its row stays (it is the amount). A
  group with several switches is several groups. The row of names shows every name, wrapping (never "+ N more").
- **Where a param shows** (`Param.shown`): "" its row while valid; "script" never on a screen (raw data agents write: SVG
  path text, font axis tags); "changed" only while away from its default (an uneven stretch a canvas drag made). A row
  that only repeats its open group's heading ("Anchor" over Anchor X | Y) drops its label.
- **A pair is one setting.** Position (X | Y), Size (W | H), Anchor, Stretch and Tilt share a line (`pairs.py`) and one key
  mark: `toggleAnimate` on either half keys or stops both as ONE change ("Animate Position"); the mark shows their joint state.
- **No side panel:** `AppShell { leftWidth: 0 }` (or `rightWidth: 0`) removes that panel and its gap; the centre
  takes the room.
  Groups with nothing valid vanish. `deep` params sit behind a More row. Order: groups as they first appear,
  primary before secondary, then data order. A row appearing or leaving eases height + opacity over 160 ms;
  a new selection swaps the list at once.
- **Every control drawn once.** Number, text, choice and colour fields are all `FieldFrame`: same box, same
  underline (grey, lighter on hover, accent when in use), same 8 px padding, same left-aligned text with
  tabular digits, unit dim after the value. The dropdown arrow is drawn (not a font glyph), centred at the right.
- **Every GUI action is an operation.** An edit calls `doc.apply([...], Who.person(...))`; a scrub (number drag,
  slider drag) is one `doc.gesture` = one change; Ctrl+Z / Ctrl+Shift+Z (or Ctrl+Y) are `doc.undo / redo` for
  the person. The command bar lists `registry.available(...)`; running a command is an operation. The bridge
  subscribes to the document, so agent and script changes show up in place. A refused edit fails loudly
  (console + red status in the top bar).
- **Layout.** Top bar; left panel | centre viewer | right inspector; the timeline runs the **full width** under both.

## Run

```
.venv\Scripts\python.exe shared\gui-kit\demo\main.py                    # the window
... main.py --step "select cam_1" --step "set dof true" --shot out.png  # scripted, quits by itself
... main.py --sheet --shot controls.png                                 # every control in its states
sh shared/gui-kit/demo/make_shots.sh [folder]                           # all screenshots
.venv\Scripts\python.exe -m pytest -q shared\gui-kit\tests              # under a second
```
Steps: `select <id>`, `set <param> <value>`, `scrub <param> <v> <v> …`, `undo`, `redo`, `more`,
`commands [text]`, `run <command key>`. Screenshots render offscreen with `QT_QPA_FONTDIR=C:/Windows/Fonts`
(without it the offscreen platform has no fonts); hover works offscreen too: a script rests the pointer with `rostrum_gui/pointer.py` › `hover(win, point, ms)` (the `hover` / `hoverobj` steps and the agents' harness use it). Never put a HoverHandler in an item over a control: an item that takes hover hides the MouseArea under it (HoverTip's pointer position comes from TipGate's one handler per window).

## Bridge pieces from other modules (parts.py)

A bridge file need not hold every slot. Two ways (existing bridges keep working as they are):
1. **Slot mix-in.** A plain class (no base, not a QObject) whose methods carry `@Slot`; list it before `DocBridge`:
   `class Bridge2D(ZoomSlots, DocBridge)`. QML sees the slots as the bridge's own; the mix-in uses `self.doc`,
   `self._apply`, `self._guard`. (A QObject base would hide the slots.)
2. **`self.handle("zoomTo", fn)`** registers a Python function by name from any module; QML calls
   `bridge.invoke("zoomTo", [args])`. A `RostrumError` from it is reported like a refused edit.

## The background picture worker (frames.py)

`PictureWorker` is the one thread-and-engine loop behind the 2D canvas and the 3D viewport: newest request wins
(`post_latest`), ordered jobs such as picks run first (`post_ordered`), a failure is reported loudly (`failed`, stderr)
and the next job tries again. An app subclasses it and gives `open_engine`, `handle(eng, job)` and `describe(job, e)`.
The picture is served as `image://<provider>/<serial>` by `ImageProvider`.

## Fields already shown on the page (`on_page`)

`DocBridge.on_page(item) -> set[str]` returns the names of this item's fields that the page's own controls show;
the inspector leaves them out (a group whose members all went goes too). `rows.omit` does the work.

### Switching Sound's onpage.py to the kit hook (request for Team Priyam)

In `apps/sound/screen/screensound/bridge.py`:
- Delete the `_rows` override (the one calling `onpage.omit(super()._rows(), ...)`).
- Add instead:
  ```python
  def on_page(self, item):
      return onpage.fields(self._page, item.get("type", ""), self.doc.kind.registry)
  ```
- In `onpage.py` delete `omit()` (now `rostrum_gui.rows.omit`, called by the kit); keep `ON_PAGE` and `fields()`.
Nothing on screen changes. The kit's `_rows` already runs `rows.omit(..., self.on_page(it))`, so Sound's override is
harmless until it is removed.

## Attribution rows

Nothing new: PySide6 / Qt (LGPL-3.0, dynamically linked) is already recorded.
