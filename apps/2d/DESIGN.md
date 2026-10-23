# Rostrum2D — how the screen is laid out and how you work in it

*Team Hem, H28, 2026-10-22. Written for Sam. The direction was decided by the manager (docs/PLAN.md › Decided,
"Rostrum2D's screen and workflow") and Sam added three points while using the app (drag feel; select first, then act;
design from the workflows); this is the detailed design. The yardstick is Sam's 3E's: **effective** (you can make
what you want), **efficient** (few steps, no detours), **easy** (you can see what to do).*

## What was wrong

- **Three pages (Design / Draw / Animate) split one job into three places.** Design was only "add things"; to make
  anything move you switched page, then switched back to change how it looks. Every switch cost a click and hid half
  of what you were working on.
- **When a layer shows was hidden.** Timing was two number boxes deep in a long settings list.
- **The settings panel was one long scroll** (a text layer: 23 settings on screen, 18 more behind More), with headings
  said twice.
- **The top bar ran out of room**: the change count, Undo and Redo slid behind the page switcher on Sam's screen.
- **Dragging a layer, the box moved first and the picture caught up after.**
- **Things were made backwards**: an empty Group from + Add, then layers dragged into it. People select first, then act.
- **The screen was laid out from the features, not from the work.** This version starts from the jobs people do
  (below) and gives each moment only what it needs.

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

## Start from the work: the jobs people do in 2D

Before deciding where anything goes, here is what people actually do, step by step, from an empty project to an
export. For each step: what the person is thinking, what they need on screen at that moment, and what is only in the
way. The screen is then designed so each moment shows what that step needs: the rule of individuality, applied to the
whole screen and not just the settings panel.

### F1 · A title or type animation ("Spring launch": the letters rise in, the title leaves on the beat)

| Step | Thinking | Needs on screen | Doesn't need |
|---|---|---|---|
| 1. New project | "What size, how long?" | The composition's size, frame rate, length, background | Layer rows, brush, keys |
| 2. Add the text, type it | "The words and how they look" | The text on the canvas; text essentials: words, font, size, weight, colour | Timing, other layers, effects |
| 3. Place it | "Where on the frame?" | Drag on the canvas, snapping to the centre and to other layers; X / Y | The timeline rows |
| 4. Make it come in | "How, when, how fast?" | Playhead and ruler; the diamond beside Y and Opacity; Letter delay; its keys on its bar | Font features, colour, other layers' settings |
| 5. Tune the feel | "Too stiff, softer landing" | The key selected → its ease; the curve if needed; play the stretch again | Every other setting |
| 6. Time it | "It leaves on the 'out' marker" | The layer's bar, the markers on the ruler, snapping | The settings panel |
| 7. Watch | "Does it feel right?" | A big canvas and Play (looping) | Panels |
| 8. Export | "An MP4 for the edit" | The Export panel | Everything else |

### F2 · A logo reveal (the strokes draw on one after another, the fill fades in, a glow, the logo settles)

| Step | Thinking | Needs on screen | Doesn't need |
|---|---|---|---|
| 1. Import the logo (SVG / PDF / Figma) | "Bring in the real artwork" | The Import panel; the logo lands as one group | Timeline detail |
| 2. Look at its parts | "Which piece is which?" | The group opened in the layers list; click a piece on the canvas to find it | The settings of every part at once |
| 3. Draw the strokes on | "All outlines draw on together" | **Select the four outlines**, one diamond on Trim end for all of them, two values | Keying each one by hand |
| 4. Stagger them | "One after the other" | Their bars one above the other; drag a bar (its keys go with it), or several together | Typing times |
| 5. Fill fades in, add a glow | "The fill comes after the lines" | **Select the fill shapes → add Glow** (to each); Opacity keys | The effect list of every layer |
| 6. Settle | "Overshoot a little and land" | Scale keys and a springy ease on the last key | — |
| 7. Watch, export | as F1 | | |

### F3 · UI or product animation (app screens, cards sliding in, a cursor taps, a phone from Rostrum3D)

