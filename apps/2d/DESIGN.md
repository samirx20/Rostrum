# Rostrum2D — how the screen is laid out and how you work in it

*Team Hem, H28, 2026-10-22. Written for Sam. The direction was decided by the manager (docs/PLAN.md › Decided,
"Rostrum2D's screen and workflow"); this is the detailed design. The yardstick is Sam's 3E's: **effective** (you can make
what you want), **efficient** (few steps, no detours), **easy** (you can see what to do).*

## What was wrong

- **Three pages (Design / Draw / Animate) split one job into three places.** Design was only "add things"; to make
  anything move you switched page, then switched back to change how it looks. Every switch cost a click and hid half
  of what you were working on.
- **When a layer shows was hidden.** Timing was two number boxes deep in a long settings list.
- **The settings panel was one long scroll** (a text layer: 23 settings on screen, 18 more behind More), with headings
  said twice.
- **The top bar ran out of room**: the change count, Undo and Redo slid behind the page switcher on Sam's screen.

## How the best tools do it (studied, not copied)

| Tool | What it teaches us |
|---|---|
| **After Effects** | Every layer is a bar on the timeline: drag it to move it in time, drag its ends to trim. A stopwatch per setting starts animating; after that every change makes a key. Its weak side: dozens of nested property rows, and the layer list and timeline are one huge table. |
| **Rive** | Has a Design mode and an Animate mode — exactly the split Sam disliked. People switch modes all day and forget which one they are in. We take its clean key editing, not its modes. |
| **Jitter** | One workspace. Layers on the left, a timeline at the bottom where each animation is a block on the layer's line. Very quick for UI motion; hand-tuned curves are harder. |
| **Cavalry** | One workspace with a full timeline; you animate any attribute in place with a key button beside it. Attributes are folded into groups. |
| **Figma (Smart Animate)** | No timeline at all: you design two states and it animates between them. Very easy, but you can't time things precisely. Its settings panel is the model for ours: a few settings always on top, the rest in short, named sections. |
| **Apple Motion** | A timeline at the bottom of the one workspace, plus a short "mini timeline" under the canvas so the selected layer's timing is always in view. |
| **Procreate Dreams** | Painting over time in one workspace: the canvas on top, tracks at the bottom. Each track holds its drawings as blocks; you paint straight onto the canvas at the playhead. No page change to paint. |

**What we take:** one workspace (Jitter, Cavalry, Dreams); layer bars you drag (After Effects, Dreams); a key button
beside each setting that starts animating it in place (After Effects, Cavalry); a short settings panel with a few
essentials on top and named folded groups (Figma, Cavalry); painting as a tool you pick, not a place you go (Dreams).
**What we leave:** modes or pages (Rive); deep nested property rows (After Effects).

## The screen

