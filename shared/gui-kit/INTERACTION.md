# Rostrum: one way of working (the shared interaction spec)

*Team Sam, brief S30, 2026-10-22. Design only: no app code. It sits above the two app specs and wins where they
differ:*
- *Rostrum2D: `C:\Users\Sam\Documents\CODE\Rostrum\apps\2d\UX_SPEC.md`*
- *RostrumSound: `C:\Users\Sam\Documents\CODE\Rostrum\apps\sound\DESIGN.md`*

*Rostrum3D and the Rostrum Editor are designed to the same rules when their turn comes. The same spec with drawn
wireframes is `C:\Users\Sam\.rostrum\waves\results\kit\s30\INTERACTION.html`.*

*Other inputs: `docs/PLAN.md` › Decided (2026-10-22: Scene not comp, select first, the 2D and Sound screens), AGENTS.md
(rule of individuality, layout check, engineering rules), and the GUI kit as it is on `main` and on Team Hem's H28
branch (`C:\Users\Sam\.t3\worktrees\Rostrum\team-hem`, read only).*

**Why this exists.** Someone who learns one Rostrum app should already know how to use the others: the same action,
key, place and word for the same idea. Sam: *"I shouldn't have to explain these, these are very basics."*

**The yardstick: the 3E's.** Each choice below is judged by three questions:
- **Effective:** does it do the whole job, at the level of the reference films?
- **Efficient:** is it the fewest steps, with no detours?
- **Easy:** can a first-day person see what to do, with nothing to remember and every mistake one Undo away?

When the three pull apart, effective wins, then efficient, then easy. Across apps a fourth test is added:
**the same everywhere**. A habit that works in one app and breaks in the next costs more than a slightly better
local choice.

**How to read it.**
- **Part 1** gives the common patterns. Each one says how it works, why (3E), and what each app adds.
- **Part 2** is the one key map.
- **Part 3** is the one word list.
- **Part 4** lists where the two app specs disagreed, what was chosen and why, and the edits made to each spec.
- **Part 5** lists the kit pieces this needs, as a build list for after H28.

---

## The ten shared rules that matter most

| # | Rule | Why |
|---|---|---|
| 1 | **The same window everywhere.** Top bar with project-wide things only. Tools on the left of the view they act on. One context bar at a fixed place at the top-centre of the main view. Settings on the right. The timeline with transport and time at its top-left. | Your eyes go to the same place for the same need in every app. |
| 2 | **Select first, then act, from one action list.** The context bar, right-click, Ctrl+K and shortcuts all read the same list. Each action carries "valid when" and "importance", so an action shows only when the selection allows it. | One list means the four doors always agree, and agents call the very same operation. |
| 3 | **One selection grammar.** Click picks. Ctrl+click adds or removes in lists and timelines. Shift+click picks the run between. A box picks what it touches. Ctrl+A picks all. Esc steps back one level. On a canvas, Shift adds and Ctrl goes deep. | Each place keeps the habit people bring to it, and the rule is the same in every app. |
| 4 | **Animate in place with the diamond.** Every setting that can change over time has a ◇ at the end of its row. Once a setting has keys, changing it at another time adds a key there. K keys the selection at the playhead. In Sound, automation keys use the same ◇ and K. | One idea of "changes over time", learnt once, with no record mode to forget. |
| 5 | **Arrows move what you selected, in the place you are working.** Shift moves a big step, Alt a fine one. Ctrl+←/→ always move the playhead. `,` and `.` jump to the previous or next thing that happens. | One rule instead of a table to memorise, and it carries into 3D and the Editor. |
| 6 | **One gesture is one undo step, and your undo is yours.** A whole drag, an action on 40 things, or a burst of nudges is one step. Ctrl+Z takes back only your own steps. An agent's run is one group you keep or undo whole. | You can let an agent work beside you without fear, and undo never surprises you. |
| 7 | **Drags never lie.** The box and its content move as one, in the same frame. A press under 4 px is a click. Ctrl = no snapping, Alt = drag a copy, Shift = keep it straight. Things snap within 6 px, with a magenta line naming what they caught. | Trust in the picture, and the same modifier keys in every app. |
| 8 | **Saving is automatic, and versions are named.** There is no Save and no "unsaved" state. Ctrl+S saves a named version. The top bar says "Saved" and how many changes are recorded, and that count is never cut. | Nothing is lost, agents and people edit the same file, and Ctrl+S gets a real meaning. |
| 9 | **Nothing greyed out, and nothing silent.** A control that can't act now is absent. Errors are one plain sentence that says what failed and what to do, on the thing itself and in the message line. Red means an error, amber means "not there yet". | The screen only shows what you can use, and you can always trust it. |
| 10 | **The agent is a co-worker, not a mode.** Its changes arrive live and never move your selection, playhead, zoom or the field you are typing in. You see a chip and a 1-second outline, and you can review or undo its work. A locked thing is locked for agents too. The agent reads what you see through `inspect_screen`. | People and agents share one document and never fight over it. |

---

# Part 1 · The common patterns

Every pattern below follows the same layout:
- **How it works:** the clicks, drags and keys, where they live and when they appear.
- **Why (3E):** the reasoning, and what was rejected.
- **Per app:** what each app adds or uses differently. Anything not mentioned is the same everywhere.

## 1.1 The window's regions