| Step | Thinking | Needs on screen | Doesn't need |
|---|---|---|---|
| 1. Bring the design in | "Use the real screens" | Import (Figma / PSD / SVG), or shapes and text | — |
| 2. Lay out the cards | "Neat, even gaps" | **Select the cards → Align, Distribute**, or wrap them in an auto-layout row | Typing positions one by one |
| 3. Slide them in, one by one | "A cascade: quick, then soft" | Select all cards → one X key on all; drag their bars apart; one ease for all | Opening every layer |
| 4. A cursor taps a button | "Move there, press, release" | The cursor's position keys; its path on the canvas; a quick scale dip | The other layers |
| 5. The phone from 3D | "The 3D render sits in this" | + Add › 3D render; pick the item | 3D's own controls |
| 6. Watch, export | | | |

### F4 · A character with a rig and lip sync

| Step | Thinking | Needs on screen | Doesn't need |
|---|---|---|---|
| 1. Import the parts (PSD) | "Head, body, arms, mouths as layers" | Import; the parts as layers | — |
| 2. Make a rig | "These parts are one puppet" | **Select the parts → Make rig** | An empty rig to drag parts into |
| 3. Bones, bind the parts | "Shoulder → elbow → hand" | A Bone tool that appears **only while a rig is selected**; the bones drawn on the canvas | Text, effects, timeline rows |
| 4. Mouths as a swap set | "One mouth showing at a time" | **Select the mouth drawings → Make swap set** | — |
| 5. Lip sync | "Match the voice line" | On the swap set: "Lip sync from…" (a voice from Sound, or an audio file) | — |
| 6. Pose over time | "Arm up on the beat" | Drag the hand (IK) on the canvas at the playhead; poses saved and applied | Scrolling the settings panel |
| 7. Watch, export | | | |

### F5 · Hand-drawn frame by frame

| Step | Thinking | Needs on screen | Doesn't need |
|---|---|---|---|
| 1. New project, 24 fps, on twos | "Classic timing" | Composition settings; Steps | — |
| 2. Pick Draw, draw the first drawing | "Just draw" | **A big canvas**; brush size, colour, eraser close at hand | Layer settings, other rows, keys |
| 3. Next drawing, onion skin on | "See the last one faintly" | New drawing (Alt N), onion skin, the drawing's frames as marks on its bar | The full timeline |
| 4. Flip and play | "Does it move?" | Previous / next drawing; play a loop | Panels |
| 5. Hold longer / shorter | "Slow the anticipation" | Hold buttons; the frame marks | — |
| 6. A colour layer under the lines | "Lines on top, colour below" | A second drawing under the first; both in the layers list | — |
| 7. Export (GIF / MP4) | | | |

### F6 · A painted or textured illustration that then moves

| Step | Thinking | Needs on screen | Doesn't need |
|---|---|---|---|
| 1. A painted background in depths | "Far hills, mid trees, near grass" | + Add › Painted background (far / mid / near layers at camera depths) | — |
| 2. Paint each depth | "Rough it in, then detail" | Big canvas, **zoom and pan**, the brush; the layer stack | Keys, timing |
| 3. Texture on shapes (H29) | "Grain inside this shape" | Paint on any element, kept inside its outline | — |
| 4. Camera move | "A slow push in; depth does the parallax" | The camera selected: its frame on the canvas, position / zoom keys | Every other layer's settings |
| 5. Small life (smoke, a bird) | "Little moves" | Keys on those elements | — |
| 6. Watch, export | | | |

### F7 · Timing a piece to music markers from RostrumSound

| Step | Thinking | Needs on screen | Doesn't need |
|---|---|---|---|
| 1. The music has markers ("drop", "verse 2") | "Hit these moments" | The project's markers on the ruler, by name | — |
| 2. Hear it | "Where is the beat?" | **The project's music playing with the picture** (through Sound's engine) and its waveform under the ruler — *missing today* | — |
| 3. Put layers on the moments | "The logo lands on the drop" | Drag the layer's bar onto the marker: it snaps and ties | Typing times |
| 4. The music changes | "Sound moved the drop" | The tied layers follow by themselves | Re-timing by hand |
| 5. Hand back to Sound | "Music on the moments: a note on a landing, a rise into it" | Export › Motion samples | — |

### F8 · An agent builds a piece while a person tweaks it