```
┌ Rostrum2D  File  [project •]                 status… · 12 changes  ↶ ↷  + Add  Import  ↗  [Search  Ctrl K]  ? ┐
├──────────────────────────────────────────────────────────────────────────┬────────────────────────────┤
│ CANVAS                                                                   │ SETTINGS                   │
│ ┌──────────────┐                                                          │ Title                      │
│ │ ↖ Move  V    │   the frame at the playhead                              │ Text                       │
│ │ ✒ Pen   P    │                                                          │ [ Find a setting        ]  │
│ │ ✎ Draw  B    │                                                          │ Text      Spring launch    │
│ └──────────────┘                                                          │ Size      88 px            │
│                                                                          │ Colour    ■ #FFFFFF         │
│                                                                          │ X         960 px      ◇    │
│                                                                          │ Opacity   1.00        ◆    │
│                                                                          │ ▸ Text                      │
│                                                                          │ ▸ Timing                    │
│                                                                          │ ▸ Matte                     │
├────────────────────────── drag this edge to make the timeline taller ────┴────────────────────────────┤
│ ▶ 2.48 s  frame 62    Preview size  Full Half Quarter      Add marker    Keys | Curves                      │
│ LAYERS                     │0s      1s      2s  ▼logo lands  3s      4s      5s                            │
│ ▾ ▢ lockup                 │████████████████████████████████████████████████████████████████            │
│     ▢ rule                 │          ███████◆███████◆██████████████████████████████████████            │
│     ○ dot                  │                    ███████◆██████◆██████████████████████████                │
│ ▸ T title                  │              ███◆██◆████████████████████████                                │
│   ▢ card                   │████████████████████████████████████████████████████████████████            │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Regions, and why

1. **Top bar** — the app, File and the project name on the left; on the right what just happened, the change count,
   Undo / Redo, **+ Add**, **Import**, **Export**, search (Ctrl K) and Help. No page switch any more.
   *Why:* things to do live on the right in one row, in one fixed order (efficient: always in the same spot). When the
   window is narrow, things give way in a fixed order and never slide under each other: first the "what just happened"
   message shortens (hover shows all of it), then the project name, then the search box becomes just its icon. The
   change count, Undo, Redo, Add, Import, Export and Help never shrink (effective: they are what you need while working).
2. **Canvas** — the frame at the playhead, as it will export. A small **tool strip** floats at its top-left: **Move**
   (V), **Pen** (P), **Draw** (B). Export, Import and Problems open as small panels on the canvas's right edge.
   *Why:* tools sit where you use them, next to the picture (easy); a tool is a way of using the mouse, not a place.
3. **Settings panel** (right) — the selected thing's settings at the playhead: its name, a **Find a setting** box,
   the essentials, then every other group folded to its name. See "The settings panel" below.
4. **Timeline** (bottom, full width, always there) — play, the time, preview size, Add marker, the Keys / Curves switch
   and, for a drawing, its frame buttons; under that the ruler with the project's markers, and **one row per layer**:
   its name on the left (this is now *the* layers list) and its **bar** on the right. Drag the timeline's top edge to
   make it taller or shorter.
   *Why:* timing is the heart of motion design, so it is always in view (effective). The layers list and the timeline
   were the same list twice; now there is one list, and each layer's name sits right beside when it shows (easy: one
   place to look; efficient: select, rename, reorder and time a layer in one spot). On a 16:9 picture the canvas is
   limited by height, not width, so the old left panel's room gave the picture nothing; the timeline uses that height
   better.

### The layer rows (one list for layers and time)

- **Name side:** the layer's icon and name, indented inside its group; the arrow folds a group or opens a layer's rows.
  Click selects. Double-click (or F2) renames. Drag a name up or down to reorder, or into a group. Right-click: the
  layer menu (the same commands as Ctrl K).
- **Bar side:** a bar from when the layer appears to when it goes. **Drag the bar** to move the layer in time — its
  keys and drawings move with it. **Drag an end** to change when it starts or ends (keys stay where they are). Near a
  marker or the playhead the bar snaps to it; **dropping an end or the bar's start on a marker ties it to that marker**
  (move the marker later and the layer follows — in every app, by the marker's name). A tied end shows a small flag.
- **Keys:** every key of the layer sits on its bar as a diamond. Open the layer (its arrow) for one row per animated
  setting. Click a diamond to select that key: the settings panel shows its time, value and **ease**. Drag a diamond
  to move the key. **Curves** (timeline header) shows the selected layer's animated settings as curves to shape by hand.
- **A drawing** shows where each drawn frame starts and how long it is held, on its bar, as today.

### Animating in place

- Every setting that can move has a diamond on its right. **Click the diamond to start animating it**: a key at the
  playhead with the value it has now.
- Once it is animated, **just change it at another time** (type, drag the number, or drag the layer on the canvas):
  a key is added there. Changing it on a key changes that key. Click the diamond again to stop animating (the value
  at the playhead stays).
- Filled diamond = a key right here; outlined = animated, but no key here; faint (on hover only) = could be animated.
- *Why:* no page to switch to and no "record" mode to forget (easy, efficient); every change is an ordinary operation
  in the one history, so Undo takes a key back out (effective, and agents do exactly the same thing).

### The settings panel

- **Top:** the name and kind, then **Find a setting** (Ctrl F). Typing shows every setting whose name or meaning
  matches, from any group, already open; Esc clears it.
- **Essentials:** the settings the kind marks as most used, always open, in its own order — e.g. a text: Text, Size,
  Weight, Colour, X, Y, Scale, Rotation, Opacity; a shape: Shape, Width, Height, Corner radius, Fill, X, Y, Scale,
  Rotation, Opacity.
- **Every other group folded to its name** (▸ Outline, ▸ Timing, ▸ Matte, ▸ Colour, ▸ Depth …). Click a name to open it;
  the panel remembers which groups you opened while you move between layers. No separate "More": a group's rarer
  settings sit at the end of that group.
- **Rule of individuality, unchanged:** a setting that doesn't apply now is absent, never greyed; a group with nothing
  that applies is absent; no heading is said twice.
- **Built from the data:** each kind's settings already carry an importance (most used / sometimes / rarely) and a group;
  the panel is made from that for every kind, never drawn by hand per panel.
- **Jump to a setting:** Ctrl K "Edit Opacity" (or a search hit) opens its group, scrolls to it and puts the cursor in it.
- *Why:* the few settings you use all the time are always in view without scrolling (efficient); every group's name
  is visible at a glance, which tabs would hide (easy); nothing is lost — search finds anything (effective).

### Drawing (until H29)

- **Draw** is a tool in the strip (B), like the Pen. With a drawing layer selected, a stroke paints on it at the
  playhead. With anything else selected, or nothing, the first stroke makes a new drawing layer (one change).
- While Draw is on, the settings panel shows the brush; Move (V) or Esc gives the layer's settings back.
- Frame-by-frame buttons (previous / next / new drawing / hold longer / shorter / onion skin) sit in the timeline
  header while a drawing is selected; the shortcuts are unchanged (Alt + arrows, Alt N, Alt O).
- H29 replaces this with one painting model: paint on any element, kept inside its outline; a "Drawing" is an element
  with paint and no outline; "Draw each frame" is a switch on any painted element. The tool strip and the Brush panel
  are the places it will live.

### + Add

One list, the same everywhere (no per-page lists): Shape, Text, Path (turns the Pen on), Image, Video, Drawing (turns
Draw on), Group, Camera, Rig, and a 3D render when Rostrum3D is installed. A new layer starts at 0 and lasts the
whole composition, as today; you drag its bar to place it. *Why:* a layer that quietly started at the playhead would
vanish when you scrub back, which is confusing (easy).

## Every action is an operation

The screen is built on the same operations agents call through the 2D MCP server; nothing here is screen-only except
screen state (selection, playhead, which groups are open, the search text, the tool).

| On screen | Operation |
|---|---|
| Drag a layer's bar | `layer.shift {by}` — the layer, its keys, drawings and inner layers move together (new) |
| Drop the bar's start on a marker | `layer.shift {to: "#marker"}` — moved so it starts on the marker, and tied to it (new) |
| Drag a bar's end | `layer.trim {start}` / `layer.trim {end}`; dropped on a marker: `"#marker"` ties it (new) |
| Diamond: start / stop animating | `key.add` / `key.clear` |
| Change an animated setting | `value.set {at: playhead}` (adds or changes the key there) |
| Drag a key / pick its ease | `key.set` |
| Shape a curve | `key.handles` |
| Reorder / rename / delete a layer | `layer.arrange` / `item.rename` / `layer.remove` |
| Draw a stroke | `stroke.add` (and `layer.add` + `frame.add` first, in the same change, when needed) |
| + Add | `layer.add` + the kind's settings |

Each drag is one change in the one history, so Undo takes a whole drag back.

## Clicks for common jobs, before and after

Counted as clicks (a drag counts as one; typing a value counts as one click into the box). Before = H27's screen.

| Job | Before | After |
|---|---|---|
| **Add a title and fade it in at 2 s** | + Add, Text, type the words · click the ruler at 2 s · Opacity diamond · type 0 · click the ruler at 2.5 s · type 1 · to change the ease: **Animate page**, click a diamond, Ease, pick one = **12** | + Add, Text, type the words · ruler at 2 s · Opacity diamond · type 0 · ruler at 2.5 s · type 1 · click its diamond on the bar, Ease, pick = **11** — and the bar shows the fade, no page change |
| **Move a logo across from 1 s to 3 s with an ease** | click the logo · ruler 1 s · X diamond · ruler 3 s · drag the logo · **Animate page** · click the key · Ease · pick = **9** | click the logo · ruler 1 s · X diamond · ruler 3 s · drag the logo · click the key on its bar · Ease · pick = **8** |
| **Make a layer appear on a marker** | click the layer · scroll the settings panel to Timing (long) · Timed from marker · pick the marker = **3 + a long scroll**; the layer's timing never shown as a bar | **drag the layer's bar onto the marker's flag = 1** (it snaps, ties, and shows the flag). Or: Find a setting "marker", pick = 2 |
| **Paint** (until H29) | **Draw page** · + Add · Drawing · paint = **3 + strokes** | **Draw tool (B)** · paint = **1 + strokes** (the first stroke makes the drawing) |
| **Export** | Export ↗ · format · Export = **3** | Export ↗ · format · Export = **3** (unchanged: it was already short) |

Pictures of each job before and after: `C:\Users\Sam\.rostrum\waves\results\2d-redesign\h28\`.

## Left for later (not in H28)

- Position as one setting (X and Y keyed together) and X / Y, Width / Height side by side on one line.
- A fade handle on a bar's corner (drag it to fade in or out without touching Opacity).
- A right-click ease menu on a key (one click less than the settings panel).
- Sound and 3D moving to the same settings panel (the kit has it; each app turns it on with one line).