```
┌ ≡ App │ Project › Scene ▾ ····· message   Saved · 14 changes │ chips │ ↶ ↷ │ Search Ctrl K │ Export │ ? ┐  top bar
├──┬───────────────────────────────────────────────────────────────────────────┬────────────────────────┤
│T │            ┌ context bar: 3 layers · Group  Mask ▾  Align ▾ ⋯ ┐            │ SETTINGS               │
│O │                                                                           │ name · Kind            │
│O │                       main view                                           │ [Find a setting Ctrl F]│
│L │           (canvas · arrangement · viewer · 3D view)                       │ Essentials             │
│S │                                                                           │ ▸ folded groups        │
│+ │                                                     view controls ▾       │                        │
├──┴───────────────────────────────────────────────────────────────────────────┴────────────────────────┤
│ ▶ 2.48 s ⟳ │ (timeline context: key bar, frame tools)                       │ ◇ Marker  view  ⊟      │  timeline header
│ rows       │ range band · marker band · time scale with the playhead                                  │
│ names      │ bars, keys, clips                                                                         │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Region | Where | Holds | When |
|---|---|---|---|
| **Top bar** | top row, 44 px, one line, never two | Fixed order, left to right: **≡** menu · **project › scene ▾** (or song name) · **message** (what just happened) · **Saved · N changes** · **chips**, each shown only while it has something to say (agent at work, Problems, a running job, an app's own chip such as Sound's loudness) · **↶ ↷** (only when they can act) · **Search Ctrl K** · **Export** (once there is something to export) · **?** | Always. Project-wide things only: nothing that makes or edits one item lives here. |
| **Tool strip** | floating on the left edge of the view it acts on, 40 px wide | Tools that make or draw things, then tools that appear with their thing (Camera with a camera, Bone with a rig), then **+ Add** at the bottom | In apps and views with tools: the 2D canvas, the 3D view, the Editor's viewer. Sound's Editor has two tools (Select V, Draw B), so they sit at the left end of the Editor's header instead. |
| **Context bar** | floating at the **top-centre of the main view** (for Sound, of the area that has focus: the arrangement or the Editor), one row, never wraps | With the Move / Select tool and a selection: what is selected ("3 layers") and its top actions, then **⋯** for the rest. With another tool: that tool's few options. | Only when there is something to say. Hidden while dragging. Never covers the tool strip. |
| **Main view** | the middle | The work itself: the canvas (2D), the arrangement (Sound), the 3D view, the viewer (Editor). Bottom-right: **view controls** (Fit · zoom % ▾ · preview size · Fast / Final). Bottom-left: where you are (the group path "Logo › mark"). | Always. |
| **Settings panel** | right, full height down to the timeline; 256 px at 1280, 264 at 1366, 296 at 1646, 320 at 1920; drag its edge between 256 and 420 | The settings of what is selected; the document's (scene's or song's) when nothing is. **Sheets** take its place when needed: Export, History. | Always (Ctrl+\ folds it away). |
| **Timeline** | bottom, **full width** (side panels stop above it), in 2D, 3D and the Editor. In Sound the arrangement *is* the timeline and fills the main view; Sound's dock (Editor / Mixer) sits below it. | **Header:** transport and time on the left (▶, time, ⟳ loop; Sound adds ● Record when a track is armed, the click, tempo · beats · key), the timeline's context in the middle (key bar, frame tools), view controls on the right (◇ Marker, snap / grid, zoom, ⊟ fold). **Ruler:** range band, marker band, time scale. **Rows:** names on the left, bars / clips / keys on the right. | The header and ruler are always there. |
| **Drawers** | left (Library, Guides); the right-hand sheets take the settings panel's place | The Library (Ctrl+L), Guides (F1). History and Export open as sheets in the right column. | One click away. A drawer pushes the main view aside and never covers it. Below 1500 px wide, the Library floats and closes after each use. |

**Why (3E).**
- *Easy:* the same region holds the same kind of thing in every app, so nothing has to be searched for twice.
- *Efficient:* creation sits beside where things land (the tool strip), and the context bar sits at the top of the
  work, where the eye already is.
- *Effective:* the top bar only carries project-wide things, so it fits on one line at 1280 px and can never overlap.
- *Rejected:*
  - **Transport and tempo in the top bar** (Sound P26). They pushed its top bar to two lines at Sam's size, and 2D's
    transport is in the timeline header.
  - **+ Add in the top bar.** It is not project-wide.
  - **Pages.** Both apps already chose one workspace.

**Per app.**
- *2D:* the tool strip is Library, Move, Shape, Pen, Text, Paint, then + Add.
- *Sound:* there is no canvas tool strip. **+ Add** sits at the left end of the arrangement's header strip, followed
  by transport, position, tempo · beats · key, then Grid ▾, Snap, zoom and fit. "+ Track" stays under the last track.
  The loudness readout is Sound's own chip in the top bar.
- *3D:* the tool strip sits on the 3D view; the timeline is at the bottom, as in 2D.
- *Editor:* each page keeps these regions. The viewer is the main view, and the cut timeline is the timeline.

## 1.2 Select first, then act

**How it works.**
1. You pick the things (1.3), then say what to do with them. Nothing is ever made empty and filled afterwards. +
   Add only creates new content.
2. Every action is **one operation on the selected ids**, the same one an agent calls. It is listed once, in one
   **action list**, with:
   - its label;
   - its key;
   - **valid when** (a condition on the selection);
   - **importance** (primary: on the bar; secondary: under ⋯ and in menus);
   - optionally **promoted when** (a selection that puts it first, such as "all shapes" putting Combine first).
3. The list feeds four doors, and they always agree:
   - the **context bar** shows the count chip ("5 notes"), up to **five** primary actions in rank order, then **⋯**
     for the rest. When space runs short, the lowest-ranked actions fold into ⋯ one by one.
   - the **right-click menu** shows all the valid actions in the same order, a divider, then the edit block (Copy ·
     Cut · Paste · Duplicate · Rename · Delete, each with its key).
     - Right-click on an **unselected** item first selects it alone.
     - On a selected item, it keeps the selection.
     - On empty space it offers that place's "add here" actions (Paste here, Add marker here, Add a sound here …).
   - **Ctrl+K** lists the valid actions first, under a title that says what they will act on ("5 notes").
   - **Shortcuts:** a key does its action only when the action is valid. Otherwise nothing happens and the message
     line says why ("Combine needs two or more shapes selected").
4. The **edit block** (Copy, Cut, Paste, Duplicate, Rename, Delete) never sits on the context bar or under its ⋯. These
   are keys, and they are in the right-click menu.
5. An action with an amount (stagger by, transpose by, fade length) opens a small popover or an inline field in the
   bar. It remembers the last amount, and is one undo step when you click away or press Enter.

**Why (3E).**
- *Effective:* every relating action (group, mask, combine, send to a group, layer as one sound) takes the right
  things in one step, and agents call the same operation.
- *Efficient:* the next step sits where the eye is.
- *Easy:* you select, then see what you can do. Nothing is greyed.
- *Rejected:*
  - **A bar floating under the selection** (H28's and Sound P26's). It jumps while you scroll, covers neighbouring
    tracks or artwork, and falls off-screen.
  - **Two action lists** (H28's app-local `actions.py` beside the registry's `valid_when`). One source of truth.

**Per app.** Each app writes its own actions into the list. The kit draws the bar, the menus and Ctrl+K from it. The
2D table is `UX_SPEC.md` 4.3; the Sound table is `DESIGN.md` 3.0 point 3.

## 1.3 Selection and multi-select

| Gesture | Lists and timelines (layer rows, tracks, notes, clips, keys, strips) | Canvas and 3D view |
|---|---|---|
| Click | picks it alone | picks what is **painted** under the pointer, the outer group first; hover outlines it first |
| Click empty space | clears | clears |
| **Ctrl+click** | adds or removes one | picks the **deepest** piece under the pointer |
| **Shift+click** | picks the **run** from the last clicked to this one (rows between; notes or keys between in time on that row) | adds or removes one |
| Drag a box on empty space | picks everything it touches; **Ctrl+box** adds to the selection | picks everything it touches; **Shift+box** adds; **Ctrl+box** picks the deepest pieces |
| **Ctrl+A** | all of that kind in the focused place (all notes of this track, all tracks, all keys of the open rows) | all at this level |
| Double-click | goes in: opens its detail (Sound's Editor, a group, a symbol) | goes in: into the group, to a path's points, to a text's letters |
| Double-click a **name** · **F2** | rename in place | — |
| Enter / Shift+Enter | go in / go out | go in / go out |
| Tab / Shift+Tab | next / previous item at this level | next / previous item at this level |
| **Esc** | steps back one level (see below) | steps back one level |

- **Esc**, one level per press:
  1. cancel the drag or the typing in progress;
  2. close the open popover, menu or sheet;
  3. clear the innermost selection (keys or points, then items);
  4. leave the entered group;
  5. nothing.
- **One selection** is shared by every place an item shows (canvas, rows, Mixer strip, settings panel). The settings
  panel's title says what is selected ("title · Text", "3 layers", "5 notes").
- **Selecting is not a change:** it is not an undo step and it is not saved. Undo does restore the selection that
  went with the step it undoes, so your next action is on the same things.
- **Locked and hidden** things can't be picked in the main view. They can be picked in rows, so you can unlock them.
- **Mixed kinds** (2 texts and 1 shape; notes and clips): the settings panel shows the settings they share, plus one
  line per kind ("2 texts ›", "1 shape ›"). Click a line to narrow the selection to that kind.
- **Agents never change the person's selection.** If an agent deletes something you had selected, it simply leaves
  your selection.
- **Clicking a marker** selects it **and** moves the playhead to it. Double-clicking it renames it.

**Why (3E).**
- *Easy:* each place keeps its native habit. Lists follow Windows and every file manager. Canvases follow Figma and
  Illustrator.
- *Efficient:* box and Ctrl+A make 40 things one gesture.
- *Rejected:*
  - **One modifier rule for both kinds of place.** Canvas or list users would lose a habit.
  - **Shift adds keys in the timeline** (2D's draft). A timeline is a list in time, so it follows the list rule.
  - **Ctrl+box for "fully inside" on the canvas.** Ctrl already means "deep" there.

## 1.4 The settings panel

**How it works.**
1. **Header:** the name and kind ("title · Text"), or the count ("3 layers"). Under it, **Find a setting** (Ctrl+F).
2. **Essentials:** the few settings used all the time, always open, at the top. Pairs share a row (X Y, W H).
3. **Every other group is folded to its name**, every name in one wrapping line. Click to open it. The panel remembers
   open groups by name across selections. A group you turn on (+ Outline, + Motion blur, + Levels) is turned on by that
   one click; − on its heading turns it off. Pairs (Position, Size) have one key mark for both values.
4. **Search:** typing shows every matching setting from any group, open and editable. It understands people's words
   ("transparency" finds Opacity). Esc clears.
5. **Several selected:** their shared settings, with **Mixed** where the values differ. Changing one sets them all, as
   one undo step.
6. **Nothing selected:** the document's settings (2D: the scene's size, length, frame rate and background; Sound: the
   song's name, tempo, beats per bar, key and length), with the hint "Select something to change it here."
7. **Nothing greyed:** a setting that doesn't apply now is absent. Turn on depth of field and Focus appears; turn it
   off and Focus goes. This is built from each setting's **valid when** and **importance**, never by hand per panel.
8. **Last line:** "Last changed by Claude, 3 min ago (Add glow)". Click it to open History at that step.
9. **Fields:**
   - Drag a field's label left or right to scrub it. Shift scrubs ×10, Alt ×0.1.
   - Type maths: `+20`, `*2`, `50%`.
   - ↑ / ↓ change by one step (Shift ×10, Alt ×0.1).
   - Enter commits, Esc cancels, Tab moves to the next field.
   - Values use the words of the trade with units ("Opacity 100 %", "Level −4.0 dB").
   - **Double-click a slider, knob or fader** to put it back to its default. On any field, right-click › **Reset**
     does the same.
   - The mouse wheel changes a value **only while that control has focus**, so scrolling the panel never changes
     anything by accident.
10. **Sheets:** Export and History open in the panel's place. × or Esc brings the settings back.

**Why (3E).**
- *Easy:* every group's name is visible at a glance, with no long scroll and no tabs hiding things.
- *Efficient:* search and Ctrl+F reach any setting in two keys.
- *Effective:* nothing is left out, because it is all one fold away.
- *Rejected:* tabs, and long open lists.

**Per app.** 2D: per-kind essentials are in `UX_SPEC.md` 4.4. Sound: a track's settings live here once, never also on
cards.

## 1.5 Animating in place: the diamond, keys and easing

**How it works.**
1. **The diamond ◇** sits at the right end of every row that can change over time. It has three looks:
   - **faint** ◇: not animated (always visible, not only on hover, so "this can move" is never hidden);
   - **outlined** ◇: animated, but no key at the playhead;
   - **filled** ◆: a key at the playhead.
2. **Click a faint ◇** to add a key at the playhead with today's value. From then on, **changing the setting at any
   time adds a key there**, or changes the key already there. This works from the field, a scrub, or a drag in the
   main view.
3. **Click a filled ◆** to remove that key. Right-click › **Stop animating** keeps the value at the playhead.
4. **K** keys the selection at the playhead:
   - 2D: position, scale, rotation and opacity on every selected layer.
   - Sound: a key on every open automation lane of the selected tracks.
   - The message says what it did ("Keyed 4 settings on 3 layers").
5. **Keys show in the timeline**, on the item's bar (all its keys) and on the opened setting rows or lanes (that
   setting's keys). They are selected and moved like any timeline item (1.3, 1.6).
6. **The key bar:** with keys selected, the **timeline header** shows Ease ▾ (Linear, Ease in, Ease out, Smooth,
   Spring, Jump, Custom) and a small curve to drag. For one key it also shows Time and Value. Every selected key
   changes. The settings panel **does not** swap to the key: it keeps showing the item.
7. **Curves:** Keys | Curves in the timeline header turns the bar area into the curve view, in the same place.
8. **A** shows the selection's animated rows or lanes (only those that change), and A again folds them.

**Why (3E).**
- *Effective:* the After Effects model, proven for precise keys.
- *Efficient:* no record mode, and K keys many layers or lanes in one press.
- *Easy:* the diamond's three looks say everything, and it is the same mark in every app.
- *Rejected:*
  - **Auto-key and record modes.** People forget them and key by accident.
  - **The settings panel swapping to the key** (H28). You lose sight of the layer.
  - **A separate word and mark for audio automation.** It is the same idea of "a setting that changes over time".

**Per app.**
- *Sound:* lanes open under their track (A). The lane's picker lists only what can change over time. Alt-drag on a
  segment moves that stretch up or down. Ease shapes between keys come when the song file has a per-key `curve`
  (later); until then the key bar shows only Time and Value.
- *3D:* the same ◇, K and key bar.
- *Editor:* clip settings (opacity, position, levels) use the same diamond.

## 1.6 The timeline

**How it works.**
1. **Header** (left to right):
   - transport: ▶ / ■ (Space), the **time** (click to type: seconds, frames, bar numbers in Sound, or a marker name
     such as `#drop`), and **⟳ Loop**;
   - the timeline's own context (the key bar, frame tools);
   - view controls: **◇ Marker**, snap and grid, zoom − + and fit, **⊟** fold.