| Step | Thinking | Needs on screen | Doesn't need |
|---|---|---|---|
| 1. Ask the agent (in the AI app) | "Make a 10 s launch title" | The screen updating live as the agent works | — |
| 2. Watch | "What did it just do?" | Who did what ("Claude: add title") in the top bar; the changed layers marked briefly | Losing my selection or playhead to the agent |
| 3. Tweak | "Warmer colour, later fade" | Normal editing; the agent's next run never wipes my change | — |
| 4. Take back my own step | "Not that" | Ctrl Z undoes **my** changes only | — |
| 5. Review the agent's changes | "Show me everything it changed" | A history list by who, one click away — *later* | — |

## What the flows tell us

1. **Two kinds of moments.** *Timing moments* (F1, F2, F3, F7: when and how things move) need the layer rows, bars,
   keys and the settings with their diamonds, together. *Canvas moments* (F4 posing, F5 drawing, F6 painting) need the
   biggest possible picture and the tool's own controls, and only the timing of the one thing being worked on.
2. **The selection is the input for almost every action** (F2 steps 3 and 5, F3 steps 2–3, F4 steps 2 and 4). Many
   layers are keyed, aligned, grouped or masked at once. So selecting several things must be easy everywhere, and every
   action that relates layers to each other takes the selection ("Select first, then act", below).
3. **Time is placed by dragging, not typed** (F1 step 6, F2 step 4, F3 step 3, F7 step 3): bars and keys, snapping to
   markers.
4. **The playhead and Play are needed in every flow**, even while drawing; the full layer list is not.
5. **Tools change what the mouse does and what the panels show** (Pen: points; Draw: brush; Bone: bones). A tool's
   controls belong with the tool, not on a page.
6. **Some controls belong to one kind of thing** (the Bone tool with a rig, the camera's frame with a camera, frame
   buttons with a drawing). They appear with that selection and nowhere else.
7. **Agents and people share the screen** (F8): an agent's change must show without taking anything from the person
   (selection, playhead, scroll, open groups).

## How the screen follows the flows

Everything on screen sits in one of five tiers. An element earns its tier from the flows above, not from habit.

| Tier | What | Why (flows) |
|---|---|---|
| **Always** | The canvas (the picture as it will export) · the top bar (File, project, what just happened, Undo / Redo, + Add, Import, Export, search, Help) · the timeline's header and ruler (Play, the time, preview size, the markers) | Every flow ends in a picture; every flow plays and watches (finding 4); project-wide actions are needed at any moment |
| **With a selection** | The settings panel's content (one layer, or the shared settings of several) · the selected layers' bars highlighted · handles on the canvas · the **action bar** of that selection (Group, Mask, Align…: only what applies) · the controls of that kind only: a drawing's frame buttons and onion skin, a path's points, a camera's frame, (later) a rig's Bone tool, a swap set's Lip sync | Findings 2 and 6. Nothing selected → the settings panel shows the composition (F1 step 1, F5 step 1) |
| **With a tool** | Move (V): handles, the action bar · Pen (P): points and the "click for a corner, drag for a curve" hint · Draw (B): the brush in the settings panel, the frames, onion skin · each tool remembers the timeline height it was last used with | Finding 5. Drawing gets a big canvas without losing Play (F5) |
| **One click away** | + Add, Import, Export, Problems, Help · Ctrl K (every command, every setting) · Find a setting · the folded setting groups · Curves · the right-click menu on a selection or a layer row · Add marker | Used at a moment, not all the time |
| **Gone** | The Design / Draw / Animate pages · the separate Layers panel (its list now lives in the timeline beside each layer's bar) · Group, Rig and other empty containers in + Add · the More row | Pages split one job into three places; two lists of the same layers; empty containers are made backwards |

### The timeline has two heights, and each tool remembers its own

- **Full:** every layer's row and bar, the layers list. For timing moments.
- **Compact:** the header, the ruler with its markers, and **only the selected layer's row** (its bar, its keys, a
  drawing's frames). Its name is a menu of all the layers, so another layer is one click away. For canvas moments.
- Switch with the button at the right end of the timeline's header, or drag its top edge. **Move remembers its own
  height, Draw its own** (Draw starts compact). Picking Draw gives the canvas the room; going back to Move brings the
  rows back. No extra click, and nothing moves that you didn't ask for.

### Where the flows pull apart, and how I chose

| Pull | Choice | Why |
|---|---|---|
| Timing wants every row; drawing and painting want the whole screen for the canvas | Two timeline heights, remembered per tool | Each moment gets what it needs without a page; Play and the playhead stay in both (finding 4) |
| Designers and painters think in a layer stack; animators think in time | One list: the layers list *is* the timeline's name column; compact mode keeps the stack one click away (its name menu) | Two lists of the same layers meant reading twice; now stack order and bars agree row by row |
| Tool settings next to the canvas (fast) or in the settings panel (one place) | The settings panel shows the active tool's settings (the brush while drawing); quick brush size and colour on the canvas come with H29 painting | One place to look now; H29 adds the quick reach painters need |
| Click on a grouped logo: the piece or the whole logo? | Click selects the outermost group (move the whole logo); double-click goes one level in; Ctrl click goes straight to the piece under the pointer (as Figma does) | F2 and F3 move whole groups most of the time; the piece is one more click |
| Shift or Ctrl to add to a selection | On the canvas Shift click adds / removes (as Figma); in the layers list Ctrl click adds / removes and Shift click selects a range (as every list on Windows) | Each place keeps the habit people already have there |
| An agent editing live vs a person working | The agent's change shows at once but never moves the person's selection, playhead, scroll or open groups; the top bar names who did it | F8: watching must not cost the person their place |

## Select first, then act

**The rule (Sam):** every action that relates layers to each other starts from the selection. You select the
things, then act on them; the action takes the selection as its input. Nothing is made empty to be filled
afterwards. *Why:* it is how people think ("these go together", "this shape cuts those"), it saves the drag-into-a-
container step, and the result is right the first time (effective, efficient, easy).

**Where an action lives** (all four read one list of actions, each with "valid when the selection is …" and an
importance, so they always agree and nothing is greyed out):
1. the **action bar**: a small bar that appears just under the selection on the canvas, showing only the actions this
   selection allows, most used first (Boolean shows only with 2+ shapes selected);
2. the **right-click menu** on the selection (canvas or layers list): the same actions, all of them;
3. **Ctrl K**: the same actions, by name;
4. a **shortcut** for the common ones.

**One operation per action, taking the selected ids**, so an agent calls exactly what the screen calls.

| Action | Select | Then | Operation | H28 |
|---|---|---|---|---|
| **Group** | 2+ layers | Ctrl G · Group. A group sized to them; every layer stays where it was | `group.make {ids}` | build |
| **Ungroup** | a group | Ctrl Shift G · Ungroup. The children go back where they were on screen | `group.release {ids}` | build |
| **Mask with a layer** | the shape that cuts + the layers to cut | Mask (with top layer). They become a group; the layers show only inside the shape | `mask.make {cutter, targets, mode}` | build |
| **Track matte** (shape / outside / brightness / darkness) | the same | Mask › Use its brightness … (the mode) | `mask.make {mode: alpha·alphaInverted·luma·lumaInverted}` | build |
| **Release a mask** | the masked layers | Release mask | `mask.release {ids}` | build |
| **Boolean shapes** | 2+ shapes or paths | Union · Subtract · Intersect · Exclude | `shape.boolean {ids, op}` | build (baked); the live, still-editable boolean group with **Flatten** is later (it needs the engine to combine shapes every frame) |
| **Clip to box** | layers | Clip. A group that hides what is outside its box | `group.make {ids, as: "clip"}` | build |
| **Auto layout** | layers | Auto layout. A row that spaces them evenly | `group.make {ids, as: "layout"}` | build |
| **Swap set** | the drawings or pictures to swap | Make swap set. One of them shows at a time, keyed | `group.make {ids, as: "swap"}` | build |
| **Align** | 2+ layers (or 1: to the composition) | Left · Centre · Right · Top · Middle · Bottom | `layer.align {ids, edge, to}` | build |
| **Distribute** | 3+ layers | Even gaps across · down | `layer.distribute {ids, axis}` | build |
| **Match size** | 2+ layers; the first picked is the size to match | Match width · height · both | `layer.match_size {ids, to, dims}` | build |
| **Copy / paste style** | a layer → Copy style; then other layers → Paste style | Fill, outline, opacity, blend, colour and effects copied onto each | `style.apply {from, ids}` | build |
| **Effects** | layers | Add effect › Glow (each gets its own) | `effect.add` on several targets | build |
| **Keys on several** | layers | One diamond click keys that setting on all; one ease for all selected keys | `key.add` / `value.set` / `key.set` on several targets | build (settings panel) |
| **Lock / hide** | layers | Lock · Hide (also the lock and eye on each layer row) | `layer.lock` / `layer.hide {ids, on}` | build |
| **Make rig** | the parts | Make rig. A rig holding them, all staying where they are | `rig.make {ids}` | build if small, else H30 |
| **Parent (follow another layer)** | the layers + the one to follow (picked last) | Follow. They move, turn and scale with it without being grouped | `layer.link {ids, to}` | later (needs the engine to carry a parent that is not a group) |
| **Bones** | a rig | the Bone tool appears; drag from joint to joint | `bone.add` | later (H30, the character tools) |
| **Lip sync** | a swap set | Lip sync from… a voice | `lipsync.apply` | later (H30) |

+ Add only makes **new content**: Shape, Text, Path (the Pen), Image, Video, Drawing, Camera, 3D render, and later
Painted background. Group and Rig are gone from it.

## Everyday things people expect (from Figma, After Effects, Rive)

| Expectation | What Rostrum2D does | When |
|---|---|---|
| **Select, multi-select** | Click; Shift click adds / removes on the canvas; Ctrl click / Shift click in the layers list; drag a box on empty canvas; Ctrl A all; Esc clears. Click a group selects the group; double-click goes in; Ctrl click picks the piece under the pointer. Ctrl K, the menus and the settings panel act on **every** selected layer | H28 |
| **Settings of several** | The settings panel shows what the selected layers share; a value that differs says "Mixed"; a change sets it on all, as one change | H28 |
| **Group / ungroup** | Select → Ctrl G; Ctrl Shift G | H28 |
| **Align and distribute** | In the action bar, right-click and Ctrl K | H28 |
| **Snapping and guides** | Layer bars and keys snap to markers and the playhead. On the canvas: a dragged layer snaps to the frame's centre and edges and to other layers' edges and centres, with a thin line showing what it snapped to; Ctrl while dragging turns snapping off | H28 |
| **Copy / paste / duplicate** | Ctrl D duplicates (with keys); Ctrl C / Ctrl X / Ctrl V copy, cut and paste layers (in place, also into another project); Alt drag drags a copy | H28 |
| **Nudge with the arrow keys** | 1 px; Shift 10 px; every selected layer; one change per key press | H28 |
| **Zoom and pan the canvas** | Ctrl wheel zooms at the pointer, Space drag or middle drag pans, Ctrl 0 fits, Ctrl 1 shows 100 %; the zoom shows in the canvas corner. On Sam's screen a 1080p frame is fitted at about half size, so this is needed for any detail | H28 |
| **Right-click menus** | On a layer row, on the selection on the canvas, on a key (ease) — all from the one action list | layers and canvas: H28 · keys: H29 |
| **Keyboard shortcuts** | V Move, P Pen, B Draw, Space play, Ctrl Z / Ctrl Shift Z, Ctrl D, Delete, F2 rename, Ctrl ] / [ order, Ctrl G / Ctrl Shift G, arrows nudge, Ctrl F find a setting, Ctrl K everything, Alt + arrows / Alt N / Alt O frames. A list of them in Help | list in Help: H29 |
| **Renaming** | Double-click a name, or F2 | now |
| **Locking and hiding** | A lock and an eye on each layer row (on hover, or always when on); hidden layers don't export | H28 |
| **Undo of every gesture as one step** | Every drag (move, resize, turn, a point, a key, a bar), every action, every nudge is one change in the person's history; an agent's changes are in the agent's own | now (kept) |
| **Drag feel and lag** | The box and the picture move together (below); Shift while dragging keeps the move straight, Alt resizes from the centre | H28 |
| **Make things where you want them** | Tools in the strip: Rectangle (R), Ellipse (O), Text (T). Drag on the canvas to draw a shape at that place and size; with Text, click (or drag a box) and type straight on the canvas; double-click any text to edit it there. + Add stays for pictures, video, camera and the rest | H28 if time, else H29 |
| **Clicks go to what is painted** | A click picks the layer whose picture is under the pointer: an empty group or the empty part of a drawing never catches it (it was catching every click) | H28 |

## Drag feel: the box and the picture move as one

**What Sam saw:** dragging a layer, the selection box moved first and the picture caught up afterwards. The box was
drawn by the screen at once; the picture waits for the engine's next frame. They came apart.

**The fix, at the base:** every picture the engine sends back carries the document state and time it was drawn
from. Everything the screen draws over the picture (the box, handles, path points, other selected outlines, onion
skin) is drawn from **that same state**, not from the newest one. So the box and the picture can never disagree: they
always show the same moment. While a drag is going on, the picture is drawn at half size, so new pictures come back
faster and the drag stays close to the pointer; on release one full-size picture follows. Pressing and hit-testing
still use the newest document, because that is what the person is acting on. The same holds for every direct drag:
resize, turn, path points and handles, keys and bars on the timeline (the timeline updates at once; the picture
follows without anything on it jumping). Measured lag before and after: `C:\Users\Sam\.rostrum\waves\results\2d-redesign\h28\drag-feel\`.

## The screen

```
┌ Rostrum2D  File  [project •]                  what just happened · 12 changes  ↶ ↷  + Add  Import  ↗  [Search Ctrl K]  ? ┐
├───────────────────────────────────────────────────────────────────────────┬─────────────────────────────┤
│ CANVAS                                                                    │ SETTINGS                    │
│ ┌────────┐                                                                │ title · Text                │
│ │ Move V │        ┌──────────────────────┐                                │ [ Find a setting   Ctrl F ] │
│ │ Pen  P │        │    Spring launch     │  ← the selection's box          │ Text      Spring launch     │
│ │ Draw B │        └──────────────────────┘                                │ Size      88 px             │
│ └────────┘        [ Group  Align ▾  Mask  … ]  ← action bar (only what      │ Colour    ■ #FFFFFF          │
│                                               this selection allows)      │ X         960 px       ◇    │
│                                                                           │ Opacity   1.00         ◆    │
│                                                                           │ ▸ Text  ▸ Letters  ▸ Timing  │
├──────────────────────── drag this edge, or use ⇕ at the right ─────────────┴─────────────────────────────┤
│ ▶ 2.48 s  frame 62   Preview size  Full Half Quarter   Add marker   Keys | Curves              ⇕ compact │
│ LAYERS                    │0s      1s      2s  ▼drop    3s      4s      5s                               │
│ ▾ ▢ lockup          🔒 👁 │████████████████████████████████████████████████████████████████             │
│     ▢ rule                │          ███████◆███████◆██████████████████████████████████████             │
│ ▸ T title                 │              ███◆██◆████████████████████████                                 │
│   ▢ card                  │████████████████████████████████████████████████████████████████             │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Regions, and why

1. **Top bar** (always): File and the project on the left; on the right what just happened, the change count, Undo /
   Redo, **+ Add**, **Import**, **Export**, search (Ctrl K) and Help. No page switch.
   *Why:* project-wide actions, needed in every flow, in one fixed row and order (efficient: always in the same
   place). When the window is narrow, things give way in a fixed order and never slide under each other: first the
   "what just happened" message shortens (hover shows all of it), then the project name, then the search box becomes
   its icon. The change count, Undo, Redo, Add, Import, Export and Help never shrink.
2. **Canvas** (always): the frame at the playhead, as it will export. The **tool strip** floats at its top-left (Move,
   Pen, Draw). Under the selection sits its **action bar**. Export, Import and Problems open as small panels on the
   canvas's right edge.
   *Why:* every flow ends in this picture; tools and actions sit where the hand already is (easy), and appear only
   when they can be used (rule of individuality).
3. **Settings panel** (right; with a selection, else the composition; with Draw, the brush): see below.
4. **Timeline** (bottom, full width; the header and ruler always, the rows full or compact): play, the time, preview
   size, Add marker, Keys / Curves, a drawing's frame buttons when a drawing is selected, the compact switch; the ruler
   with the project's markers; **one row per layer** — its name on the left (this *is* the layers list, with a lock
   and an eye on each row) and its **bar** on the right.
   *Why:* time is placed by dragging (finding 3), and the layer stack and the bars agree row by row. On a 16:9 picture
   the canvas is limited by height, not width, so the old left panel gave the picture nothing.