2. **Ruler**, top to bottom:
   - **Range band**, thin (8 px). Drag on it to set the **time range**. The range shows shaded here and faintly over
     the rows. Double-click the band to clear it. Shift+I / Shift+O set its start or end at the playhead.
   - **Marker band** (and Sound's section band). Each marker is a flag with its name above the ticks, never over the
     time labels:
     - **shared markers** (the project's, seen in every app) are solid with a small chain;
     - **this scene's or song's own markers** are hollow.
   - **Time scale:** ticks and labels. The first label sits inside the left edge, and a label that would be cut is
     left out. **Click or drag here to move the playhead** (scrub). Sound shows two lines: bars, then time.
3. **Playhead:** a line across every row. It follows playback, and turns the page at the right edge while playing.
4. **Markers:**
   - **M** adds a marker at the playhead with its name field open ("Marker 3" selected). Enter keeps it, Esc cancels.
   - A **Shared** switch beside the name is on by default when the document is in a project.
   - Drag a flag to move it. Double-click or F2 renames it. Right-click: Rename · Share with the project / Keep it
     here only · Colour · Delete.
   - Deleting a shared marker says first, in the menu item, what is tied to it ("Delete from the project · 3 things
     tied"). Other apps then show it in Problems.
   - The same name as a shared and an own marker is refused (PLAN).
5. **Bars, clips and keys:**
   - Drag the body to move it in time. Drag its ends to change when it starts and ends.
   - Several selected move together.
   - **Dropping an end on a marker ties it.** A small flag shows on the tied end; hover it to read "On *logo* +0.20 s".
     Drag it away with Ctrl to untie it.
   - Alt+[ / Alt+] trim the selection's start or end to the playhead.
6. **Zoom and scroll:**
   - Ctrl+wheel zooms time around the pointer.
   - Shift+wheel scrolls in time; the wheel scrolls the rows.
   - Alt+wheel makes rows taller or shorter.
   - Ctrl+= / Ctrl+− zoom in steps. **Ctrl+0** fits everything. **F** fits the selection.
   - Space+drag or a middle-drag pans.
7. **Heights:** drag the timeline's top edge, or press ⊟ (full ↔ compact). Each tool remembers its own height.
   Compact shows the header, ruler, the sound row and the selected row. Under 800 px tall it starts compact.
8. **Play:**
   - Space plays and stops.
   - Shift+Space plays from the selection's start.
   - Playing loops over the time range while ⟳ Loop is on (**Shift+L**).
   - Home and End go to the start and end.

**Why (3E).**
- *Effective:* cross-app timing goes by named markers (rule 8), and ties keep things on them when another app moves
  them.
- *Efficient:* tie by dropping, retime by dragging, and one range serves loop, export and notes.
- *Easy:* one ruler layout everywhere: the band at the top makes a range, the scale below moves the playhead.
- *Rejected:*
  - **"Drag on the ruler makes a range"** (Sound P26). In 2D and in every video tool, dragging on the ruler scrubs.
  - **Dashed shared markers** (they read as "disabled").
  - **A separate "play range" and "loop range".** They are one time range.

## 1.7 Arrow keys and nudging

| Keys | Does |
|---|---|
| ← → ↑ ↓ | Move the selection **in the place you are working**, by that place's step. Canvas: 1 px. Timeline: 1 frame. Sound: one grid step in time; ↑ ↓ move notes a half step, or clips to the track above / below. |
| Shift + arrows | A big step: 10 px · 10 frames · one bar · an octave. |
| Alt + arrows | A fine step: 0.1 px · Sound: 10 ms or 1/32 of a beat. Nothing where there is no finer unit (2D's timeline: frames are whole). |
| Ctrl+← / Ctrl+→ | **Always** move the playhead one step: a frame (one grid step in Sound when there is no picture). Ctrl+Shift moves ten. |
| `,` / `.` | Playhead to the previous / next thing that happens: a key, a marker, a drawing, an item's start or end. With a selection, of the selection; with nothing selected, of everything. |
| Shift+`,` / Shift+`.` | Previous / next beat (when there is a tempo). |
| Alt+M / Alt+Shift+M | Next / previous marker only. |

- A **burst of presses** (each less than 1 s after the last), or a held key, is **one** undo step.
- An animated setting nudged at the playhead adds or changes the key there.
- A tied item nudged keeps its tie, with the offset written down (`"#logo+0.2"`).
- With nothing selected, plain arrows do nothing. They never move the playhead by surprise.

**Why (3E).**
- *Easy:* one rule covers space, time and pitch. Shift is "more" and Alt is "less" everywhere, including field
  scrubs and faders.
- *Efficient:* the playhead keys never depend on focus.
- *Rejected:*
  - **Ctrl+arrows as a fine nudge** (Sound P26). They are the playhead everywhere else.
  - **Alt+arrows for the previous / next drawing** (2D). `,` and `.` already do it.

## 1.8 Copy, paste and duplicate

| Keys | Does |
|---|---|
| Ctrl+C / Ctrl+X | Copy or cut the selection: items with their relative places and times, keys with their settings. Cut is one undo step. |
| **Ctrl+V** | Paste **where you would expect it**. Things in space (layers, objects) go back **in place**, above the selection. Things in time (notes, clips, keys) start **at the playhead** on the selected row, keeping their spacing. Keys land on the same settings of the selected items. |
| Ctrl+Shift+V | Paste at the other spot: in space, **at the pointer**; in time, **at their original time**. |
| **Ctrl+D** | Duplicate next to the original. In space, with a small offset; repeat Ctrl+D after moving the copy once and the next copies repeat that offset. In time, right after the selection's end. |
| Alt+drag | Drag a copy. |
| Delete / Backspace | Delete. Shift+Delete deletes and closes the gap on that row (Sound now, the Editor later). |

- A paste that can't land (notes onto an audio track) fails loudly and names why.
- Copied items keep their ties and expressions.

**Why (3E).**
- *Easy:* each kind lands where people expect it. Figma pastes in place; every DAW and editor pastes at the playhead.
- *Efficient:* smart duplicate builds a row of buttons in three presses, and a repeat in music in one.

## 1.9 Undo, and how big a step is

**How it works.**
1. **One gesture is one step:**
   - a whole drag, a box-move of 40 things, a typed value, a scrub, a stroke;
   - an action on the whole selection, a paste;
   - a burst of nudges, or of typing in one field (each under 1 s after the last).
2. **Ctrl+Z / Ctrl+Shift+Z** (Ctrl+Y too), or **↶ ↷** in the top bar.
   - The buttons appear only when they can act, with the step's name on hover ("Undo: Move title").
   - The message line then says **"Undid: Move title"**, and the changed things flash once.
3. **Your undo is yours.**
   - Ctrl+Z takes back your own last step, never an agent's or a script's.
   - If someone else has since changed the same thing, undo changes nothing and says so: "Can't undo 'Move chorus':
     Claude changed those notes since. Undo that first, in History."
4. **An agent run is one group:**
   - **Undo all** takes it back in one step.
   - **Undo this** takes back one step in it.
   - Each says why if a later step depends on it.
5. **Undo across the document and the shared markers:** Ctrl+Z undoes your last change made **in this window**,
   whether it was in the document or in the project's shared markers.
6. **Not changes** (no undo step, not saved): the selection, the playhead, the tool, zoom and scroll, panel heights,
   open groups, the time range, the search text, solo, arming a track.
7. **History** (Ctrl+H, or click "N changes"):
   - It opens as a sheet in the right column. Steps are newest first, each with who (You, Claude, Script), what and
     when.
   - An agent's run is one folded row with **Keep** and **Undo all**.
   - Hovering a step lights up what it touched (2D also shows a before / after picture).
   - A filter at the top: Everyone · You · Agents · Scripts.
   - **Versions** sit at the top (1.19).
8. Undo itself is a step, so undo can be undone. History only grows.

**Why (3E).**
- *Easy:* one gesture is one step, so never half a drag.
- *Effective:* safe to let an agent work, because nothing it does is hidden or hard to remove.
- *Rejected:*
  - **One shared undo stack.** Ctrl+Z would take back the agent's work under you.
  - **Accept or reject before agent changes apply.** That makes two documents at once.

## 1.10 Drag feel

**How it works.**
- **The pointer is the system's own**, and is never drawn by us.
- **A press that moves less than 4 px is a click**, not a drag.
- **The grab point stays under the pointer** (no jump on press).
- **The box, handles and guides move in the same frame as the content.** Overlays are drawn from the state of the
  picture on screen (H28's base fix), so the box and the picture never disagree.
- **While dragging:**
  - a small label by the pointer shows the value (X Y, W × H, angle, "+6 f", "1.20 s → 3.40 s", "−4.0 dB");
  - a faint copy stays where the item was until release.
- **Esc during a drag** cancels it and puts everything back.
- **Modifiers while dragging**, the same in every app:
  - **Ctrl:** no snapping;
  - **Alt:** drag a copy (from the centre on a resize handle);
  - **Shift:** keep it straight (proportions on a resize, 15° steps on a turn, only in time on a timeline).

**Speed budgets** (on Sam's laptop, with a typical scene or song; "p95" means 95 times out of 100):

| What | Budget (median / p95) |
|---|---|
| Handles, box, selection, guides during a drag | the same frame as the content |
| Timeline items, keys, rows, faders (drawn by the screen) | ≤ 16 ms |
| The picture during a drag (2D, 3D, Editor) | ≤ 33 / 50 ms; half size while dragging, full on release (≤ 150 ms) |
| A paint stroke under the pen | ≤ 16 / 25 ms |
| Sound after a release (Sound re-renders what was touched) | target ≤ 150 ms; while playing, heard from the next block |
| Highlight after a click / settings after a click | ≤ 16 ms / ≤ 50 ms |
| A menu, popover, drawer or sheet opening | ≤ 50 ms; no interface animation longer than 120 ms; nothing blocks input |
| Undo | ≤ 50 ms for the change |
| Opening a project | ≤ 2 s to a usable screen |

**Why (3E).** *Effective:* a drag that lies about where a thing is breaks trust and precision. *Easy:* the same
modifiers everywhere. *Rejected:* Shift as "no snapping" (Sound's first round), because Ctrl means that everywhere
else.

## 1.11 Snapping

- **Distance:** within **6 screen px**, at any zoom. At high zoom you can still place freely between grid lines.
- **What it catches**, strongest first:
  1. markers;
  2. the playhead;
  3. other items' edges, centres and keys;
  4. section edges, beats, guides, the layout grid and equal spacing;
  5. the grid, and whole frames (always, in time).

  On a canvas, the frame's edges and centre come first.
- **Feedback:** a thin **magenta** line shows what it caught, with a name for a marker ("logo lands"). Equal gaps show
  their distance.
- **Off:** hold **Ctrl** during the drag. A **Snap** switch in the view controls (2D) or header strip (Sound) turns it
  off for everything; it stays on by default.
- **Dropping on a marker ties.**
- Snapping never changes a value the person typed.

**Why (3E).** *Efficient:* the first try lands right. *Easy:* one colour and one key in every app. *Rejected:* 8 px
(Sound P26) next to 6 px (2D): one number for one feel, in the kit.

## 1.12 Zoom and pan

| Keys | Does, in the focused view (canvas, 3D view, arrangement, Editor, timeline) |
|---|---|
| Ctrl+wheel · pinch | Zoom **around the pointer** |
| Wheel / Shift+wheel | Scroll up and down / sideways (in a timeline, sideways is time) |
| Space+drag · middle-drag | Pan (tapping Space plays; holding it while dragging pans) |
| Ctrl+= / Ctrl+− | Zoom in / out a step |
| **Ctrl+0** | Fit everything (the frame, the song, the cut) |
| **F** | Fit the selection (nothing selected: everything). Shift+2 also works in 2D, for Figma habits. |
| Ctrl+1 | 100 % (pictures only) |

- The view controls at the main view's bottom-right show the zoom ("Fit · 50 % ▾"). Its menu has the same steps.
- The view is **not** a change: there is no undo step, and an agent never moves it.

**Why (3E).** *Easy:* the same keys as Figma, Photoshop and the DAWs, and **F** is Maya's and Blender's "frame
selected", so 3D gets it free. *Rejected:* a zoom tool you pick (a tool for what the wheel does), and Z for zoom to
the selection (Sound P26), because F already means it in 2D curves and in 3D.

## 1.13 The command box (Ctrl+K)

**How it works.**
- **Ctrl+K**, or the top bar's **Search Ctrl K** box. Type, and results come in groups:
  - **Do:** actions valid for the selection, applied to **all** of it. The title says what ("5 notes").
  - **Settings:** go to a setting. It opens its group, puts the cursor in it, and flashes it.
  - **Add:** sounds, symbols, project items by name.
  - **Learn:** sections of the guides.
- ↑ ↓ Enter runs a result; Esc closes (also while the cursor is in the search field).
- Each result shows its key, and (once per run of rows) what it acts on: "3 notes", "Time range". A command on the
  whole song or project has no scope word, never "Document".
- Search matches the start of words and people's words ("transparency" finds Opacity, "import" finds Add from a file).
- An action that isn't valid now is not listed. If you type its exact name, one line says why ("Join needs two clips
  that touch").

**Why (3E).** *Efficient:* pros never leave the keyboard. *Easy:* beginners find what they can't see. The same list is
the agent's `inspect_tools`.

## 1.14 Status line and change count (never cut)

- The **message** in the top bar says what just happened, in words, with who: "You: Moved title", "Claude: added 12
  notes to Strings", "Undid: Move title", "Exported Main.mp4". It is overwritten by the next change. History keeps
  everything.
- After it: **Saved · 14 changes**.
  - "Saved" confirms the change is on disk.
  - The count is the number of recorded steps since this window opened. **Click it to open History** (Ctrl+H).
- **When the top bar runs short**, nothing is cut with "…" and nothing slides under anything. The room goes out by
  priority:
  1. the chips (else each shows only its dot and count);
  2. the message, **whole or not at all**. If it doesn't fit beside "Saved · 14 changes", the count steps back to
     "Saved" (hover says "14 changes"). If it still doesn't fit, the message steps aside: hover on "Saved" says it,
     and History keeps it;
  3. Search (else its icon);
  4. the project name beyond its first 160 px (the scene name never shortens).
- **Never shrunk or hidden:** "Saved" (the door to History), ↶ ↷, Export, ?.
- **Chips** appear only while they have something to say:
  - **agent** ("● Claude is working · 6 changes", then "Claude: 12 changes · Review · Undo all");
  - **Problems** ("2 problems");
  - a **job** ("Exporting Main.mp4 · 42 %", click to see it or cancel);
  - an app's own chip (Sound: "Loudness −15.2 · target −14 ●").
- Every state is checked by the layout check at 1280, 1366, 1646 and 1920 wide.

**Why (3E).**
- *Easy:* you always know what just happened and that it is safe.
- *Efficient:* the count is the one-click door to History.
- *Rejected:* dropping the count (2D's draft). It is the visible proof that every step is recorded and can be taken
  back, it is the door to History, and H28 already keeps it from ever being cut.

## 1.15 Errors in plain words

- **One sentence: what failed, then what to do**, naming the thing:
  - "The font *Söhne* isn't on this computer. Pick another, or install it and it will be used."
  - "The microphone isn't connected. Plug it in or pick another input."
- **Where it shows:**
  - **on the thing** (a red outline and its sentence on a clip, a warning on a layer's row, a field's message under
    it);
  - **in the message line**;
  - if it lasts, in **Problems** (a top-bar chip, only while something is wrong). Each problem is in words, with what
    to do. Click it to select the thing and jump to the moment.
- **Colour:** red only for errors and damage (clipping). Amber means "not at the target yet". Green means fine.
- **Never:** a code, an internal name, a silent fallback, or a broken file reported as success (rule 6). A failed job
  keeps the old result and says why.
- **Not errors:** an action that can't apply is **absent**, not refused. A refused agent change is shown in that run's
  review ("Not changed: you had changed *title · Colour* after Claude last looked"), and the person is not interrupted.
- **Refusals that block** say that nothing was changed: "Lull was saved by a newer RostrumSound. Update it to open
  this. Nothing was changed."

## 1.16 Empty states

- Every empty place says **what goes here and the one way to start**, in one line, with at most two buttons.
- **Never on the canvas** (Sam, 2026-10-24): the work area stays clean, words drawn over it are noise; an empty scene is
  an empty frame, and the tools' hover help says how to start.
- It disappears as soon as there is something, and never comes back as a pop-up.
- Examples:

| Where | Says |
|---|---|
| A new song (Sound) | "Start with a sound." **Add a track** · **Bring in a picture** · "or drop a file here" |
| Empty rows | "Your layers appear here as bars. Drag a bar to change when it shows." |
| History | "Changes you and agents make will be listed here." |
| Search finds nothing | "Nothing called 'xyz'. Try a shorter word." |

- **No tours, no tip of the day, no welcome dialog.** The first run is the start screen (1.19), then the empty state.

## 1.17 The guides window

- **?** › **Guides**, or **F1**, opens the how-to guides in a **drawer on the left, beside the main view** (360 px). You
  follow along while you work: the drawer never covers the work.
- Guides are searchable. Links between guides work, and Back returns. Pictures wider than the drawer are scaled to
  fit.
- Ctrl+K's **Learn** results open the drawer at that section.
- **Ctrl+/** opens the **key list**: every key, grouped by job, searchable, built from the same key map the shortcuts
  use, so it can never be out of date.
- **Hover help:** after **500 ms** over any button or setting, you see its name, one plain sentence (from the
  operation's or setting's `help`) and its key. A trade word ("Loudness", "Matte", "Ease") has a dotted underline the
  first time it shows in a session.
- The **?** menu: Guides (F1) · Keys (Ctrl+/) · Connect an AI agent… · Report a problem (opens the log folder and
  copies the version) · About and licences.
- Guides are tools, not taste: how to use each tool, never finished pieces to copy.

## 1.18 Working with an agent

1. **Connect once:** ? › **Connect an AI agent…** opens the kit's dialog. It lists the AI apps found on this computer,
   each with **Connect**, or the exact text to paste.
2. **Live, never moving you.** An agent's changes arrive as ordinary changes while you watch. Your selection,
   playhead, zoom, scroll, open groups, open dock and the field you are typing in **never change** because of it.
3. **You see who did what:**
   - the **agent chip** in the top bar ("● Claude is working · 6 changes");
   - the message line ("Claude: added glow to title");
   - a **1-second outline** in the agent colour the first time something changes;
   - a small **dot** on each row or track it changed in the last minute.
4. **Review:**
   - When a run ends (or pauses for 5 s), the chip reads "Claude: 12 changes · **Review** · **Undo all**".
   - Review opens History filtered to that run. Each step has its before and after, and **Undo this**.
   - **Keep** folds it away as reviewed. The changes were already in the document: nothing is ever pending.
5. **Your edits win:**
   - If the agent re-runs its script, what you moved by hand stays.
   - If it tries to change something you set after its last look, or something you are dragging right now, the
     operation is refused **to the agent**, with the reason. You see it only in the run's review ("Not changed: you
     had changed it").
6. **Lock is respected:** a locked item (Ctrl+Shift+L, or the lock on its row) can't be changed by anyone. An agent
   gets "*Background* is locked by Sam: unlock it first."
7. **Pointing:**
   - The agent reads what you see with **`inspect_screen`**: the selection's ids with kind and time, the playhead, the
     time range, the open scene or song, and the focused area.
   - Right-click › **Copy for an agent** (also in Ctrl+K) puts a plain line with ids on the clipboard ("2D · Spring
     launch › Main › title · 2.40 s").
8. **When the agent fails:**
   - History's **Agent activity** fold lists its last 20 calls, refused ones included, with the reason.
   - A failed job shows in the job chip, in red, with the reason.
9. **Notes** (2D now, then every app with a picture): **N** lets you scribble directions on a frame that the agent
   reads (`look_notes`).

**Why (3E).**
- *Effective:* trust; you can let an agent work beside you.
- *Efficient:* Undo all instead of many undos, and "the selection" instead of describing things in words.
- *Easy:* no agent mode; the screen behaves the same whoever made the change.
- *Rejected:*
  - **Following the agent** (moving your view to its change).
  - **Locking the document while it works.**
  - **A suggestions mode.**

## 1.19 File actions and recovery

1. **Saving is automatic.**
   - Every change is saved as it happens. There is no Save, no "unsaved" dot and no "Save changes?" question.
   - A new project or song is created at once in the Rostrum projects folder, named "Untitled …". Click the name in
     the top bar to rename it.
   - Agents edit the same file, and their changes are saved the same way.
2. **The ≡ menu**, the same in every app:
   - New (Ctrl+N), Open… (Ctrl+O), Open recent ▸;
   - Duplicate… (Ctrl+Shift+S: a separate copy; the window stays on the original and says so, with "Open the copy");
   - Save a version (Ctrl+S);
   - Show folder;
   - Preferences… (Ctrl+,);
   - Quit (Ctrl+Q);
   - then the app's own items (2D: New scene; Sound: Export MIDI, Move into a project).
3. **Starting:**
   - The app reopens the last project, or the last song in Sound, exactly where you left it: the same scene,
     selection, playhead and zoom.
   - With nothing to reopen, the **start screen** shows:
     - the ways in as three tiles on one grid: **New** (the accent), **Open…**, the app's sample (opened as a copy, so
       the original never changes);
     - recent projects as pictures;
     - three guide cards.
4. **Versions:**
   - **Ctrl+S** saves a **named version**. The name field opens in place at the top of History, with the time as the
     default name.
   - Each version can be **Opened** to look at (read-only, with a banner), **Restored** (a new step that brings
     everything back; nothing is lost) or **Duplicated** as a new scene or song.
   - Every export is marked automatically ("Exported v003").
5. **Recovery:**
   - Nothing needs recovering by hand, because every change is already saved.
   - After a crash, the launcher shows one plain sentence and where the log is, with **Open again**, which returns to
     the last step.
   - If the engine stops, the app restarts it once, then says so.
6. **Missing files and fonts:**
   - The document opens. The items show "missing" on their row and in Problems.
   - **Find…** asks for a folder and relinks every missing file found there, in one change.
   - Play and export stop at a missing file and name it. Nothing is silently converted.
7. **Damaged or newer files:** a plain refusal that says nothing was changed. It offers **Open the last version that
   works** when the history can rebuild it, and **Show folder**.
8. **Export** (Ctrl+E, the top bar's Export):
   - The **Export sheet** takes the settings panel's place, so the work stays visible. It holds:
     - **What for** as a short list in words, each with its file type;
     - the settings for that choice only;
     - the **range** (everything · the time range · marker to marker);
     - where it goes (the project's Renders folder by default);
     - **Export**.
   - Sound's targets (Streaming −14 …) and "+ Another version" live here too.
   - Export runs as a job in the background. When it is done: "Exported · **Play** · **Show in folder**".
   - **Ctrl+Shift+E** exports again with the last settings.
   - An existing file is never replaced without asking: Replace / Keep both / Cancel. This is the one blocking dialog.
9. **Preferences** (Ctrl+,) are the person's machine choices: devices, folders, pen pressure, models, interface size.
   They open in a dialog built like the settings panel, are not in any history, and are never agent operations.
   Scripted runs never touch them or Open recent (`rostrum_core/userhome.py`).

**Why (3E).**
- *Effective:* nothing is lost, and nothing is overwritten.
- *Efficient:* no Save, and export again is one key.
- *Easy:* "Saved" is always true, and the start screen asks one thing.
- *Rejected:*
  - **A classic Save with "unsaved changes"** (Sound's named-song dialog and 2D main's save flow). Agents edit the same
    file, so there would be two copies of the truth. PLAN: files hidden, saving automatic.
  - **Export as a separate dialog over the work** (Sound P26). Every app now uses the same sheet in the right column.

## 1.20 Focus and the keyboard

- **Which area takes keys:** the area you last clicked (main view, timeline, settings panel, a dock, the Library).
  **F6** moves to the next area; an area reached with F6 shows a thin accent line on its top edge (a click shows none:
  the pointer already says where you are).
- **Fields:** a text field takes every key until Enter, Tab or Esc. Space types a space; it does not play. Esc in a
  field returns focus to the main view.
- **Letter keys work only when no field has focus,** so typing a name never switches tools.
- **Arrows, Delete, Ctrl+A, Ctrl+C / V / D** act on the focused area's selection.
- **Pen and touch:**
  - pressure and tilt from any pen; the pen's back end erases;
  - two-finger pinch zooms, two-finger drag pans;
  - a long press is a right-click.
- **Every mouse action is reachable from Ctrl+K,** and every shortcut is on its button's hover help and in Ctrl+/.

---

# Part 2 · One key map

**How the key map works.**
- **Shared keys mean the same thing in every app.** Every Ctrl / Alt / Shift combination below, and the action keys
  (Space, M, K, A, F, Delete, F2, arrows, Esc, Enter, Home, End, `,`, `.`), are shared.
- **App-only keys** are marked **[2D]**, **[Sound]**, or **[app]** when each app may use the key for its own tool.
  Single letters pick **tools and panels** and differ between apps. A letter never means two things in one app, and
  an app-only letter is never an action that removes anything, so a slipped habit from another app is harmless.
- Ctrl = ⌘ and Alt = ⌥ on the Mac.
- **Reserved:** a shared key not yet used in an app is kept for that meaning. The app may not give it another one.

| Job | Key | Does | Where |
|---|---|---|---|
| **Play** | Space | Play / stop (hold + drag: pan) | shared |
| | Shift+Space | Play from the selection's start (hold + drag in 2D: turn the view) | shared |
| | Home / End | Playhead to the start / end | shared |
| | Ctrl+← / Ctrl+→ | Playhead one frame (Sound without a picture: one grid step); Ctrl+Shift: ten | shared |
| | `,` / `.` | Previous / next thing that happens (key, marker, drawing, item edge) | shared |
| | Shift+`,` / Shift+`.` | Previous / next beat | shared |
| | Alt+M / Alt+Shift+M | Next / previous marker | shared |
| | Shift+L | Loop on / off (loops the time range) | shared |
| | Shift+I / Shift+O | Time range start / end at the playhead | shared |
| | R | Record on the armed track (arms the selected track first if none is) | [Sound] |
| | Shift+K | Click (metronome) on / off | [Sound] |
| **Select** | Click · Ctrl+click · Shift+click · box · Ctrl+A · Esc | See 1.3 (lists vs canvas) | shared |
| | Enter / Shift+Enter · double-click | Go in / go out | shared |
| | Tab / Shift+Tab | Next / previous item at this level (in fields: next field) | shared |
| | Ctrl+Shift+F | Find an item in the rows (layers, tracks) | shared |
| **Edit** | Ctrl+Z · Ctrl+Shift+Z (Ctrl+Y) | Undo / redo your own steps | shared |
| | Ctrl+C / Ctrl+X / Ctrl+V | Copy / cut / paste (in place for space, at the playhead for time) | shared |
| | Ctrl+Shift+V | Paste at the pointer (space) / at the original time (time) | shared |
| | Ctrl+D | Duplicate next to it | shared |
| | Delete · Backspace | Delete | shared |
| | Shift+Delete | Delete and close the gap | shared (Sound now, Editor later) |
| | F2 | Rename | shared |
| | Arrows · Shift · Alt | Nudge · big step · fine step (1.7) | shared |
| | Ctrl+↑ / Ctrl+↓ | Pitch by a scale step (notes) / pitch only (clips) | [Sound] |
| | Ctrl+] / Ctrl+[ | Forward / back in the stack (tracks: down / up the list) | shared |
| | Ctrl+Shift+] / [ | To the front / back | shared |
| | Ctrl+G / Ctrl+Shift+G | Group / ungroup (2D: layers; Sound: tracks into a group, clips into one sound) | shared |
| | Ctrl+Shift+H | Hide / show (2D layers, 3D objects) | shared |
| | Ctrl+Shift+L | Lock / unlock, for people and agents | shared |
| | Ctrl+T | Split at the playhead | shared (Sound now; 2D layers and the Editor later) |
| | Ctrl+J | Join | shared (Sound now) |
| | Alt+[ / Alt+] | Trim the selection's start / end to the playhead | shared |
| | Ctrl+Alt+C / Ctrl+Alt+V | Copy / paste style (looks, effects) | shared |
| **While dragging** | Ctrl · Alt · Shift | No snapping · a copy · keep it straight | shared |
| **Animate** | ◇ click | Start animating / remove the key here | shared |
| | K | Key the selection at the playhead | shared |
| | A | Show / hide the selection's animated rows / automation lanes | shared |
| | F9 · Shift+F9 · Ctrl+Shift+F9 · Ctrl+Alt+J | Smooth · ease in · ease out · jump | shared (2D now; Sound when curves land) |
| | M | Marker at the playhead (name it at once) | shared |
| **View** | Ctrl+wheel · pinch | Zoom at the pointer | shared |
| | Shift+wheel · wheel | Scroll sideways / up and down | shared |
| | Alt+wheel | Row height (timelines) | shared |
| | Space+drag · middle-drag | Pan | shared |
| | Ctrl+= / Ctrl+− · Ctrl+0 · Ctrl+1 | Zoom step · fit all · 100 % | shared |
| | F (2D also Shift+2) | Fit the selection | shared |
| | Ctrl+\ | Hide the side panels and fold the timeline / dock; again to bring them back | shared |
| | F6 | Focus the next area | shared |
| **Panels** | Ctrl+L | Library (2D: symbols, styles, brushes, brand kit; Sound: instruments and sounds) | shared |
| | Ctrl+H | History | shared |
| | Ctrl+F | Find a setting | shared |
| | E · X | Editor dock · Mixer dock | [Sound] |
| **Find and help** | Ctrl+K | Search and run anything | shared |
| | F1 | Guides | shared |
| | Ctrl+/ | Key list | shared |
| **Files** | Ctrl+N · Ctrl+O | New · Open | shared |
| | Ctrl+S | Save a version | shared |
| | Ctrl+Shift+S | Duplicate (a separate copy) | shared |
| | Ctrl+I | Add from a file | shared |
| | Ctrl+E · Ctrl+Shift+E | Export… · export again | shared |
| | Ctrl+, | Preferences | shared |
| | Ctrl+Q | Quit | shared |
| | Ctrl+Shift+N | New scene | [2D] |
| **Tools** | V | Move / Select (the default tool) | shared |
| | B | Paint / Draw | shared (2D: Paint; Sound Editor: Draw notes) |
| | N | Notes on the picture | shared (2D now) |
| | R O L P T C J · E G (while painting) · [ ] · 1–0 | Rectangle, Ellipse, Line, Pen, Text, Camera, Bone · Eraser, Fill · brush size · opacity | [2D] |
| | Q · T · S · H (hold) · Shift+M · Shift+S | Quantise · next take · swap a sound · hear the original · mute · solo | [Sound] |
| **Frame by frame** | Alt+N · Alt+Shift+N · = / − · Alt+O | New drawing · copy of this drawing · hold longer / shorter · onion skin | [2D] |
| **Arrange** | Shift+A · Alt+A / D / W / S · Alt+H / V · Ctrl+Alt+M · Ctrl+Alt+U / S / I / X · Ctrl+Alt+K | Auto layout · align · centre · mask · combine · make symbol | [2D] |

**Kept free for 3D and the Editor.**
- **J / L:** the Editor's play-backward / play-forward shuttle.
- **W E R:** 3D's move / turn / scale handles. 2D's R (Rectangle) is a tool, so it does not collide.

The Editor's "stop" stays Space, and **K stays "key here"** in every app.

---

# Part 3 · One word list

On screen, in guides and in hover help, one idea has one word. The trade word, where one exists, appears on hover and
is found by search. Operation names may differ (they are for agents), but their descriptions use these words.

| Say | Means | Not |
|---|---|---|
| **Project** | The folder that holds everything for one film: scenes, songs, 3D scenes, edits, markers | file, workspace |
| **Scene** | 2D's canvas with its own size, length and timing; in 3D, a 3D scene | comp, composition, precomp |
| **Song** | One RostrumSound document (music, voice or effects) | session, project (in Sound) |
| **Layer** | One thing in a 2D scene (shape, text, picture, drawing, group) | object, element (in screen text) |
| **Track** | One row of a song | channel (a track's mixer strip is its **strip**) |
| **Item** | Any selectable thing, when the kind doesn't matter (guides, errors) | node, entity |
| **Settings** / **settings panel** | The selection's values, on the right | inspector, properties, parameters |
| **Preferences** | The person's machine choices (devices, folders) | settings (that word is taken) |
| **Context bar** | The one bar of actions for the selection, or of the tool's options | action bar, toolbar |
| **Action** | Something you do to the selection (Group, Quantise) | command, operation (on screen) |
| **Library** | The left panel of reusable things: symbols, styles, brushes (2D); instruments and sounds (Sound) | assets, Sounds panel, browser |
| **Add** | Make or bring in something new (+ Add, Add from a file…) | Import, Place, Insert, New … (for items) |
| **Export** | Make the final file(s) | Deliver, Render, Bounce (Bounce is Sound's "turn tracks into one recording") |
| **Group** | Several things acting as one: layers in 2D, tracks playing into one group channel in Sound | precomp, folder, bus (bus on hover) |
| **Symbol** | A reusable 2D piece with its own time | component, precomp, nested scene |
| **Key** | A set value at a moment (also in Sound's automation lanes) | keyframe, automation point, node |
| **Animate / animated** | A setting that changes over time (2D, 3D); **automation** is Sound's trade word for the same, used for its lanes | — |
| **Ease** | How a change starts and lands | interpolation, tween |
| **Marker** | A named moment. **Shared marker:** the project's, in every app. **This scene's / song's marker:** only here. | cue, locator |
| **Tie / untie** | An edge or key held to a marker so it moves with it | pin, unpin, link (link is between values) |
| **Link** | One value following another (2D) | bind, expression (an expression is code) |
| **Time range** | The stretch of time you marked on the ruler's top band; it loops and sets export ranges | play range, loop range, work area, in / out |
| **Playhead** | The line that marks "now" | cursor, CTI |
| **Timeline** | The rows over time at the bottom (in Sound, the arrangement) | dope sheet, sequencer (on screen) |
| **History** | The list of every change with who did it | undo stack, log |
| **Version** | A named point in History you can go back to | snapshot, checkpoint, save |
| **Saved** | On disk (always, automatically) | — |
| **Problems** | What is wrong now, each with what to do | errors, warnings, diagnostics |
| **Job** | Long work done in the background (export, clean-up, render) | task, process |
| **Agent** | An AI working through the app's tools (named: "Claude") | bot, assistant, AI (as a noun on its own) |
| **Notes** | Directions drawn on the picture for an agent or team | comments, annotations |
| **Guides** | The how-to pages (and, on a canvas, **guide lines**) | help docs, tutorials |
| **Fast / Final** | Lighter preview while playing / exactly the export | draft, proxy (proxy is the Editor's media word) |
| **Hide / show** (2D), **mute / solo** (Sound) | Out of the picture and the export / silent, or only this heard | disable, bypass (bypass is for one effect) |
| **Lock** | Nobody can change it, agents included | freeze |
| Spelling | **Colour, Centre** (British, as on every screen today) | Color, Center |

---

# Part 4 · Where the two specs disagreed

## 4.1 The differences and the choices

| # | Topic | 2D said | Sound said | Chosen | Why |
|---|---|---|---|---|---|
| 1 | **Saving** | Automatic; no unsaved state; Ctrl+S = save a version | File menu with Save / Save as; an unsaved dot; "Save changes?" on close; Ctrl+S names an untitled song | **Automatic everywhere.** New documents get a name at once in the projects folder. Ctrl+S = save a version. Ctrl+Shift+S = Duplicate. | PLAN: files hidden, saving automatic. Agents edit the same file, so a second "unsaved" copy can't exist. |
| 2 | **App menu** | ≡ | File | **≡**, the same items in every app (1.19) | It holds more than files (Preferences, Quit), and "File" invites "where is Save?". |
| 3 | **Top bar contents** | Project-wide only; transport in the timeline header | Transport, position, tempo, loudness, + Add, Deliver in the top bar (two lines at 1646) | **Project-wide only.** Sound's transport, position and tempo move to the arrangement's header strip, + Add to its left end; loudness stays as a chip. | One line at every size; the same place for play and time in every app. |
| 4 | **Change count** | Dropped ("means nothing") | "N changes", click = History | **Kept:** "Saved · N changes", never cut (steps back to "Saved" only so a message fits whole), click = History | It proves every step is recorded, it is the door to History, and H28 already keeps it from being cut. |
| 5 | **The bar of actions** | "Context bar", fixed at the canvas's top-centre, also holds tool options | "Action bar", floats under the selection and flips above; More ▾ | **Context bar at the top-centre of the main view** (Sound: of the focused area); ⋯ for the rest; tool options too | A fixed place never jumps, never covers neighbouring tracks or art, and is never off-screen. One name. |
| 6 | **Edit block on the bar** | Duplicate and Delete under ⋯ | Never on the bar | **Never on the bar or its ⋯**; keys and right-click | The bar keeps room for the actions that matter. |
| 7 | **Adding to a selection in timelines** | Keys: Shift+click adds | Ctrl+click adds, Shift = run; but automation keys used Shift-click to add | **Ctrl+click adds, Shift+click = run** in every list and timeline | A timeline is a list in time; one rule. |
| 8 | **Box with a modifier** | Canvas: Ctrl+drag = fully inside | Ctrl+box adds | Lists: **Ctrl+box adds**. Canvas: **Shift+box adds**, Ctrl+box = deepest | The add key adds in each place; Ctrl means "deep" on a canvas. |
| 9 | **Clicking a marker** | Drag moves; double-click renames | Click selects and moves the playhead; double-click went to it (3.6e) or renamed (3.0) | **Click = select + playhead; double-click = rename** | Sound contradicted itself; rename by double-click is the rule for every name. |
| 10 | **Dragging on the ruler** | Drag scrubs; the top band sets the play range | Drag makes a time range | **Top band = range; the scale scrubs** | Every video tool scrubs on the ruler; one layout. |
| 11 | **Play range / loop range** | "Play range", Shift+I / O | "Loop range", "time range", C toggles loop | **One "time range"**; ⟳ Loop with **Shift+L**; Shift+I / O | One idea; C is 2D's Camera tool. |
| 12 | **Ctrl+← / →** | Playhead one frame, always | Fine nudge | **Playhead, always.** Fine nudge = **Alt+arrows** | A key that sometimes moves the playhead and sometimes the selection breaks trust. |
| 13 | **Alt+arrows** | Previous / next drawing, hold longer / shorter | Kept unused on purpose | **Fine step everywhere.** 2D's drawing jumps are `,` / `.` (they already were); hold is = / − | Alt = "finer" is already 2D's scrub rule. |
| 14 | **`,` / `.`** | Previous / next key, marker or drawing | One picture frame back / forward (proposed) | **Previous / next thing that happens.** Frames are Ctrl+← / → | Two keys for the same frame step would be waste. |
| 15 | **Shift / Alt on faders and scrubs** | Shift ×10, Alt ×0.1 | Fader Shift = fine | **Shift = more, Alt = finer**, everywhere | One meaning per modifier. |
| 16 | **Zoom to the selection** | Shift+2 | Z | **F** (Shift+2 kept in 2D) | F is already "fit" in 2D's curves, and is "frame selected" in Maya and Blender (3D). |
| 17 | **K** | Key the selection here | Click (metronome) | **K = key here** in every app; Sound's click = Shift+K | "Key" is a verb in 2D, 3D and the Editor; the metronome is Sound-only. |
| 18 | **Show what changes over time** | U | A | **A** in every app | Plain mnemonic (animated / automation); U was an After Effects habit. |
| 19 | **Automation's parts** | Diamond, keys, key bar | ◇ in settings, "points" on lanes | **Keys and the same ◇**; changing an automated setting at the playhead adds a key; the key bar for keys once curves land | One idea of "changes over time". |
| 20 | **Library** | Library drawer, Ctrl+L | "Sounds panel", L | **Library, Ctrl+L**, left | One name and key for "reusable things to bring in" (PLAN's asset library); L is 2D's Line tool. |
| 21 | **Bringing things in** | "+ Place", Place a file…, Ctrl+I | "+ Add", From a file… | **+ Add**, "Add from a file…", Ctrl+I | "Add" is the plainest word; "Place" was jargon. |
| 22 | **Final file** | Export (Ctrl+E), export again Ctrl+Shift+E; a sheet in the right column | Deliver (Ctrl+Shift+E), a dialog | **Export, Ctrl+E**, the sheet in the right column; Ctrl+Shift+E = again | Everyday word; the work stays visible; one key. The Editor's page is still called Deliver (PLAN); its button says Export. |
| 23 | **App choices** | Preferences (a sheet) | Settings (a dialog), Ctrl+, | **Preferences, Ctrl+,, a dialog** | "Settings" is the settings panel's word; preferences are not about the document. |
| 24 | **Help keys** | Ctrl+/ shortcut sheet; Guides in a left drawer | F1 = Help with keys; guide viewer dialog | **F1 = Guides** (left drawer); **Ctrl+/ = key list** | Windows' Help key for help; the drawer lets you follow along. |
| 25 | **History place** | Right drawer pushing the canvas | Right column over the settings panel | **A sheet in the right column** | The main view stays the same size, and the hover highlight stays visible. |
| 26 | **Undo burst** | Presses < 1 s apart = one step | Ends 500 ms after the key is let go | **< 1 s apart** | One number in the kit. |
| 27 | **Undo refusals** | Only in History's "Undo this" | Ctrl+Z refuses when someone else changed it since | **Sound's rule for both** | Undo never silently takes back over someone else's work. |
| 28 | **Snap distance** | 6 px | 8 px | **6 px** | One feel; Ctrl frees it. |
| 29 | **Hover delay** | 0.5 s | 600 ms | **500 ms** | One number. |
| 30 | **Agent flash** | 0.6 s outline, dot on rows | ~1.5 s flash | **1 s outline + dot on rows for a minute** | Long enough to notice, short enough not to distract. |
| 31 | **Agent chip** | In the top bar | Message line only | **Chip in both** | One place to see that an agent is working, and to Review / Undo all. |
| 32 | **Agent's view of the screen** | `inspect_screen` | `inspect_selection` | **`inspect_screen`** (selection, playhead, time range, open document, focus) | One shared core tool; it carries more than the selection. |
| 33 | **Pointing for an agent** | "Copy link for an agent" | "Copy for an agent" | **Copy for an agent** | Shorter; it is not a link. |
| 34 | **Lock** | Lock layers; refused for agents | No lock | **Lock in both** (Sound: tracks), Ctrl+Shift+L | The simplest way to protect your work from an agent (PLAN rule 3). |
| 35 | **Tie words** | Tie / untie | Tie; "Unpin" | **Tie / untie** | One word. |
| 36 | **Marker looks** | Flags | Shared solid with a chain, own hollow | **Sound's looks** in both, plus the Shared switch on M | Dashed reads as disabled; 2D needs the shared / own difference too. |
| 37 | **Comp** | "Comp" kept, flagged | — | **Scene** (PLAN 2026-10-22) | Plain word, and "comp" means compositing in the Editor. |
| 38 | **Sam's window size** | 1646 × 950 | 1646 × 900 | **1646 × 900** | AGENTS.md's figure for the layout check. |
| 39 | **Start** | Start screen | Opens the last song, else a new untitled one with a card | **Reopen the last; else the start screen** | One first-run in every app. |
| 40 | **Picture toggle key** | — | P proposed, while P is also reserved for parts | **No letter**; its − button and Ctrl+K | Sound had a clash inside itself. |
| 41 | **Mixed kinds selected** | Shared settings | Shared plus a narrowing line per kind | **Sound's**, in both | Narrowing is one click instead of reselecting. |
| 42 | **"Who changed this" line** | — | Last line of the settings panel | **In both** | Cheap (`history.who`), and answers the commonest agent question. |

Things both specs already agreed on are written once in Part 1:
- one workspace, no pages;
- select first, from one action list;
- the settings panel model;
- diamonds always visible;
- one undo step per gesture, per-person undo;
- Ctrl = no snapping, Alt = a copy, Shift = straight;
- Ctrl+D, Ctrl+G, Ctrl+] / [, F2;
- plain errors, nothing greyed, empty states that teach;
- agents never move the person;
- the layout check at four sizes.

## 4.2 The edits made to each app spec

Every edit in the two spec files is marked **(S30)**. Each spec also has an "S30 shared-spec changes" box at its top,
listing every change with its section, so drawings that weren't redrawn (the ASCII wireframes) read correctly.

**`apps/2d/UX_SPEC.md`**
1. "comp" → **scene** on screen everywhere (operation names `comp.*` kept). The H28 table row now says "Changed".
2. **+ Place** → **+ Add**. "Place a file…" → "Add from a file…".
3. Change count **kept** in the top bar ("Saved · 14 changes", click = History). 4.1, 4.2 and 4.8 updated.
4. Context bar's ⋯ no longer holds Duplicate and Delete.
5. Keys in the timeline: Ctrl+click adds, Shift+click picks the run. Canvas box: Shift adds, Ctrl picks the deepest.
6. U → **A**. Shift+2 → **F** (Shift+2 kept as well).
7. Alt+←/→ (previous / next drawing) removed, since `,` / `.` cover it. Alt+↑/↓ (hold) → **= / −**. Alt+arrows = fine
   nudge.
8. "Play range" → **time range**, set on the ruler's top band. ⟳ Loop on **Shift+L**.
9. History opens as a sheet in the right column. F1 = Guides. Ctrl+, = Preferences, which is a dialog.
   Ctrl+Shift+S = Duplicate.
10. Agent outline 0.6 s → **1 s**. "Copy link for an agent" → **Copy for an agent**.
11. Markers: shared ones solid with a chain, own ones hollow; the Shared switch on M.
12. Sam's size 1646 × 950 → **1646 × 900**.
13. Settings panel: narrowing lines for mixed kinds; the "Last changed by" line.
14. Undo refuses over someone else's later change.
15. Added keys: Shift+Space, Alt+M, F6, Ctrl+Q.

**`apps/sound/DESIGN.md`**
1. **Saving is automatic:**
   - no unsaved dot, no Save / Save as, no "Save changes?";
   - Ctrl+S = save a version, Ctrl+Shift+S = Duplicate;
   - the File menu → **≡**;
   - with nothing to reopen, the start screen.
2. **Top bar is project-wide only.**
   - Transport, position, tempo · beats · key and ● Record move to the arrangement's header strip.
   - + Add moves to the strip's left end.
   - Loudness becomes a chip.
3. **Action bar → context bar**, at a fixed place at the top-centre of the focused area. More ▾ → ⋯.
4. **Deliver → Export** (Ctrl+E; Ctrl+Shift+E exports again). It is now a sheet in the right column, not a dialog.
5. **Sounds panel → Library** (Ctrl+L, no longer L).
6. **Settings dialog → Preferences** (Ctrl+,).
7. **K** = key here (automation). The click (metronome) → **Shift+K**.
8. Loop **C** → **Shift+L**. "Loop range" → **time range**, on the ruler's top band. The ruler's scale scrubs.
9. **Ctrl+← / →** = playhead. Fine nudge → **Alt+← / →**. `,` / `.` = previous / next thing that happens.
10. Zoom to the selection **Z** → **F**.
11. Automation "points" → **keys**. Automation keys: Ctrl+click adds, Ctrl = free (no more Shift).
12. Faders and knobs: Shift = bigger steps, **Alt = fine**.
13. Hover 600 → **500 ms**. Snap 8 → **6 px**. Undo burst → **< 1 s apart**.
14. **Lock** on tracks (Ctrl+Shift+L), respected by agents.
15. The agent chip in the top bar; the outline 1.5 s → **1 s**; a dot on changed tracks.
16. `inspect_selection` → **`inspect_screen`**. "Unpin" → **Untie**.
17. Picture show / hide loses P (no letter). Double-click a marker = rename.
18. F1 = Guides, Ctrl+/ = key list. Added Ctrl+\, Alt+[ / ], Shift+I / O, Shift+`,` / `.`, Space+drag pans.

---

# Part 5 · The kit pieces this needs (build list, after H28 lands)

**Sizes:** S = under ~100 lines, M = ~100–300, L = over 300. "Today" is `main` plus H28 on `team/hem`, read
2026-10-22.

**Built:** pieces 1–5 (S31, 2026-10-22; see `ACTIONS.md`). 2D runs on them; Sound plugs in through the adapter.
Pieces 7, 10 (the undo rules), 11 and 12 (S32, 2026-10-22; see `HISTORY.md`). Both apps run on them.
Pieces 13, 14, 16, 17, 19, 20, 21 and 22 (S34, 2026-10-22; see `FILES.md`, `EXPORT.md`, `SHELL.md`). Both apps run on
them. Pieces 6, 8, 9, 15 and 18, hold keys in the key map, renaming by clicking the project name and Report a problem
(S35, 2026-10-22; see `TIMELINE.md`, `PANEL.md`, `DRAG.md`, `FILES.md`). Apps adopt 6, 9 and 15 from the notes there.
Sound's "+ Another version" and export range are built in the app (P28). S36 (2026-10-22): reopening at the same
scene / selection / playhead / zoom, Find… for missing files, "Open the last version that works", the marker
right-click menu, "Fit · 50 % ▾" (`ViewControl`), the settings panel's "Effects (n) +" and right-click › Reset,
`Popover`, `EdgeFade`, `Theme.snap`; in the core one undo step across documents (`joint.py`) and markers that follow
another app's item (`links.py`); see `FILES.md`, `PANEL.md`, `shared/core/OPERATIONS.md` § 6. Not built yet: the
dotted underline on trade words, Cancel in Sound's export.

**Order:** the first six unblock both apps' rebuilds. Do them one at a time, by Team Sam alone, since they are
shared-layer work.

| # | Piece | Today | What must change | Size |
|---|---|---|---|---|
| 1 | **One action list in the kit** (`rostrum_gui/actions.py` + registry) | H28 has an app-local `apps/2d/screen/screen2d/actions.py` (172 lines: `valid(Facts)`, importance "bar" / "menu", `calls`). The registry has `valid_when` and `importance` on operations, and H28 adds `min_targets`. Two validity models. | Move the generic part into the kit. Actions are registry operations, or app "do" actions, with `valid_when`, `importance` (primary = bar, secondary = ⋯), `promoted_when`, `key` and `label`. Apps supply only their entries. The context bar, menus, Ctrl+K and the shortcuts all read it. | M |
| 2 | **Context bar** (`ContextBar.qml`) | H28's app-local `ActionBar.qml` (94 lines), floating under the selection | Kit piece at a fixed top-centre place of a given view. Count chip, up to 5 actions by rank, fold to ⋯ when narrow, a tool-options mode, inline amount field and popover slot. Hidden while dragging. | M |
| 3 | **Menus with keys and dividers** (`Menu.qml`) | Kit Menu (45 lines): no keys, no dividers, no open-at-point. App copies: H28 `ActionMenu.qml`, Sound `HintMenu.qml`. | Add the key chip, groups and dividers, `openAt(x, y)` and the edit block. Delete both app copies. | S |
| 4 | **Key map** (`rostrum_gui/keymap.py` + `KeyMap.qml`) | None: `Shortcut`s are spread over many QML files in each app, with key strings also in Python data | One data list (id, keys, label, shared / app, the action it runs, when it is active), with the shared keys of Part 2 built in. It creates the shortcuts, feeds hover help and the Ctrl+/ key list, and refuses an app key that takes a shared one. | M |
| 5 | **Selection rules** (`bridge_select.py` + `selection_rules.py`) | H28 kit `bridge_select.py` (83 lines, `selectMany`); 2D's own `multi.py`; Sound single-select | List vs canvas modifier rules (1.3), box helper, the Esc ladder, run (Shift) picking in lists and timelines, restoring the selection on undo, mixed-kind narrowing. | M |
| 6 | **Timeline kit** (`Ruler.qml`, `TimelineHeader.qml`, `rostrum_gui/timeview.py`) | Kit `Ruler.qml` (133 lines): no zoom or scroll, flags only. Zoom and scroll exist only in Sound (`view.py`, `Timeline.qml`, `HScroll`, `PinchGrow`). H28's 2D timeline is app-local (`LayerTimeline` and others). | Move Sound's zoom / scroll / fit / follow into the kit. The Ruler gains the range band, shared / own marker looks, first label inside, a two-line scale hook (bars), click and drag to scrub, and M with its name field and Shared switch. A header with three slots (transport, context, view) and ⊟. | L |
| 7 | **Top bar** (`TopBar.qml`) | H28 rewrite (+156 lines): message and count separate, the count never shrinks, the give-way order. 2D-local `UndoRedo.qml`. | Keep H28's version. Add the ≡ slot, a chips row (agent, Problems, job, app chip), ↶ ↷ moved into the kit, the Export slot, and the fixed order of 1.1. Remove Sound's `tools` use (transport moves out). | M |
| 8 | **Settings panel extras** (`Inspector.qml`, `many.py`, `rows.py`) | H28: Essentials, folded groups, search, Mixed, open groups remembered | Narrowing lines for mixed kinds. The "Last changed by" line. The ◇ always faint (H28's "still" mark shows only on hover). Double-click to reset sliders. The wheel only with focus. Alt fine / Shift coarse scrubs. | S |
| 9 | **Drag and snap** (`rostrum_gui/drag.py`, `snap.py`) | Kit `edits.Drag` / `Scrub`; `markers.snap`; snapping is app-local (Sound `timing.py`, H28 `bar_drag.py`) | One threshold (4 px), modifiers (Ctrl, Alt, Shift), Esc cancels, the value label, snap targets in order within 6 px, the magenta line with a name, tie on a marker drop. | M |
| 10 | **Nudge and undo bursts** (core `edits` / history) | Merging exists for typing; nudge merging is per app | One rule: presses under 1 s apart are one step. "Undid:" wording. Refusal over someone else's later change. | S |
| 11 | **History sheet** (`HistorySheet.qml` + core) | None on screen. The core has who, groups, per-author undo and `undo_changes`. | Right-column sheet: steps by who, folded agent runs with Keep / Undo all / Undo this, a filter, hover highlight, versions at the top, Agent activity. Core: `history.undo {step}`, `version.save` / `restore` and the MCP `edit_undo`. | L |
| 12 | **Agent pieces** | `agents.py`, `ConnectAgentDialog.qml` | The agent chip, a 1 s outline in the agent colour, a dot on rows, `inspect_screen` (shared core + MCP), Copy for an agent. | M |
| 13 | **Files and start** (`rostrum_gui/docfiles.py`, `StartScreen.qml`) | All app-local: 2D `files.py` (Save / Save As / unsaved dot), Sound `session.py` (untitled area, ask on close); shared `userhome.py` | One automatic-save model, the ≡ menu items, Duplicate, Show folder, Save a version, Open recent, reopen-last, the start screen, the missing-file Find…, plain damaged / newer refusals. Remove both apps' save questions. | M |
| 14 | **Export sheet frame** (`ExportSheet.qml`) | 2D-local export panel; Sound's master-strip render | A sheet in the right column: What for list, a slot for per-choice settings, range, where, Export, the job chip, Replace / Keep both / Cancel. Apps fill the choices. | M |
| 15 | **Canvas view** (`rostrum_gui/canvasview.py`) | Planned in H28 (A) as 2D-local zoom / pan | Zoom at the pointer, Space+drag and middle-drag pan, F, Ctrl+0 / 1, the view controls. Kit-owned so 3D and the Editor's viewer reuse it. | M |
| 16 | **Guides drawer and key list** (`GuideDialog.qml` → `GuidesDrawer.qml`, `KeyList.qml`) | `GuideDialog.qml` (58 lines, a dialog); F1 opens About | The guides as a left drawer; F1 opens Guides; a Ctrl+/ list built from the key map; About moves into the ? menu. | S |
| 17 | **Hover help** (`HoverTip.qml`) | HoverTip exists; H28 adds hover for long names | 500 ms; name + one sentence (`help`) + key from the key map; a dotted underline the first time for trade words. | S |
| 18 | **Name label** (`NameLabel.qml`) | Ad hoc elides | One piece: shortens with "…" and shows the whole name on hover, used for every name (rows, strips, titles). | S |
| 19 | **Empty state** (`EmptyHint.qml`) | Ad hoc texts in each app | One line and up to two buttons; it goes once there is content. | S |
| 20 | **Focus and areas** (`AppShell.qml`) | No visible focus; no F6 | An accent edge on the focused area, F6, Ctrl+\ to fold panels, Esc back to the main view from fields. | S |
| 21 | **Problems and job chips** (`ProblemsChip.qml`, `JobChip.qml`) | 2D-local `ProblemsPanel.qml` | Kit chips: Problems list in words with fixes, click to jump; the job chip with progress, cancel and failure in red. | S |
| 22 | **Layout check states** | `layout_check.py` with H28's scroll fix | Add a state for every new piece above (long texts included) at the four sizes, and fail on a top bar that wraps. | S |

**Totals:** about 3 L, 10 M, 9 S. That is roughly four briefs of ~2 h for Team Sam after H28 merges:
- **(a)** pieces 1–5;
- **(b)** pieces 6 and 9;
- **(c)** pieces 7, 10, 11 and 12;
- **(d)** pieces 13–22.

Each app then rebuilds its screen on these pieces: 2D first (H28 is closest), then Sound.

**What H28 should know now** (no edit to their branch; for the manager to pass on):
- the action bar is fixed at the top-centre, not under the selection;
- ◇ is always faint, not hover-only;
- keep the change count (H28 already does);
- U is A; F fits the selection;
- Ctrl+click adds keys in the timeline;
- their `actions.py` will move into the kit, so keep it data-only.

---

## Appendix · For Rostrum3D and the Editor when their turn comes

- **Regions:**
  - 3D: tool strip on the 3D view; settings on the right; timeline at the bottom; Fast / Final in the view controls.
  - Editor: each page (Story → Deliver) keeps the same top bar, settings panel and timeline. The viewer is the main
    view. The Deliver page's button says **Export**.
- **Keys kept for them:**
  - F frames the selection;
  - W / E / R for the move / turn / scale handles (3D);
  - J / L shuttle, with Space play / stop and K still "key here" (Editor);
  - Ctrl+T split, Shift+Delete ripple delete, Alt+[ / ] trim to the playhead (Editor).
- **Words:** a 3D "scene" is the 3D document's scene; the Editor's **compositing** page is "Comp" by PLAN, which is
  why 2D says Scene.
- **Agents:** `inspect_screen`, Copy for an agent, Notes and the History sheet all come from the kit.