### The layer rows (one list for layers and time)

- **Name side:** the layer's icon and name, indented inside its group; the arrow folds a group or opens a layer's rows.
  Click selects; Ctrl click adds or removes one; Shift click selects a range. Double-click (or F2) renames. Drag a name up or down to reorder, or into a group. Right-click: the
  menu of the selection (the same actions as the action bar and Ctrl K). A lock and an eye on each row (shown on
  hover, or always while on).
- **Bar side:** a bar from when the layer appears to when it goes. **Drag the bar** to move the layer in time — its
  keys and drawings move with it (with several layers selected, all their bars move together). **Drag an end** to change when it starts or ends (keys stay where they are). Near a
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
- **Several layers selected:** the panel shows the settings they all have; a value that differs says "Mixed";
  changing it (or clicking its diamond) sets it on every one, as one change. Above the settings sits the selection's
  action bar (Group, Align, Mask … only what applies).
- **Nothing selected:** the composition's settings (size, frame rate, length, background, Steps).
- **Jump to a setting:** Ctrl K "Edit Opacity" (or a search hit) opens its group, scrolls to it and puts the cursor in it.
- *Why:* the few settings you use all the time are always in view without scrolling (efficient); every group's name
  is visible at a glance, which tabs would hide (easy); nothing is lost — search finds anything (effective).

### Drawing (until H29)

- **Draw** is a tool in the strip (B), like the Pen. With a drawing layer selected, a stroke paints on it at the
  playhead. With anything else selected, or nothing, the first stroke makes a new drawing layer (one change).
- While Draw is on, the settings panel shows the brush, and the timeline goes to Draw's own height (compact at first:
  the drawing's row with its frames). Move (V) or Esc gives the layer's settings and the rows back.
- Frame-by-frame buttons (previous / next / new drawing / hold longer / shorter / onion skin) sit in the timeline
  header while a drawing is selected; the shortcuts are unchanged (Alt + arrows, Alt N, Alt O).
- H29 replaces this with one painting model: paint on any element, kept inside its outline; a "Drawing" is an element
  with paint and no outline; "Draw each frame" is a switch on any painted element. The tool strip and the Brush panel
  are the places it will live.

### + Add

Only **new content**: Shape, Text, Path (turns the Pen on), Image, Video, Drawing (turns Draw on), Camera, and a 3D
render when Rostrum3D is installed (later: Painted background). Groups, rigs, swap sets, clips and layouts are made
from a selection (above), never added empty. A new layer starts at 0 and lasts the whole composition; you drag its
bar to place it. *Why:* a layer that quietly started at the playhead would vanish when you scrub back.

## Every action is an operation

The screen is built on the same operations agents call through the 2D MCP server; nothing here is screen-only except
screen state (selection, playhead, tool, open groups, the search text, the timeline's height).

| On screen | Operation |
|---|---|
| Drag a layer's bar (or several selected bars) | `layer.shift {by}` — the layer, its keys, drawings and inner layers move together |
| Drop the bar's start on a marker | `layer.shift {to: "#marker"}` — moved so it starts on the marker, and tied to it |
| Drag a bar's end | `layer.trim {start}` / `{end}`; dropped on a marker: `"#marker"` ties it |
| Diamond: start / stop animating (one layer or several) | `key.add` / `key.clear` |
| Change an animated setting | `value.set {at: playhead}` (adds or changes the key there) |
| Drag a key / pick its ease | `key.set` |
| Shape a curve | `key.handles` |
| Reorder / rename / delete / duplicate | `layer.arrange` / `item.rename` / `layer.remove` / `layer.duplicate` |
| Group / ungroup / clip / auto layout / swap set | `group.make {ids, as}` / `group.release` |
| Mask, track matte, release | `mask.make {cutter, targets, mode}` / `mask.release` |
| Boolean | `shape.boolean {ids, op}` |
| Align / distribute / match size | `layer.align` / `layer.distribute` / `layer.match_size` |
| Paste style | `style.apply {from, ids}` |
| Lock / hide | `layer.lock` / `layer.hide` |
| Nudge | `value.set` x / y (at the playhead when animated) |
| Draw a stroke | `stroke.add` (and `layer.add` + `frame.add` first, in the same change, when needed) |
| + Add | `layer.add` + the kind's settings |

Each drag and each action is one change in the one history, so Undo takes it back whole.

## Clicks and screen changes per flow, before and after

Counted along the shortest path a person would take. A click, a drag, a key press or typing one value each count as
one. A *screen change* is a page switch or a panel replacing what you were looking at. Before = H27's screen; after =
H28 as built. Every step of every flow is pictured in `C:\Users\Sam\.rostrum\waves\results\2d-redesign\h28\flows\`.

| Flow | Before (clicks · screen changes) | After H28 | What changed |
|---|---|---|---|
| **F1 Title** | 24 · 1 page switch, 2 long scrolls | 23 · none | Letters and Timing are named groups (no scroll); the ease is on the key on the bar; the exit lands on the marker by dragging the bar's end |
| **F2 Logo reveal** | ~49 · 1 page switch; the glow can't be added on screen | ~34 · none | Four outlines selected and keyed at once; staggered by dragging bars; Add effect on the selection |
| **F3 UI cards** | ~51 · 1 page switch; no align | ~37 · none | Align / Distribute; one key on three cards; bars dragged apart |
| **F4 Rig and lip sync** | Import 4, then rig, bones and lip sync **not possible on screen** | Import 4, select the parts, Make rig; bones and lip sync still agent-only (H30) | Make rig from a selection |
| **F5 Frame by frame** | 23 · 2 page switches | 22 · 2 tool switches; the timeline goes compact by itself while drawing | No page; the first stroke makes the drawing |
| **F6 Painted, then moves** | Painted background only by an agent; no zoom | The same in H28 | H29: + Add › Painted background, zoom and pan, paint on any element |
| **F7 Timing to music** | 12 + 4 scrolls, and the keys jump when a layer is tied to a marker | 4 (drag each bar onto its marker; keys keep their place) | Tying by dragging; you still can't hear the music in 2D (later) |
| **F8 Agent and person** | The same: the agent's change shows; the top bar names who | The same | A history list by who is later |

### The five jobs of the brief

| Job | Before | After |
|---|---|---|
| **Add a title and fade it in at 2 s** | + Add, Text, type · ruler 2 s · Opacity diamond · type 0 · ruler 2.5 s · type 1 · **Animate page**, click a diamond, Ease, pick = **12** | the same, then the diamond on the bar, Ease, pick = **11**; no page change, the bar shows the fade |
| **Move a logo across from 1 s to 3 s with an ease** | click the logo · ruler 1 s · X diamond · ruler 3 s · drag the logo · **Animate page** · click the key · Ease · pick = **9** | the same without the page = **8** |
| **Make a layer appear on a marker** | click the layer · scroll the settings to Timing · Timed from marker · pick = **3 + a long scroll** (and its keys jump) | **drag its bar onto the marker = 1** (it snaps, ties, keys keep their place) |
| **Paint** (until H29) | **Draw page** · + Add · Drawing · paint = **3 + strokes** | **Draw (B)** · paint = **1 + strokes** |
| **Export** | Export ↗ · format · Export = **3** | **3** (it was already short) |

## Built in H28, and left for later

**Order of work in H28** (the manager's order, after the fresh-eyes check
`C:\Users\Sam\.rostrum\waves\results\2d-redesign\audit\FINDINGS.md`): the design; the core structure (one workspace,
the timeline as the layers list with bars and two heights, animating in place, the settings panel, the top bar, the
tool strip); three bugs (a timeline row that wouldn't open because the shared code and the app used the same internal
name; Ctrl K acting on the first selected layer only; empty groups and drawings catching every click); drag feel;
select first, then act, with real multi-select; the everyday keys; zoom and pan; snapping, guides, align and
distribute; creation tools. Whatever doesn't fit is listed in the H28 report.

**H29 (painting, and what it needs):** one painting model (paint on any element); quick brush size and colour on the
canvas; + Add › Painted background and "Set depth" on selected drawings; a key's right-click ease menu, selecting
several keys and moving or easing them together; the shortcut list in Help; sizes by name for a new composition
(16:9, 4K, 9:16, 1:1, 4:5); Opacity in %, weights by name; a font list.

**Later:** the character on screen (H30): Bone tool on a selected rig, attach parts, IK drag, poses, lip sync and
blinks on a swap set; **hearing the project's music in 2D** while playing and scrubbing, through Sound's engine (the
one-audio-engine rule), with its waveform under the ruler; the live boolean group with Flatten; parenting (follow
another layer); a history list by who; a fade handle on a bar's corner; Sound and Rostrum3D moving to the same
settings panel (the kit has it; each app turns it on with one line).
