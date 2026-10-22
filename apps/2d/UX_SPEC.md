# Rostrum2D: how people use it (UX spec)

*Written 2026-10-22 by the product designer for Rostrum2D, for Sam and for the teams who build it. Design only: no
app code. Inputs: `docs/PLAN.md` (Rostrum2D's feature list and › Decided), `apps/2d/STATUS.md`, Team Hem's H28 draft
(`C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\apps\2d\DESIGN.md` and its code on `team/hem`), the fresh-eyes check
(`C:\Users\Sam\.rostrum\waves\results\2d-redesign\audit\FINDINGS.md`), the experiment's screen rules
(`docs/GUI_DESIGN.md` at tag `experiment-final` in `C:\Users\Sam\Documents\CODE\OLD-EXPERIMENT`), and how After Effects,
Rive, Jitter, Cavalry, Figma, Apple Motion, Toon Boom Harmony, Moho and Procreate Dreams handle each job.*

*A version with drawn wireframes, easier to read: `C:\Users\Sam\.rostrum\waves\results\2d-redesign\spec\UX_SPEC.html`.*

> **S30 shared-spec changes (2026-10-22, Team Sam).** The shared interaction spec
> `C:\Users\Sam\Documents\CODE\Rostrum\shared\gui-kit\INTERACTION.md` sets one way of working for every Rostrum app
> and wins where this spec differs. The edits it made here are marked **(S30)** in place. Where a drawing or a sentence
> was not changed, read it with these in mind:
>
> 1. **Scene**, not comp, on every screen and in every guide (`comp.*` operation names are kept).
> 2. **+ Add** replaces "+ Place". "Place a file…" is now **Add from a file…** (Ctrl+I).
> 3. The top bar keeps **"Saved · N changes"**: it is never cut, and a click opens History.
> 4. The context bar's ⋯ no longer holds Duplicate or Delete. Those are keys, and they are in the right-click menu.
> 5. **Selecting in the timeline:**
>    - keys follow the list rule: Ctrl+click adds, Shift+click picks the run;
>    - on the canvas, Shift+box adds and Ctrl+box picks the deepest pieces.
> 6. **Keys renamed:**
>    - **A** (not U) shows the animated settings;
>    - **F** fits the selection (Shift+2 still works).
> 7. **Arrow keys:**
>    - **Alt+arrows** are a fine nudge (0.1 px);
>    - the previous / next drawing is `,` / `.`;
>    - hold longer / shorter is **= / −**.
> 8. **The time range:**
>    - "Play range" is now the **time range**, set on the ruler's top band;
>    - **⟳ Loop is Shift+L**;
>    - dragging on the time scale scrubs.
> 9. **History** opens as a **sheet in the right column**, in the settings panel's place.
> 10. **Help keys:** F1 opens Guides, Ctrl+/ the key list. Ctrl+, opens **Preferences** in a dialog.
> 11. **New file keys:**
>     - Ctrl+Shift+S makes a separate copy (**Duplicate**);
>     - Ctrl+Q quits;
>     - F6 moves focus to the next area;
>     - Shift+Space plays from the selection's start;
>     - Alt+M / Alt+Shift+M go to the next / previous marker.
> 12. **Agents:**
>     - an agent's change is outlined for **1 s**;
>     - the menu item is **Copy for an agent**.
> 13. **Markers:**
>     - shared markers are **solid with a small chain**, this scene's own are **hollow**;
>     - M's name field has a **Shared** switch.
> 14. **Settings panel:**
>     - mixed kinds get a narrowing line per kind ("2 texts ›");
>     - the last line says who changed it last.
> 15. Sam's window size is **1646 × 900**.

## The yardstick: the 3E's

Every interaction below is judged by three questions, in this order:

- **Effective:** does it get the person exactly what they want, at the level of an Apple launch film, a Pinkman.TV
  short or Fortiche's 2D effects? A shortcut that caps quality fails here first.
- **Efficient:** is it the fewest steps, with no detours, no retyping, and the result visible while you work?
- **Easy:** can a first-day person see what to do without a manual, with nothing to remember and every mistake one
  Undo away?

When the three pull apart, effective wins, then efficient, then easy, but the design keeps looking for the version
that satisfies all three.

## The rules this design follows (binding)

1. **Rule of individuality.** Each place shows only what you can use right now, most important first. Nothing is
   greyed out: if it can't be used, it isn't there.
2. **Select first, then act.** You pick the things, then say what to do with them. Nothing is made empty and filled
   afterwards.
3. **One operation per action.** Every click, drag and key press is an operation an agent can call too, recorded in
   one history.
4. **Tools, not taste.** We ship tools and how-to guides. No look presets, no finished pieces, no story templates.
5. **Preview equals export.** The canvas is the export at the playhead. Nothing is preview-only.

## The ten decisions that matter most

| # | Decision | Why (in a sentence) |
|---|---|---|
| 1 | **One workspace.** Canvas in the middle, settings on the right, a full-width timeline at the bottom that *is* the layers list (one row per layer: name on the left, its bar on the right). No Design / Draw / Animate pages. *(Keeps Hem's H28.)* | Motion design is shape and time at once; pages split one job into three places. |
| 2 | **One context bar at a fixed place, the top of the canvas.** It shows exactly what you can do right now: the selection's actions (Group, Mask, Align …) with the Move tool, or the active tool's few options (brush size, colour) with any other tool. *(Changes Hem's bar that floated under the selection.)* | One place to look; it never covers the artwork, never jumps while the selection moves, and is never pushed off-screen. |
| 3 | **Making things lives in one place: the tool strip** on the canvas's left edge (Move, Shape, Pen, Text, Paint, and **+ Add** for files and everything else *(S30: was "+ Place")*). Import and + Add become one door, + Add, which also takes a dropped file. The top bar keeps only project-wide things, so it can never overlap. *(Changes Hem's top bar.)* | One door instead of two ("is a logo an Add or an Import?"), and creation sits beside the canvas where it lands. |
| 4 | **Select first, then act, everywhere.** One list of actions, each with "valid when"; the context bar, the right-click menu, Ctrl+K and shortcuts all read it. Extended past Hem's list to Follow, Put on path, Stagger, Repeat, Make symbol, Lip sync and Add blinks. | Matches how people think ("these go together"), saves the drag-into-a-container step, and the screen and the agent share one operation per action. |
| 5 | **Animate in place.** The diamond beside a setting starts animating it; once animated, changing it anywhere in time adds a key. **K keys the selection's main settings in one press.** Selected keys get their own **key bar** in the timeline header (ease, spring, a curve you drag); the settings panel never swaps away from the layer. *(Changes Hem: clicking a key no longer replaces the settings panel.)* | No mode to forget; easing many keys is one pick; you keep seeing the layer you are animating. |
| 6 | **Arrows move what you selected, in the place you are working.** On the canvas they move it in space; in the timeline, in time. **Ctrl+arrows always move the playhead.** `,` and `.` jump to the previous / next thing that happens (a key, a marker, a drawing). | One rule instead of a list to memorise, and the habits of Figma (nudge) and After Effects (step) both fit. |
| 7 | **Painting is one model.** Any element can be painted on: its paint is its texture, kept inside its outline, painted once, and it moves, scales and fades with it. A **Drawing** is paint with no outline. **"Draw each frame"** is a switch on any painted element for hand-drawn animation. Paint (B) on nothing makes a new drawing the size of what you paint. *(Implements PLAN › Decided 2.)* | One model covers grain on a shape, a painted illustration and frame-by-frame, with one set of brushes and one way to undo. |
| 8 | **Symbols: one idea for reuse and nesting.** Select → Make symbol. A symbol is a reusable piece with its own time; each copy can change its words, colours and swap choices and has its own start, speed and loop. It replaces "precomp", "component" and "nested comp". | Three overlapping ideas from other tools become one, so there is one thing to learn and one operation for agents. |
| 9 | **Sound is in the room.** The project's music and voice play in 2D through RostrumSound's engine (rule 9), with a waveform row at the bottom of the timeline and the beat grid when Sound has a tempo. Bars, keys and the playhead snap to markers and beats; dropping a bar's end on a marker ties it there. | Timing to music by eye is not timing to music; the one-engine rule keeps it a single sound path. |
| 10 | **The agent is a co-worker, not a mode.** Its changes appear live without touching your selection, playhead or scroll; each run arrives as a group you can review or undo whole; Ctrl+Z only takes back your own steps; **Notes** (N) lets you scribble directions on a frame that the agent reads; a locked layer is locked for agents too. | You can let an agent work beside you without losing your place or your trust. |

Other decisions, with reasons, are in each feature's card (part 3) and in "Hem's draft: kept, changed, added" (end of
part 4).

## The screen at a glance

```
┌ ≡ Rostrum2D │ Spring launch › Main ▾ ··········· Saved · You: Moved title │ ↶ ↷ │ 🔍 Search  Ctrl K │ Export │ ? ┐
├──┬───────────────────────────────────────────────────────────────────────────────┬──────────────────────────────┤
│V │                ┌── context bar: what you can do right now ──┐                 │ SETTINGS                     │
│▭ │                │ 2 layers · Group  Mask  Align ▾  Combine ▾ ⋯│                 │ title · Text                 │
│✒ │                └────────────────────────────────────────────┘                 │ [Find a setting      Ctrl F] │
│T │          ┌──────────────────────────────────────────────────┐                 │ Essentials (always open)     │
│🖌 │          │                                                  │                 │ ▸ Groups folded to names     │
│  │          │              the frame, as it exports            │                 │ ▸ Effects (2)            +   │
│+ │          │                                                  │                 │                              │
│  │          └──────────────────────────────────────────────────┘                 │                              │
│  │  Logo › mark                                   Fit  50 %  Full ▾  Final ▾     │                              │
├──┴───────────────────────────────────────────────────────────────────────────────┴──────────────────────────────┤
│ ▶  2.48 s  ⟲   │ (key bar or frame tools appear here when they apply)  │ ◇ Marker  Keys│Curves  🔊  ⊟ │
│ LAYERS          │0s     1s     2s ▼drop   3s     4s     5s                                                     │
│ ▾ ▢ Logo   👁🔒 │████████████████████████████████████████                                                     │
│ T  title        │      ████◆█████◆████████████████████                                                         │
│ 🔊 Music        │▁▃▅▇▅▃▁▃▅▇█▇▅▃▁▃▅▇▅▃▁▃▅▇▅▃▁▃▅▇▅▃▁▃▅▇▅▃                                                    │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Top bar: project-wide only. Left strip: tools that make things. Top of the canvas: the context bar. Right: the
settings of what is selected (or of the scene when nothing is). Bottom, full width: the timeline and layers list.
Part 4 has every region, every state and every window size.

## How to read this spec

- **Part 1** is who uses Rostrum2D and for what.
- **Part 2** is every feature, grouped by job, each marked **Now** (needed for the first release; built or being built),
  **Next** (needed for the quality bar; the next briefs) or **Later**.
- **Part 3** is the interaction for each feature, as a card: the goal, the steps, where the controls live and when they
  appear, the feedback, how to undo or adjust, the shortcuts, the agent's operation, and the 3E reasoning with what was
  rejected. Operation names that exist today are written plain (`group.make`); new ones are marked *(new)*.
- **Part 4** is the screen: regions, what shows when, wireframes, window sizes, dialogs.
- **Part 5** is ten real jobs from an empty project to an export, with every click counted.
- **Part 6** is the feel: speed budgets, snapping, nudging, selection, keyboard, empty states, errors, first use.
- **Part 7** is the gap against today (main plus Hem's H28 work in progress) with the size of each change.
- **Appendix A** lists every shortcut; **Appendix B** every operation the screen calls.

---

# Part 1 · Who uses Rostrum2D, and for what

## The people

| Person | Who they are | What they know | What they need from us | What hurts them most |
|---|---|---|---|---|
| **Maya, motion designer** | Makes launch films, title sequences, brand motion, UI demos. Lives in After Effects and Figma. | Keys, easing, curves, masks, mattes, precomps, expressions. Fast with the keyboard. | Precision (curves, spring easing, exact timing to the frame and to music), speed (keys on many layers at once, stagger, copy and paste of motion), a picture that never lies. | Hunting for a control; a tool that is "simple" because it is shallow; waiting for the picture. |
| **Kenji, illustrator and animator** | Paints, draws, animates by hand: effects, characters, loops. Comes from Procreate Dreams, Toon Boom Harmony, Moho. | Brushes, pressure, onion skin, exposures (holding a drawing for 2 or 3 frames), line and colour on separate layers, cut-out rigs. | A big, fast canvas; brushes that feel right with a pen; zoom and rotate; frame tools at hand; a rig that bends well. | Panels that eat the canvas; a lag between pen and line; having to "set things up" before drawing. |
| **Priya, marketer** | Makes a 10–20 s social video or a product teaser now and then. Knows Canva, maybe Figma. | Fonts, brand colours, sizes for each platform. Not keys or curves. | To get a good-looking video from her brand kit in minutes, and export the right size. Words she knows. | Jargon; empty screens with no hint; anything that requires the manual. |
| **Sam with an agent** | Directs an AI agent that builds the piece through the same operations, then adjusts by hand. | What good looks like; less patience for clicking through settings. | To see what the agent did, take back what he doesn't like, point at what to change ("this, here, at 2 s"), and never have his own edits wiped by the agent's next run. | The agent changing things under his hand; not knowing what it changed. |
| **The agent itself** | Claude or another model, through Rostrum2D's agent server. | Everything in the guides; nothing it hasn't looked at. | The same operations as the screen, eyes on the result (frames, contact sheets, motion checks), the person's selection and notes, plain refusals that say what to do instead. | Screen-only features it can't call; silent failures. |

Rostrum2D is designed for Maya's precision and Kenji's canvas first, because they set the quality bar; Priya gets the
same tools with plain words, good defaults for size and type, and nothing on screen she doesn't need yet (the rule of
individuality does most of that work). The agent and Sam get the collaboration features in 3.34 and 3.35.

## The jobs people come to do

| Job | Typical piece | Who | Needs most |
|---|---|---|---|
| **Type animation** | A title, kinetic type, lyric lines, end card | Maya, Priya | Text tool, fonts, letter-by-letter animation, easing, timing to music |
| **Logo reveal** | A logo draws on, fills, settles with a glow | Maya | Import SVG / PDF, draw-on of lines, masks, booleans, stagger, effects |
| **UI and product animation** | App screens, cards sliding in, a cursor taps, a phone render from 3D | Maya | Figma import, auto layout, align, spring easing, symbols, 3D render layers, frosted glass |
| **Explainer graphics** | Icons, charts, arrows, diagrams building up | Maya, Priya | Shapes, paths, repeat, motion paths, stagger, styles |
| **Character animation** | A talking character, a walk, a gesture | Kenji | Import PSD parts, rig from parts, bones and IK, poses, swap sets, lip sync, blinks |
| **Frame-by-frame** | Hand-drawn effects (smoke, sparks, smears), a drawn loop, a character on twos | Kenji | Paint, draw each frame, exposures, onion skin, flip, stepped timing |
| **Painted illustration that moves** | A painted scene with depth and a slow camera move, a textured poster that comes alive | Kenji | Paint on elements, painted backgrounds at depths, camera, small motions |
| **Timing to music** | Anything cut to a track: beats, drops, voice lines | Everyone | Hearing the music, waveform, markers from Sound, beat grid, snapping |
| **Social post** | 9:16 or 1:1 version of a promo | Priya | Sizes by name, brand kit, export the right size |
| **Working with an agent** | Any of the above, made by an agent and finished by a person | Sam | Live view, review, per-person undo, notes, selection the agent can read |

These ten jobs are walked click by click in part 5.

## What Rostrum2D is not

- **Not the editor.** Cutting shots together, captions, versions per platform and colour grading of the whole film are
  the Rostrum Editor's (PLAN › Four separate apps). 2D makes shots and graphics that the Editor places.
- **Not the sound app.** Music, voice and sound design are RostrumSound's (rule 9). 2D plays the project's sound and
  owns only sync sound (a video's own sound; a cue tied to a beat).
- **Not a 3D app.** 3D renders come in as live layers from Rostrum3D; 2D has 2.5D depth and a camera.

---

# Part 2 · Every feature, grouped by job

Starting from PLAN's list for Rostrum2D, adding what a top motion-design and 2D-animation tool needs. **Now** = needed
for the first release (built, being built in H28, or small); **Next** = needed to reach the quality bar, the next
briefs; **Later** = deliberately after. The last column is the card in part 3. *New* marks a feature that is not in
PLAN's list or the H28 draft.

### A. Project, scenes and canvas

| Feature | What it is | When | Card |
|---|---|---|---|
| Start screen | The shared project hub: recent projects (people's, never agents' scratch), New, Open, guides | Now | 3.1 |
| New project / new scene by name | 16:9 HD, 4K, 9:16, 1:1, 4:5, custom; frame rate; length | Now | 3.1 |
| Several scenes in a project | A scene list in the top bar; PDF pages arrive as scenes | Now | 3.1 |
| Scene settings | Shown in the settings panel when nothing is selected | Now | 3.1 |
| Zoom, pan, fit, 100 % | Ctrl+wheel at the pointer, Space-drag, Ctrl+0, Ctrl+1, Shift+2 to selection | Now | 3.2 |
| Rotate and mirror the view *(new)* | Turn or mirror the canvas to check a drawing; never changes the picture | Next | 3.2 |
| Rulers and guides *(new)* | Drag guides out of the rulers; snapping to them | Next | 3.2 |
| Safe areas and grid *(new)* | Title / action safe, a layout grid, a pixel grid when zoomed in | Next | 3.2 |
| Preview size and Fast / Final | Full / Half / Quarter / Auto; Fast (no motion blur) or Final (exact export) | Now | 3.2 |
| Transparent background view *(new)* | A checkerboard behind a scene with no background, for alpha exports | Now | 3.2 |

### B. Making things

| Feature | What it is | When | Card |
|---|---|---|---|
| Rectangle, ellipse | Drag on the canvas to draw at that place and size | Now | 3.3 |
| Polygon, star, line *(new)* | The same shape tool, other shapes | Next | 3.3 |
| Rounded corners on the canvas *(new)* | Drag the corner dots; each corner on its own with Alt | Next | 3.3 |
| Pen | Click for corners, drag for curves; edit points afterwards | Now | 3.4 |
| Pencil (vector) *(new)* | Draw freehand, get a smooth editable path | Next | 3.4 |
| Variable-width lines | Width along a line; taper ends | Now (settings) · Next (on canvas) | 3.4 |
| Text tool, type on the canvas | Click and type; drag a box to wrap; double-click to edit | Now | 3.5 |
| Font list with previews | Every installed and shipped font, drawn in itself; weights by name | Now | 3.5 |
| Variable fonts, OpenType features | Axis sliders; alternates and ligatures as switches | Now (settings) · Next (glyph picker) | 3.5 |
| Text on a path | Select text + a path → Put on path | Now | 3.5 |
| Add from a file (one door for files) | Image, video, SVG, PDF / Illustrator, PSD, Lottie, audio; drop a file; Figma link | Now | 3.6 |
| Paste from other apps *(new)* | An image or SVG on the clipboard (from Figma, a browser) pastes as layers | Next | 3.6 |
| Replace a picture or video *(new)* | Keeps its keys, effects and place | Next | 3.6 |
| Crop and fit an image *(new)* | Double-click to crop; Fill / Fit / Stretch inside its box; Fill the frame | Next | 3.6 |
| Video layers | Trim, slip, speed, loop; its sound goes to Sound | Now | 3.6 |
| 3D render layers | A Rostrum3D item's newest render, updated live; open it in 3D | Now | 3.7 |
| Other project items | A Sound item (music, voice), another 2D scene as a symbol | Now (Sound) · Next (scenes) | 3.7 |

### C. Painting and drawing

| Feature | What it is | When | Card |
|---|---|---|---|
| Paint on any element | Its texture, inside its outline, painted once, moves with it | Next (H29) | 3.8 |
| Drawings | Paint with no outline; Paint on nothing makes one | Now | 3.8 |
| Paint layers inside an element *(new)* | Lines over colour, shading separate; most people use one | Next | 3.8 |
| Brushes | The shared painting kit's brushes, pressure and tilt; brush library | Now | 3.8 |
| Eraser, colour picking, fill *(fill new)* | E toggles the eraser; Alt picks a colour; a fill bucket for closed lines | Now · Next (fill) | 3.8 |
| Select and move paint *(new)* | Lasso strokes to move, scale, turn or copy them | Next | 3.8 |
| Steadiness *(new)* | Smooths shaky strokes as you paint | Next | 3.8 |
| Painted backgrounds at depths | Far / mid / near drawings sized to the camera move | Next (screen) | 3.8 |
| Draw each frame | The switch that turns a painted element into hand-drawn frames | Now | 3.9 |
| Exposures, holds, onion skin | Hold a drawing 1–n frames; see neighbours faintly | Now | 3.9 |
| Light table *(new)* | See other layers' drawings faintly while drawing | Next | 3.9 |
| Flip *(new)* | Hold to flip back and forth through drawings | Next | 3.9 |
| Stroke reveal *(new)* | Draw-on of painted strokes in the order they were painted | Later | 3.8 |

### D. Selecting and arranging

| Feature | What it is | When | Card |
|---|---|---|---|
| Click, Shift-click, box select, Ctrl+A, Esc | Picks what is painted under the pointer, outer group first | Now | 3.10 |
| Into groups: double-click, Ctrl-click, Shift+Enter | Go in, pick the deepest, go back out | Now | 3.10 |
| Select same *(new)* | Same fill, same font, same kind | Later | 3.10 |
| Move, resize, rotate on the canvas | Handles; Shift keeps proportion / straight; Alt from the centre | Now | 3.11 |
| Anchor point *(new on canvas)* | Drag the anchor; 9-point picker in the panel | Next | 3.11 |
| Nudge | Arrows 1 px, Shift 10 px | Now | 3.11 |
| Layers list = timeline rows | Order by dragging, rename, hide, lock, solo | Now | 3.12 |
| Copy, cut, paste, duplicate, Alt-drag | In place, between scenes and projects, with keys | Now | 3.12 |
| Find a layer, show only animated settings *(new)* | Search the rows; U shows only what moves | Next | 3.12 |
| Colour labels on rows *(new)* | Mark rows by colour to find them | Later | 3.12 |
| Group, ungroup, clip | From the selection | Now | 3.13 |
| Align, distribute, match size | From the selection | Now | 3.16 |
| Snapping and smart guides | To the frame, other layers, equal gaps, guides | Now | 6.2 |

### E. Combining shapes and layers

| Feature | What it is | When | Card |
|---|---|---|---|
| Mask (shape, outside, brightness, darkness) | Select the cutter + the layers → Mask | Now | 3.14 |
| Draw a mask on one layer *(new)* | Select a layer → Mask › Draw → draw the shape | Next | 3.14 |
| Booleans | Union, subtract, intersect, exclude | Now (baked) · Next (live) | 3.15 |
| Auto layout | Rows, columns, grids from a selection; gap handles on the canvas | Now | 3.16 |

### F. Motion

| Feature | What it is | When | Card |
|---|---|---|---|
| Start animating with the diamond | A key at the playhead; later changes add keys | Now | 3.17 |
| K: key the selection here *(new)* | Keys position, scale, rotation, opacity of every selected layer | Now | 3.17 |
| Select, move, stretch, copy and paste keys | Box-select on bars, drag, Alt-drag to stretch, Ctrl+C / V at the playhead | Now (select, move) · Next (stretch, paste) | 3.17 |
| Key bar and easing | Ease for all selected keys; a curve you drag | Now | 3.18 |
| Spring ease *(new)* | Bounce and settle by feel (Apple UI motion) | Next | 3.18 |
| Curve editor | Values and handles over time | Now | 3.18 |
| Speed view *(new)* | How fast a value changes, for smoothing motion | Later | 3.18 |
| Layer bars, trim, slip | Drag the bar, its ends, or the content inside | Now (bar, ends) · Next (slip) | 3.19 |
| Stagger *(new)* | Each selected layer starts n frames after the one before | Next | 3.19 |
| Markers and ties | Shared named markers; drop a bar end on one to tie it | Now | 3.19 |
| Stepped timing | Ones, twos, threes per layer, group or scene | Now | 3.9 |
| Time range and work area | Play a stretch over and over; export it | Now | 3.29 |
| Letter, word and line animation | Animate the text once, spread it per letter | Now | 3.20 |
| Letter ranges *(new)* | A wave through the letters (a range that moves) | Later | 3.20 |
| Motion paths | The path of a moving layer on the canvas, with its keys and handles | Next | 3.21 |
| Move along a path *(new)* | Select a layer and a path → it travels along it | Next | 3.21 |
| Orient along path *(new)* | A layer turns to follow its path | Next | 3.21 |
| Smears, trails, motion blur | Effects and the scene's shutter | Now | 3.25 |
| Repeat *(new)* | Copies in a row, grid, circle or along a path, with offsets | Next | 3.27 |
| Shape morphing | A path's outline changes between keys | Now | 3.4 |
| After the last key | Hold, repeat, back and forth, or carry on | Now (H31) | 3.18 |
| Time of a symbol or video *(new)* | Freeze, reverse, speed ramps | Next | 3.27 |

### F2. Expressions and links

| Feature | What it is | When | Card |
|---|---|---|---|
| Expressions | A little code on one setting, started by typing `=` | Now | 3.26 |
| Links between settings | One setting follows another, × a scale + an offset | Now (operation) · Next (on screen) | 3.26 |

### G. Following, rigs and characters

| Feature | What it is | When | Card |
|---|---|---|---|
| Follow (parenting) | Layers move with another without being grouped | Next | 3.22 |
| Make rig from parts | Select the parts → Make rig | Now | 3.22 |
| Bone tool | Draw bones from joint to joint on a selected rig | Next (H30) | 3.23 |
| Bones from part names *(new)* | A proposed skeleton from parts named like a body | Next | 3.23 |
| Attach parts to bones | Automatic by nearness; fix by select part + bone → Attach | Next (H30) | 3.23 |
| IK and posing by dragging | Drag a hand, the arm follows; pin feet | Next (H30) | 3.23 |
| Pose library | Save, apply, blend poses | Next (H30) | 3.23 |
| Swap sets | Select drawings → Make swap set; pick by thumbnail | Now | 3.23 |
| Lip sync | On a mouth set: from a voice line in the project | Next (H30) | 3.23 |
| Blinks | On an eye set: Add blinks | Next (H30) | 3.23 |
| Bend weights *(new on screen)* | Paint how much a part bends with each bone | Later | 3.23 |

### H. Camera and depth

| Feature | What it is | When | Card |
|---|---|---|---|
| Camera layer and Camera tool | Move, zoom and turn the camera on the canvas | Now (layer) · Next (tool) | 3.24 |
| Depth per layer, parallax | Each layer's distance; the camera move makes parallax | Now | 3.24 |
| Depth of field, focus by clicking | Click a layer to focus on it; key it for a rack focus | Next | 3.24 |
| Side view *(new)* | See layers' depths from above and drag them | Later | 3.24 |
| Camera shake, follow a layer | Helpers that write keys you can edit | Next | 3.24 |
| Tilt (2.5D) | Turn a layer in depth | Now | 3.24 |

### I. Look

| Feature | What it is | When | Card |
|---|---|---|---|
| Fill, outline, gradient with on-canvas handles | Gradients dragged on the canvas | Now (settings) · Next (handles) | 3.25 |
| Effects | Blur, glow, shadow, frosted glass, trail, smear; grain, displace, distort, light wrap | Now · Next (the four new) | 3.25 |
| Blend modes | All 16 plus Add | Now | 3.25 |
| Colour adjust | Exposure, contrast, saturation, curves, levels, a colour look file (LUT) | Now | 3.25 |
| Effects on the whole scene *(new)* | The scene's own effects, when nothing is selected | Next | 3.25 |
| Colour picker, eyedropper, palette | Project colours one click away | Now | 3.25 |

### J. Reuse

| Feature | What it is | When | Card |
|---|---|---|---|
| Symbols *(new as one idea)* | Reusable pieces with their own time; copies with changes | Next | 3.27 |
| Colour and text styles *(new)* | Named colours and type, change once, everywhere | Next | 3.27 |
| Copy / paste style | Look from one layer onto others | Now | 3.27 |
| Saved motions *(new)* | A person's own animation saved and applied to other layers | Later | 3.27 |
| Library drawer | Project items, symbols, styles, brushes, brand kit, connectors | Next | 3.27 |
| What ships: tools, not templates | Sizes, guides and empty projects only | Now | 3.27 |

### K. Sound and music

| Feature | What it is | When | Card |
|---|---|---|---|
| Hear the project's sound | Plays and scrubs with the picture through Sound's engine | Now (H31) | 3.28 |
| Waveform row | The last row of the timeline | Now (H31) | 3.28 |
| Shared markers on the ruler | From Sound and every app; add, rename, move | Now | 3.28 |
| Beat grid and snapping to beats | When Sound has a tempo map | Now (H31) | 3.28 |
| Sync sound | A video's own sound; a cue tied to a beat | Next | 3.28 |
| Motion samples to Sound | So Sound can place whooshes where things move | Now | 3.30 |

### L. Watching and delivering

| Feature | What it is | When | Card |
|---|---|---|---|
| Play, loop, step, scrub | Space, time range, Ctrl+arrows, drag the playhead | Now | 3.29 |
| Hide the panels | Ctrl+\ shows only the canvas and the timeline header | Now | 3.29 |
| Export panel | MP4, ProRes 4444, WebM, GIF, PNG sequence, EXR, Lottie, still, motion samples | Now | 3.30 |
| Export again *(new)* | Ctrl+Shift+E repeats the last export | Now | 3.30 |
| Exports in the background | Keep working; progress in the top bar | Now | 3.30 |

### M. Safety and files

| Feature | What it is | When | Card |
|---|---|---|---|
| Undo / redo per person | One step per gesture; yours only | Now | 3.31 |
| History drawer | Who changed what, with before / after | Next | 3.31 |
| Versions | Ctrl+S saves a named version; restore any | Next | 3.31 |
| Saving is automatic | No unsaved state to lose | Now | 3.32 |
| Crash recovery | The launcher watches; reopen exactly where you were | Now | 3.32 |
| Problems list | Missing fonts, broken links, never-seen layers, in words | Now | 3.36 |

### N. Help

| Feature | What it is | When | Card |
|---|---|---|---|
| Empty states that teach | What to do next, in one line, where you look | Now | 6.7 |
| Hover names with shortcuts | Every button | Now | 3.33 |
| Shortcut sheet | Ctrl+/ | Now | 3.33 |
| Guides inside the app | Searchable how-tos for people and agents | Now | 3.33 |
| Command search finds how-tos | "how do I mask" lands in the guide | Next | 3.37 |

### O. Working with an agent

| Feature | What it is | When | Card |
|---|---|---|---|
| Live changes that don't move you | Your selection, playhead and scroll stay | Now | 3.34 |
| Agent run as a group | Review / Undo all; changed rows marked | Next | 3.34 |
| The agent sees your selection and playhead | So "this" means what you selected | Next | 3.34 |
| Notes (paint-over directions) | Scribble and write on a frame; the agent reads them | Next | 3.35 |
| Copy a link to this *(new)* | "2D: Main › title at 2.40 s" to paste into the AI app | Next | 3.34 |
| Built-in AI panel and variations | Ask inside the app; alternate takes | Later | 3.34 |

---

# Part 3 · Every feature, and how the person does it

Each card: **Goal** · **Steps** · **Where and when** (where the controls live and when they appear) · **Feedback** ·
**Undo and adjust** · **Keys** · **Agent** (the operation an agent calls; the screen calls the same) · **3E** (why this
way, and what was rejected). Where a card leaves a field out, the default holds: **Undo** = Ctrl+Z takes the change
back as one step; **Keys** = none beyond Ctrl+K; **Rejected** = no serious alternative was found. "Context bar" means the bar at the top of the canvas (decision 2). "Settings" means the
settings panel on the right. Shortcuts are written Ctrl / Alt / Shift; on the Mac, Ctrl is ⌘ and Alt is ⌥.

## 3.1 Project, scenes and starting

### Start screen and a new project · Now
- **Goal:** start a piece, or get back to the last one.
- **Steps:** open Rostrum2D → the start screen (the shared project hub) shows **New** and your recent projects as
  pictures. New → pick a size by name (16:9 HD 1920×1080 · 4K · 9:16 vertical · 1:1 square · 4:5 · Custom) → frame
  rate (24 · 25 · 30 · 60; default from the last project) → **Create**. 2 clicks for the usual case. The project opens
  with one scene, "Main", 10 s long, and the canvas's empty state (6.7).
- **Where and when:** the start screen shows when no project is open, or from ≡ › Start screen. **Open recent lists
  only projects a person opened**; projects an agent made in a scratch folder are never listed and never open on
  launch (fixes FINDINGS 1.4).
- **Feedback:** each size shows as a small frame of the right shape; the length can be changed later by dragging the
  scene's end on the ruler.
- **Undo and adjust:** every scene setting is in the settings panel with nothing selected; change it any time.
- **Keys:** Ctrl+N new project (on the start screen); Ctrl+Shift+N new scene (inside a project); Ctrl+O open.
- **Agent:** `project` tools of the shared layer; `comp.add {size, fps, length}`.
- **3E:** *Effective:* the sizes people deliver are the ones offered. *Efficient:* two clicks; nothing to type.
  *Easy:* names, not numbers ("9:16 vertical", not "1080×1920"). *Rejected:* a blank dialog with width / height
  fields (typing numbers people don't know by heart); "templates" with content (tools, not taste).

### Several scenes in a project · Now
- **Goal:** keep the 16:9 film, the 9:16 cut-down and the end card in one project.
- **Steps:** click the scene name in the top bar (`Spring launch › Main ▾`) → the list of scenes (with small pictures) →
  pick one, or **New scene**, **Duplicate this scene**, **Rename**, **Delete**.
- **Where and when:** the scene name in the top bar, always. Delete is offered only when there is more than one scene.
- **Feedback:** switching keeps each scene's own playhead, zoom and selection.
- **Undo and adjust:** each scene operation is one undoable step (deleting a scene too).
- **Keys:** Ctrl+Shift+N new scene; Ctrl+Tab next scene.
- **Agent:** `comp.add`, `comp.duplicate` *(new)*, `comp.remove`, `item.rename`.
- **3E:** *Easy:* where you read which scene you are in is where you change it. *Rejected:* a separate Project panel
  always open (it eats width all day for something used a few times); tabs per scene (they crowd the top bar, the cause
  of the overlap bug Sam saw).

### Scene settings · Now
- **Goal:** change size, length, frame rate, background, steps, motion blur.
- **Steps:** click empty canvas outside the frame, or press Esc until nothing is selected → the settings panel shows
  the scene: **Size** (named sizes + W H), **Length**, **Frame rate**, **Background** (colour or none: transparent),
  then folded: **Timing** (Steps: ones / twos / threes), **Motion blur** (shutter, quality), **Colour** (working
  colour space), **Effects** (on the whole picture, 3.25), **Soundtrack** (3.28).
- **Where and when:** settings panel, whenever nothing is selected.
- **Feedback:** the frame on the canvas changes shape as you pick; "Length" also shows as the end of the ruler, which
  you can drag.
- **Undo and adjust:** one step each.
- **Agent:** `value.set` on the scene.
- **3E:** *Easy:* "nothing selected = the whole piece" is the habit from Figma and After Effects. *Rejected:* a scene
  settings dialog (modal; hides the picture you are setting up).

## 3.2 The canvas view

### Zoom, pan and fit · Now
- **Goal:** work on a detail, see the whole.
- **Steps:** Ctrl+wheel (or pinch) zooms **around the pointer**; Space+drag or middle-drag pans; Ctrl+0 fits the
  frame; Ctrl+1 shows 100 %; **F** zooms to the selection (Shift+2 too) *(S30)*; Ctrl+= / Ctrl+− step.
- **Where and when:** the view controls sit at the canvas's bottom-right: `Fit · 50 % ▾`. The % is a menu (Fit, 25,
  50, 100, 200, 400 %, Zoom to selection).
- **Feedback:** the % updates live; a dotted outline marks the frame's edge when zoomed in past it; the area outside
  the frame shows the layers dimmed (you can still grab them), like Figma's canvas outside a frame.
- **Undo and adjust:** the view is not part of the document (no undo step); Ctrl+0 always gets you back.
- **Keys:** as in Steps. Space is the only pan key (no separate hand tool to learn).
- **Agent:** none needed (agents see through `look_frame` / `look_at` at any zoom and region).
- **3E:** *Effective:* path points, small type and painting detail need it (FINDINGS 4.1). *Easy:* the same keys as
  Figma and Photoshop. *Rejected:* a zoom tool (Z) you pick and click (a tool for a thing the wheel does).

### Rotate and mirror the view · Next
- **Goal:** draw a curve at a comfortable angle, as on paper.
- **Steps:** Shift+Space+drag turns the view; on a pen display, two-finger twist. Click the small compass that appears
  in the view controls to set it straight again (or Shift+0).
- **Mirror:** Shift+H mirrors the view left to right (the animator's and painter's check for a lopsided drawing); a
  small "Mirrored" label shows until Shift+H again.
- **Where and when:** the compass shows only while the view is turned; the label only while mirrored.
- **Feedback:** the frame turns or mirrors on screen; the picture and export do not.
- **Agent:** none (view only).
- **3E:** *Effective:* hand-drawn lines are better drawn in the hand's natural direction (Toon Boom, Procreate).
  *Easy:* the compass appears only when the view is turned, and one click straightens it.

### Rulers, guides, safe areas and grids · Next
- **Goal:** line things up with intent; keep titles inside the safe area.
- **Steps:** Shift+R shows rulers; drag from a ruler to make a guide; drag it back off to remove; the view menu
  (`50 % ▾`) has **Safe areas**, **Layout grid** (columns, gutter, margin), **Pixel grid** (on its own above 600 %).
- **Feedback:** guides are thin lines in a calm colour; snapping to them shows (6.2).
- **Undo and adjust:** guides are saved with the scene and undoable (they are document, so agents see them).
- **Agent:** `guide.add / guide.remove` *(new)*; layout grid fields on the scene.
- **3E:** *Effective:* layout grids are how UI and type work is built. *Easy:* off by default; one menu. *Rejected:*
  rulers always on (screen space for a sometimes-thing).

### Preview size, Fast / Final, transparent background · Now
- **Goal:** keep playback smooth while working; check the exact export picture.
- **Steps:** in the view controls: **Full / Half / Quarter / Auto** (Auto lowers the size while playing if a frame
  would be late, and returns to Full when you stop) and **Fast / Final** (Fast skips motion blur and draws heavy effects
  and brush texture lighter while playing; Final draws exactly what export makes).
- **Where and when:** view controls, bottom-right of the canvas. Fast / Final appears only when the scene has something
  Fast would skip (motion blur, heavy effects or textured brushes).
- **Feedback:** a small label "Half" or "Fast" sits in the canvas's corner while not Full / Final, so you never mistake
  a lighter picture for the export. A scene with no background shows a checkerboard. The one unlabelled exception: during
  a drag the picture is drawn at half size for speed and sharpens the moment you let go (6.1). A paused frame is always
  exactly the export.
- **Agent:** `look_frame {quality}`.
- **3E:** *Effective:* preview equals export: Fast is labelled, never silent, and paused frames are always Final.
  *Efficient:* Auto means no fiddling. *Rejected:* a hidden "draft" mode that changes the picture without saying so.

## 3.3 Making shapes

### Rectangle, ellipse, polygon, star, line · Now (rectangle, ellipse) · Next (the others)
- **Goal:** put a shape exactly where and as big as you want.
- **Steps:** press R (rectangle) or O (ellipse), or click the Shape button in the tool strip (it shows the last shape
  used; right-click or a small arrow lists Rectangle, Ellipse, Polygon, Star, Line) → drag on the canvas. Shift keeps it
  square / round; Alt draws from the centre. A click without dragging makes a 200 px shape at that point. After
  drawing, the tool returns to Move (double-click the tool's button to keep it on for several shapes).
- **Where and when:** tool strip; the shape's settings appear on the right at once: Fill, Outline, W H, Corner radius
  (rectangle), Sides (polygon), Points and Inner radius (star).
- **Feedback:** live size in a small label by the pointer ("320 × 180"); smart guides while dragging (6.2).
- **Undo and adjust:** one step; resize on the canvas or in the panel.
- **Keys:** R, O, L (line); Shift, Alt while dragging.
- **Agent:** `layer.add {type: shape, kind, x, y, w, h}`.
- **3E:** *Effective:* size and place in one gesture. *Efficient:* 1 key + 1 drag (today: + Add, Shape, then move and
  resize: 4+). *Easy:* every design tool does it this way. *Rejected:* + Add › Shape dropping a default box in the
  centre, on top of other things (FINDINGS 4.2).

### Rounded corners on the canvas · Next
- **Goal:** round the corners by eye.
- **Steps:** with a rectangle selected and zoomed enough that it is bigger than ~60 px on screen, small dots sit inside
  each corner; drag one to round all four; Alt-drag one to round only that corner.
- **Feedback:** the radius shows by the pointer; the panel's Corner radius follows (it shows four fields only after
  corners differ).
- **Agent:** `value.set {radius}` / `{radii}`.
- **3E:** *Easy:* handle where the thing is (GUI_DESIGN §3.3 "on-canvas first"). *Rejected:* only a number field.

## 3.4 Paths

### Pen · Now
- **Goal:** draw any outline precisely.
- **Steps:** P → click for a corner, drag for a curve, click the first point to close (or Enter to leave it open) →
  back to Move. To edit later: double-click a path (or Enter with it selected) → its points show; drag a point or a
  handle; click on the line to add a point; Delete removes a point; double-click a point to switch smooth / corner;
  Esc or Enter leaves point editing.
- **Where and when:** the context bar while the Pen is on: "Click: corner · Drag: curve · Click the first point to
  close" and **Close path**, **Done**. While editing points: **Smooth / Corner**, **Delete point**, **Make it a shape
  again** (only if it came from a shape).
- **Feedback:** the next segment previews from the last point to the pointer; handles are drawn while dragging.
- **Undo and adjust:** every point and drag is one step; Undo while drawing removes the last point and keeps drawing.
- **Keys:** P; Shift keeps 45° steps; Alt drags one handle alone (breaks the curve); Enter / Esc to finish.
- **Agent:** `path.add_point`, `path.set_point`, `path.remove_point`, `path.close`, `path.fit`.
- **3E:** *Effective:* the industry-standard pen gives exact outlines. *Easy:* the rule is shown in the context bar
  while you need it, and nowhere else. *Rejected:* separate "add point" / "delete point" tools (Illustrator's tool zoo).

### Shape morphing · Now
- **Goal:** a logo mark that changes outline; a blob that breathes; a line that bends.
- **Steps:** select a path → click the **Shape** diamond in its settings (a key of its outline at the playhead) → move
  the playhead → edit points (double-click the path) → a second shape key. Points are matched in order; **Start point**
  (right-click a point) fixes a twist.
- **Feedback:** the outline in between draws live as you scrub; the shape keys sit on the bar like any key.
- **Agent:** `value.set {d, at}` (path-shape keys, H14).
- **3E:** *Effective:* morphing is core to logo and icon motion. *Easy:* the same diamond as every other setting.

### Pencil (vector freehand) · Next
- **Goal:** draw a line by hand and get a clean, editable path (for draw-on lines, hand-drawn arrows, signatures).
- **Steps:** Shift+P (or the Pen button's small arrow → Pencil) → draw → the stroke becomes a smooth path with few
  points. **Smoothing** sits in the context bar.
- **Feedback:** the raw line shows while drawing; it settles into the fitted path on release.
- **Agent:** `layer.add {type: path}` + `path.fit {points, smoothing}`.
- **3E:** *Effective:* a path (not paint) can draw on with Trim, morph and take a width profile. *Rejected:* asking
  people to trace by pen clicks what their hand already drew.

### Draw-on, trim and variable width · Now (settings) · Next (on canvas)
- **Goal:** lines that draw themselves on; lines with weight like a brush stroke.
- **Steps:** select one or many paths → in settings, the **Line** group: **Draw from / Draw to / Offset** (the trim, in
  %), **Width**, **Ends** (round, flat), **Taper start / end**. Animate Draw to with its diamond. On the canvas (Next):
  in point editing, Alt+drag on the line pulls width out at that spot (Illustrator's width tool).
- **Feedback:** the trimmed part disappears live as you drag the number.
- **Agent:** `value.set {trimStart, trimEnd, trimOffset}`; `path.width`.
- **3E:** *Effective:* the most-used logo and diagram effect. *Easy:* "Draw from / Draw to" are words; "trim start"
  is After Effects' jargon (it appears as a search alias).

## 3.5 Text and type

### Text tool, typing on the canvas · Now
- **Goal:** put words exactly where they go and see them as you type.
- **Steps:** T → click where the text starts (it grows as you type) or drag a box (it wraps inside) → type → Esc ends
  typing (the text stays selected). Double-click any text to type in it again; select some letters to change only
  their colour, weight or size.
- **Where and when:** the text appears at the size and font you last used (or about 8 % of the frame's height the first
  time). Its settings appear on the right: Text, Font, Weight, Size, Colour, Align, then folded Spacing, Type features,
  Letters (animation), Path.
- **Feedback:** a blinking cursor in the canvas; the box hugs the **ink** of the letters, not the line box (FINDINGS
  4.3 "box cuts through letters").
- **Undo and adjust:** one step per typing session (Undo removes what you typed since the click), not per letter.
- **Keys:** T; Esc ends; Enter is a new line; Ctrl+Enter ends.
- **Agent:** `layer.add {type: text}`, `value.set {text}`; letter styles `value.set {runs}` *(new: styled runs)*.
- **3E:** *Efficient:* 1 key + 1 click + typing (today: + Add, Text, type in a panel field). *Easy:* typing where it
  shows. *Rejected:* a text field in the settings panel as the main way (still there for long text; not the default).

### Fonts and weights · Now
- **Goal:** find the right font and weight fast.
- **Steps:** click Font → a list with each name drawn in its own font, a search box at the top, recently used first,
  then the project's brand fonts, then all. Arrow keys move through the list and the canvas previews each font live;
  Enter picks, Esc returns to the old one. Weight is a list of names (Thin … Black) for static fonts; for variable
  fonts a slider labelled with the nearest name ("Semibold · 600").
- **Feedback:** live preview on the canvas while moving through the list.
- **Undo and adjust:** one step for the pick (previewing makes no steps).
- **Agent:** `value.set {font, weight}`; `inspect_fonts` *(new; P18 friction log asked for it)*.
- **3E:** *Easy:* fonts are chosen by look; weights by name (FINDINGS 3.1). *Efficient:* preview while browsing saves
  pick-look-undo loops. *Rejected:* a free text box for the font name (today).

### Variable axes and type features · Now (settings) · Next (glyph picker)
- **Goal:** use width, slant, optical size and stylistic sets, Apple-keynote-style.
- **Steps:** the **Type features** group (folded) shows only what this font has: each axis as a slider (Width, Slant,
  Optical size, or the font's own names), and each feature the font has as a switch (Ligatures, Old-style numbers,
  Tabular numbers, Small caps, Stylistic set 1…). Every slider has a diamond, so weight and width animate.
  Next: select one letter → **Alternates** shows that letter's alternate shapes as tiles; click one.
- **Where and when:** only for fonts that have them (rule of individuality: a font with no axes shows no sliders).
- **Agent:** `value.set {axes, features}`; a feature the font lacks is refused with the layer named (P19).
- **3E:** *Effective:* animated weight / width is a staple of top-tier type motion. *Easy:* switches named in words,
  never the four-letter codes (those are search aliases).

### Text on a path · Now
- **Goal:** words that follow a curve.
- **Steps:** select the text and the path → context bar **Put on path** → the text sits on the path; drag the small
  start mark along the path to slide it; **Offset** (animatable) moves it along; **Flip side** puts it under.
- **Feedback:** the text reflows on the curve live; the path stays visible (or hide it with its eye).
- **Undo and adjust:** one step; **Take off path** in the context bar when that text is selected.
- **Agent:** `value.set {pathLayer, pathOffset, pathAlign}`.
- **3E:** *Easy:* select first, then act (FINDINGS 2.8). *Rejected:* finding "Follows path" in the settings and
  picking the path by name (today).

## 3.6 Images, video and files

### Add from a file: one door for every file · Now *(S30: was "Place")*
- **Goal:** bring in a picture, logo, video, PSD, PDF, Lottie or sound.
- **Steps:** drag files from the desktop onto the canvas (they land where you drop them) **or** press Ctrl+I / the
  **+** at the bottom of the tool strip → **Add from a file…** *(S30)* → pick one or several. Layered files (SVG, PDF, PSD,
  Illustrator) come in as a group named after the file, centred, at their own size (shrunk to 90 % of the frame only if
  bigger). A PDF with several pages asks once: **This page / All pages as scenes**. A sound file goes to the project's
  sound (3.28). A Figma frame: copy its link in Figma → Ctrl+V on the canvas → Rostrum asks for your Figma token the
  first time (never stored in the project).
- **Where and when:** + in the tool strip, Ctrl+I, drop anywhere on the canvas or onto a layer row (drop onto a
  picture row = Replace, below).
- **Feedback:** a small panel at the canvas's right edge shows progress for big files (the work runs in the
  background; the screen never freezes) and then one line: "Placed logo.svg: 14 layers". If anything didn't come
  across, the line says how many, with **Show what** (the list in words: "2 gradients on outlines, drawn as flat
  colour"). A fully clean import closes the panel by itself after 3 s. Choosing files uses the system's own file window.
- **Undo and adjust:** the whole placement is one step.
- **Keys:** Ctrl+I; drop.
- **Agent:** `run_import {file, page, at}`; `layer.add {type: image|video}`.
- **3E:** *Effective:* every format through one door means one report, one fitting rule. *Efficient:* drop = 1
  gesture. *Easy:* nobody has to know whether a logo is "Add" or "Import". *Rejected:* separate + Add › Image and
  Import (today: two doors to the same thing); an import dialog with options before you see anything.

### Paste from other apps · Next
- **Goal:** copy a shape in Figma or an image in a browser and paste it.
- **Steps:** Ctrl+V on the canvas. SVG on the clipboard comes in as layers; a picture as an image layer (saved into
  the project's files); plain text as a text layer.
- **Undo and adjust:** one step for the whole paste.
- **Agent:** `layer.paste` (extended to outside clipboards).
- **3E:** *Efficient:* the fastest route designers use daily. *Rejected:* saving to a file and placing it first.

### Replace a picture or video · Next
- **Goal:** swap the placeholder screenshot for the final one, keeping all the animation.
- **Steps:** select the image → context bar **Replace…** (pick a file) or drop a file onto its row in the timeline.
- **Feedback:** the new picture fills the same box (Fill / Fit kept).
- **Undo and adjust:** one step.
- **Agent:** `layer.replace {id, file}` *(new)*.
- **3E:** *Effective:* real projects change their artwork late. *Rejected:* delete, re-place, re-animate.

### Crop and fit · Next
- **Goal:** show only part of a picture; fill a box with it.
- **Steps:** double-click an image → crop handles on its edges, the outside part dimmed; drag the picture inside to
  re-centre; Enter. In settings: **Fit: Fill / Fit / Stretch**. For a background photo: context bar **Fill the frame**
  sizes and centres it to cover the whole frame in one click.
- **Agent:** `value.set {crop, fit}` *(new fields)*.
- **3E:** *Easy:* double-click = "go into it", the same as text and paths.

### Video layers · Now
- **Goal:** use footage or a screen recording.
- **Steps:** place it; its bar shows its length; drag the bar's ends to trim it, drag inside the bar with Alt to slip
  which part plays (Next); settings: **Speed**, **Loop**, **Start at**. Its own sound is passed to Sound and plays in 2D
  as a sound row tied to the video (3.28).
- **Time (Next):** a keyable **Time** setting says which moment of the clip shows, for freezes, reverse and speed
  ramps (After Effects' time remapping, in words).
- **Feedback:** the bar shows small frame pictures when the row is tall enough; scrubbing uses a lighter copy of the
  video made once in the background (Next).
- **Agent:** `layer.add {type: video}`, `layer.trim`, `value.set {speed, offset, loop}`.
- **3E:** *Easy:* trim like any other bar. *Rejected:* a separate clip editor (that's the Editor's job).

## 3.7 3D renders and other project items

### A 3D render layer · Now
- **Goal:** put the phone from Rostrum3D into the 2D piece and keep it up to date.
- **Steps:** + › **3D render** → a list of the project's 3D items with their newest render as a picture → pick one →
  it lands centred, playing its frames. In settings: **Version** (Newest, or pin one), **Timed from marker**, Speed,
  Loop, and **Open in Rostrum3D** (opens the item at this moment).
- **Where and when:** "3D render" is in the + menu only when Rostrum3D is installed and the project has a 3D item.
- **Feedback:** when the 3D item changes after its last render, the row shows a small **Out of date** label with
  **Render again** (sends a job to Rostrum3D through the jobs queue). When a new render lands the picture updates
  by itself.
- **Agent:** `layer.add {type: render3d, item}`; `project.latest_render`.
- **3E:** *Effective:* product shots stay live (PLAN). *Easy:* pick by picture, not by typing an item name (STATUS
  gap). *Rejected:* exporting from 3D and importing a movie by hand.

### Other scenes, and the project's sound · Now (sound) · Next (scenes)
- **Goal:** use another scene of this project inside this one; hear the project's music.
- **Steps:** another scene: open the library drawer (3.27) → drag the scene in; it arrives as a **symbol** copy (3.27).
  Sound: see 3.28.
- **Agent:** `symbol.place {source}` *(new)*.
- **3E:** one idea (symbol) for every "piece inside a piece".

## 3.8 Painting and drawing

The model (PLAN › Decided 2): **paint belongs to an element.** Every shape, text, picture and drawing can hold paint.
The paint is the element's own look: kept inside its outline (for elements that have one), painted once, and it
moves, scales, turns and fades with the element. A **Drawing** is an element that is only paint, with no outline.
**Draw each frame** is a switch on any painted element that makes its paint change from frame to frame (3.9).

### Paint (B) · Now (drawings) · Next (on any element, H29)
- **Goal:** paint a texture on a shape, paint an illustration, sketch.
- **Steps:** B (or the brush in the tool strip) →
  - with an element selected: strokes go **onto that element**, clipped to its outline (a shape, a text, a picture);
  - with a drawing selected: onto the drawing;
  - with nothing selected: the first stroke makes a **new drawing**, its box fitting what you paint, and later strokes
    grow it.
  Paint. V or Esc goes back to Move.
- **Where and when:** while Paint is on:
  - the **context bar** shows the brush you are using (its picture), **Size**, **Opacity**, **Colour** (a swatch: click
    for the picker), **Eraser** (E), and **Painting on: Card ▸** (the element; click to change it to another painted
    element or a new drawing);
  - the **settings panel** shows **Brush** first (the brush library as pictures; folded: Shape, Grain, Pressure,
    Tilt, Spacing) and under it **Paint on Card** (paint layers, **Keep inside the outline** on / off, **Draw each
    frame** switch, Onion skin when that switch is on);
  - the **timeline** goes to Paint's own height (compact at first: the painted element's row with its frames),
    remembered per tool (Hem's two heights).
- **Feedback:** the stroke draws under the pen at the screen's refresh rate (6.1); outside-the-outline paint is never
  shown (no surprise at export); a thin outline of the element's edge shows while painting so you know the limit.
- **Undo and adjust:** each stroke is one step. Paint can be moved later (lasso, below).
- **Steadiness (Next):** a slider in the brush settings smooths shaky strokes as you paint (Procreate's StreamLine);
  0 by default for sketching, higher for clean lines.
- **Keys:** B; E eraser on / off (the pen's back end erases on its own); [ and ] size; Shift+[ / ] softness; Alt
  (hold) picks a colour from the canvas; Shift+drag draws a straight line; numbers 1–0 set opacity 10–100 %.
- **Agent:** `stroke.add {target, points (x, y, pressure, tilt, speed), brush, colour, opacity, layer}` (today on a
  drawing; extended to any element); eyes `look_drawing`, `inspect_stroke_landed`.
- **3E:** *Effective:* one model serves texture, illustration and hand animation (PLAN). *Efficient:* no "make a
  drawing layer first" step; paint on what you selected. *Easy:* "paint goes on what's selected; on nothing, it makes
  a drawing" is one sentence. *Rejected:* a Draw page (today); a separate "texture" feature for shapes (a second
  model); painting that sticks to the screen rather than the element (it would slide off when the element moves).

### Paint layers inside an element · Next
- **Goal:** keep line art above colour, or shading separate, so each can change alone.
- **Steps:** in the settings panel's **Paint on …** group, the element shows one paint layer, "Paint". **+ Paint
  layer** makes your **next stroke** start a new paint layer above (nothing empty is made); drag to reorder; each has an
  eye, opacity and blend; right-click › Delete. Strokes go to the highlighted one.
  In the timeline, opening the element's row (its arrow) shows paint layers as sub-rows only when there are two or
  more.
- **Agent:** `paint.stroke {layer: "new"}` makes the paint layer with its first stroke; `paint.set`, `paint.move`, `paint.remove` *(H30: built under these names)*.
- **3E:** *Effective:* lines over colour is how hand animation and illustration are built (Toon Boom's line and
  colour art). *Easy:* invisible until you want a second layer. *Rejected:* making every paint layer a timeline layer
  (doubles rows; breaks "paint belongs to its element").

### Eraser, colour picking and fill · Now (eraser, pick) · Next (fill)
- **Goal:** fix strokes; take colours from the picture; fill a closed line drawing.
- **Steps:** E toggles the eraser (any brush can erase); hold Alt to pick a colour under the pen; **Fill** (G while
  Paint is on, Next): click inside a closed area → it fills on the current paint layer, with **Close gaps** (small,
  medium, large) in the context bar for lines that don't quite meet. Fill finds its edges in **all** the element's
  paint layers, so the colour layer fills up to the lines on the line layer.
- **Agent:** `stroke.add {erase: true}`, `paint.fill {target, at, colour, gap}` *(new)*.
- **3E:** *Effective:* fill with gap closing is what makes colouring hand-drawn frames fast (Toon Boom). *Easy:* the
  eraser is a switch, not a second tool to set up.

### Select and move paint · Next
- **Goal:** move or resize part of a painting without repainting it.
- **Steps:** while Paint is on, hold Ctrl and drag a lasso around strokes (or **Select strokes** in the context bar) →
  the chosen strokes get a box with handles → drag, scale, turn; Ctrl+C / V copies them; Delete removes; Enter or a
  click outside ends.
- **Agent:** `stroke.set {ids, transform}`; `background.move` (to another depth layer).
- **3E:** *Effective:* strokes are kept as strokes (PLAN), so moving them stays sharp. *Rejected:* a pixel-only
  selection (blurs on every move).

### Painted backgrounds at depths · Next
- **Goal:** a painted scene with far, middle and near parts that move at different speeds as the camera moves.
- **Steps:** paint it as one drawing or several; select the drawings → context bar **Set depth ▾** (Far · Middle ·
  Near · or a number) → each moves back and is resized so it still covers the camera's whole move. To split one
  painting: select strokes (above) → **Move to depth ▾**.
- **Where and when:** Set depth appears for drawings when the scene has a camera; without a camera it says why in Ctrl+K
  ("needs a camera: + › Camera"). There is no "+ Painted background" item: you paint first, then set depths (select
  first, then act).
- **Feedback:** the camera's frame shows its whole move as a faint path on the canvas; a layer that would not cover
  the shot shows a warning stripe at the uncovered edge.
- **Agent:** `background.add`, `background.fit`, `background.move`; eyes `look_background`, `inspect_background`.
- **3E:** *Effective:* parallax by depth is how painted films move (PLAN). *Easy:* the maths of resizing for depth is
  done for you. *Rejected:* making people compute sizes by hand.

### Stroke reveal · Later
- **Goal:** a painting that paints itself on.
- **Steps:** on a painted element: **Reveal** (0–100 %, animatable) under Paint, in the order strokes were painted.
- **Agent:** `value.set {reveal}`.

## 3.9 Frame-by-frame

### Draw each frame · Now
- **Goal:** hand-drawn animation: smoke, sparks, a walk, a smear. (Animators call a held drawing an "exposure"; on
  screen it is a **hold**.)
- **Steps:** with a painted element selected (or a new drawing), switch **Draw each frame** on (settings, under Paint;
  or Alt+N, which turns it on and starts the next drawing). Now each **drawing** is held on the timeline as a block.
  Draw → Alt+N (new drawing at the playhead, blank) or Alt+Shift+N (a copy of this one to change) → draw → …
- **Where and when:** when a frame-by-frame element is selected, the **timeline header** shows its frame tools:
  ◀ ▶ (previous / next drawing), **New**, **Copy**, **Hold − / +**, **Onion** (with how many before / after and their
  tint), and **New drawings hold: 1 / 2 / 3 frames** (on ones, twos, threes). The element's bar shows each drawing as
  a block; its length is how long it is held.
- **Feedback:** blocks appear as you draw; onion skin shows the previous drawing(s) in one tint and the next in
  another, fading with distance.
- **Undo and adjust:** each stroke, new drawing and hold change is one step. Drag a block's right edge to hold it
  longer; drag a block to move it; Alt-drag to copy it; Delete removes it (the previous one holds over the gap).
- **Keys:** Alt+← / Alt+→ previous / next drawing (also `,` and `.` when this layer is selected), Alt+N new,
  Alt+Shift+N copy, Alt+↑ / Alt+↓ hold longer / shorter, Alt+O onion skin.
- **Agent:** `frame.add`, `frame.hold`, `frame.remove`, `stroke.add {frame}`; eyes `look_drawing_change`.
- **3E:** *Effective:* holds as blocks are how animators think (Toon Boom's X-sheet, Dreams' flipbook).
  *Efficient:* keyboard-only between drawings. *Easy:* the frame tools appear only on a frame-by-frame layer.
  *Rejected:* a separate frame-by-frame layer type (a fourth model); an X-sheet grid view (powerful but a second
  timeline to learn: later, if animators ask).

### Onion skin, light table, flip through · Now (onion) · Next (light table, flip through)
- **Goal:** see where the last drawing was; see the other layers; feel the motion.
- **Steps:** Onion (Alt+O) shows 1 before and 1 after by default; its small menu sets counts (0–5) and tints.
  **Light table** (in the same menu, Next): show other layers' drawings faintly too. **Flip through** (Next): hold `,` or `.`
  to flip through the drawings at the scene's speed; release to stop.
- **Agent:** onion is view only; `look_drawing {onion}` gives the agent the same view.
- **3E:** *Easy:* one button, sensible default, depth one menu away.

### Stepped timing (on ones, twos, threes) · Now
- **Goal:** hand-drawn feel for keyed motion; a character on twos while the camera stays smooth.
- **Steps:** select layers (or nothing, for the scene) → settings **Timing › Steps: Every frame / On twos / On threes /
  On fours / As its group**.
- **Agent:** `value.set {steps}`.
- **3E:** *Effective:* mixed rates in one shot (PLAN tool 12). *Easy:* the name says it ("On twos"). *Rejected:*
  baking the steps into keys (the document's keys stay smooth, so a change of mind is one pick).

## 3.10 Selection

### Click, add, box, all, none · Now
- **Goal:** pick exactly the things to work on.
- **Steps:** on the canvas: click picks the layer **whose paint is under the pointer** (never an empty box: FINDINGS
  1.3), outer group first; Shift+click adds or removes; drag on empty canvas draws a box (touching layers are picked;
  Shift+drag adds, Ctrl+drag picks the deepest pieces *(S30)*); Ctrl+A picks all at this level; Esc clears (one level at a time: keys →
  points → layers → nothing). In the layers list: click, Ctrl+click adds / removes, Shift+click picks a range (Windows
  list habit). In the timeline's bar area: click a bar picks its layer; drag on empty bar area box-selects **keys**.
- **Where and when:** everywhere; canvas, rows and settings always agree (one selection).
- **Feedback:** selected layers: a box with handles on the canvas (one box around several), highlighted rows, and the
  settings panel's header says what: "title · Text" or "3 layers". Hovering a layer on the canvas outlines it thinly
  first, so you see what a click will pick.
- **Undo and adjust:** selection is not a document change (no undo step), but Undo restores the selection that went
  with the step it undoes.
- **Keys:** Shift / Ctrl as above; Ctrl+A; Esc; Tab / Shift+Tab pick the next / previous layer at this level.
- **Agent:** the agent reads the person's selection through `inspect_screen` *(new)*; its own operations name ids.
- **3E:** *Easy:* hover-before-click removes guessing; each place keeps the habit people bring to it (canvas = Figma,
  list = Windows). *Rejected:* one modifier rule for both places (Hem considered it; either canvas or list users lose a
  habit).

### Into and out of groups · Now
- **Goal:** move the whole logo usually; reach one piece when needed.
- **Steps:** click picks the outer group; double-click goes one level in (or Enter); Ctrl+click picks the deepest
  layer under the pointer straight away; Shift+Enter goes back to the parent. While inside a group, the canvas's
  bottom-left shows the path: `Logo › mark`; click a name to go back to it.
- **Feedback:** outside the entered group, layers dim slightly.
- **3E:** *Efficient:* most moves are whole groups (Hem's F2, F3); the piece is one more click. *Easy:* the path shows
  where you are. Same as Figma.

### Select same · Later
- **Goal:** pick every layer with this fill / font / kind.
- **Steps:** right-click › **Select same › Fill / Font / Kind / Effect**.
- **Agent:** none needed (agents query by `inspect_item`).

## 3.11 Transform

### Move, resize, rotate · Now
- **Goal:** place and size things by eye.
- **Steps:** drag the layer to move; drag a corner or edge handle to resize (Shift keeps proportions; Alt from the
  centre); hover just outside a corner, the pointer turns into a curved arrow, drag to rotate (Shift: 15° steps); Alt+drag
  on the layer drags a copy. Several selected move, resize and rotate as one.
- **Where and when:** handles on the selection with the Move tool. Handles turn with a turned layer (and the resize
  pointers turn with it: STATUS gap).
- **Feedback:** the box and the picture move together, every frame (Hem's base fix: overlays are drawn from the state of
  the picture on screen); a small label by the pointer shows the value (X Y, W × H, angle); smart guides (6.2).
- **Undo and adjust:** one step per drag. If the setting is animated, the drag adds or changes a key at the playhead
  (3.17).
- **Agent:** `value.set {x, y, w, h, rotation}`.
- **3E:** *Effective:* drags never lie about where the thing is. *Easy:* every design tool's handles.

### Numbers, nudge and arithmetic · Now
- **Goal:** exact values.
- **Steps:** in settings, X Y sit on one row, W H on one row with a link for proportions. Drag a field's label left /
  right to scrub (Shift ×10, Alt ×0.1). Type maths: `+20`, `*2`, `50%` (of the frame), `=` starts an expression
  (3.26). Arrows nudge the selection on the canvas by 1 px (Shift: 10 px).
- **Feedback:** the canvas follows the scrub live.
- **Undo and adjust:** one step per committed value, per scrub, per nudge burst (key presses within 1 s are one step).
- **Agent:** `value.set`.
- **3E:** *Efficient:* pairs on one row halve the panel's height (FINDINGS 4.2). *Easy:* scrubbing labels and maths in
  fields are Figma / After Effects habits.

### Anchor point · Next
- **Goal:** turn and scale around the right point (a door on its hinge, a needle at its base).
- **Steps:** drag the small circle at the layer's centre (shown when one layer is selected) to move the anchor
  **without** moving the picture; or the 9-dot picker in settings **Anchor**.
- **Agent:** `value.set {anchorX, anchorY}` (the screen also adjusts x / y so nothing jumps).
- **3E:** *Easy:* a 9-dot picker reads at a glance; "Anchor X 0.50" did not (FINDINGS 4.3).

## 3.12 Layers and stacking

### The layers list (the timeline's left side) · Now
- **Goal:** see the stack, find a layer, change order.
- **Steps:** each row: kind icon, name (indented inside groups), and, on hover or when on, an **eye** and a **lock**.
  Drag a row up or down to reorder (a drop line shows; dropping onto a group puts it inside). Double-click or F2 to
  rename. Right-click: the selection's actions (the same list as the context bar).
- **Where and when:** the timeline's name column, full or compact (3.19). In compact, the selected row's name is a menu
  of all layers.
- **Feedback:** a moved row and its bar move together.
- **Undo and adjust:** each reorder, rename, hide and lock is one step.
- **Keys:** Ctrl+] / Ctrl+[ forward / back; Ctrl+Shift+] / [ to front / back; F2 rename; Ctrl+Shift+H hide / show;
  Ctrl+Shift+L lock / unlock; Alt+click an eye: show only this layer (solo, below).
- **Agent:** `layer.arrange`, `item.rename`, `layer.hide`, `layer.lock`, `layer.unlock`.
- **3E:** *Efficient:* one list for stack and time (Hem). *Easy:* the eye and lock are where every app puts them.
  *Rejected:* a separate Layers panel beside the timeline (two lists of the same layers, read twice).

### Hide, lock, solo · Now
- **Goal:** get things out of the way while working.
- **Steps:** eye hides (a hidden layer does **not** export, and the row says so with a struck eye); lock stops it being
  picked or changed **by anyone, agents included**; Alt+click an eye shows only that layer.
- **Feedback:** solo is a viewing aid and says so: a bar across the top of the canvas reads **"Showing only Hills ·
  export shows everything · Show all"**. It ends with Show all, or Alt+click on the eye again (Esc is kept for
  clearing the selection).
- **Agent:** `layer.hide`, `layer.lock`; a locked layer refuses agent operations with "Locked by Sam: unlock it first".
- **3E:** *Effective:* lock as a shared rule makes it the simplest way to protect your work from an agent.
  *Easy:* solo is labelled, so preview equals export is never broken silently.

### Copy, cut, paste, duplicate, delete · Now
- **Goal:** reuse layers here, in another scene, or another project.
- **Steps:** Ctrl+C / Ctrl+X / Ctrl+V (paste lands **in place**, above the selection; Ctrl+Shift+V pastes at the
  pointer); Ctrl+D duplicates with a small offset (repeat Ctrl+D after moving the copy once: the next copies repeat
  the same offset, Figma's "smart duplicate"); Alt+drag drags a copy; Delete removes. Keys, effects and children come
  along.
- **Agent:** `layer.paste`, `layer.duplicate`, `layer.remove`.
- **3E:** *Efficient:* smart duplicate builds a row of buttons in three presses.

### Find a layer, show only what moves · Next
- **Goal:** find your way in a scene of 40+ layers.
- **Steps:** Ctrl+Shift+F (or the small search box at the top of the layers column, shown once there are more than
  12 layers) filters the rows by name or kind. **A** *(S30: was U)* with layers selected opens only the settings that are animated;
  A again folds them.
- **Agent:** none needed (`inspect_item`).
- **3E:** *Efficient:* no scrolling through rows. *Easy:* the search box appears when the list is long enough to need it.

### Colour labels · Later
- Right-click › **Label ▾** colours a row's edge; Ctrl+K "select label red". `value.set {label}`.

## 3.13 Grouping and clipping

### Group and ungroup · Now
- **Goal:** treat several layers as one.
- **Steps:** select 2+ layers → Ctrl+G (or context bar **Group**). The group's box hugs them; nothing moves. Ungroup:
  select the group → Ctrl+Shift+G; the layers go back where they are on screen.
- **Where and when:** Group shows in the context bar for 2+ layers in the same parent; Ungroup for a group.
- **Feedback:** the new group is selected and named "Group" ("Group 2" only when a "Group" exists: FINDINGS 4.3).
- **Agent:** `group.make {ids}`, `group.release {ids}`.
- **3E:** select first, then act (Sam). *Rejected:* + Add › Group (empty, then filled: the old way).

### Clip to a shape · Now
- **Goal:** a window: show the layers only inside a frame (a phone screen, a card).
- **Steps:** select the frame shape (top) + the layers → context bar **Clip** (under Mask ▾) → the shape becomes the
  window; the layers scroll and move inside it. Or select layers alone → **Clip to their box**.
- **Agent:** `group.make {ids, as: "clip"}`.
- **3E:** *Easy:* the same gesture as Mask; Clip keeps the frame's own fill (a card with content), Mask does not.

## 3.14 Masks and mattes

One idea for the person (a **mask**), with a choice of how it cuts; mattes are masks that use brightness. The agent
operation is one (`mask.make`).

### Mask with a layer · Now
- **Goal:** show layers only inside (or outside) another shape, text or picture.
- **Steps:** select the cutter **on top** and the layers it cuts → context bar **Mask** (Ctrl+Alt+M). They become a
  mask group; the cutter keeps its handles and can be animated like any layer. Then in settings, on the group:
  **Cuts with: Its shape / Outside its shape / Its brightness / Its darkness**, **Soften edge**, **Grow / shrink**.
- **Where and when:** Mask shows for 2+ layers in one parent; the topmost picked is the cutter (the context bar says
  so: "Mask with *circle*").
- **Feedback:** the masked result at once; while the cutter is selected, its outline shows dashed over the picture
  even though it is invisible itself.
- **Undo and adjust:** one step; **Release mask** (on the group) gives back the layers unchanged.
- **Keys:** Ctrl+Alt+M.
- **Agent:** `mask.make {cutter, targets, mode: alpha|alphaInverted|luma|lumaInverted}`, `mask.release`.
- **3E:** *Effective:* any layer can cut (text masks, painted masks, video mattes). *Efficient:* 1 action. *Easy:*
  modes in words, not "track matte luma inverted". *Rejected:* Ctrl+K "Add mask" making a 200 px box at the corner
  with no outline (today, FINDINGS 2.2); masks and mattes as two features.

### Draw a mask on one layer · Next
- **Goal:** cut a single layer without making a separate shape first.
- **Steps:** select the layer → context bar **Mask ▾ › Draw rectangle / ellipse / with the pen** → draw on the canvas →
  the mask is made from what you drew.
- **Agent:** `layer.add {type: shape}` + `mask.make` in one change.
- **3E:** *Efficient:* 1 action + 1 drag for the most common case (a wipe).

## 3.15 Booleans

### Combine shapes · Now (baked) · Next (live)
- **Goal:** build a shape from others (a crescent, a cut-out icon).
- **Steps:** select 2+ shapes or paths → context bar **Combine ▾ › Union / Subtract / Intersect / Exclude**. Now: the
  result is a new path. Next: the result is a **live combined shape**: its parts stay editable and animatable inside it
  (move the subtracting circle and the crescent changes), with **Flatten** to make it a plain path.
- **Where and when:** only for 2+ shapes / paths in one parent.
- **Feedback:** the result at once; with a live combine selected and entered, the parts show as outlines.
- **Keys:** Ctrl+Alt+U union, Ctrl+Alt+S subtract, Ctrl+Alt+I intersect, Ctrl+Alt+X exclude.
- **Agent:** `shape.boolean {ids, op}`; live: `group.make {ids, as: "boolean", op}` *(new)*; `path.flatten` *(new)*.
- **3E:** *Effective:* live combines animate (a moon phase, a logo cut that slides), which is why the live version is
  the target. *Easy:* Figma's model.

## 3.16 Auto layout, align and distribute

### Align, distribute, match size · Now
- **Goal:** tidy things fast.
- **Steps:** select → context bar **Align ▾** (six edges as icons in a row: left, centre, right, top, middle, bottom),
  **Distribute ▾** (even gaps across / down; 3+ layers), right-click **Match width / height / size** (the first picked
  sets the size). With one layer selected, Align aligns it to the frame.
- **Feedback:** the change is instant; equal gaps flash pink once.
- **Keys:** Alt+A / D / W / S (left / right / top / bottom), Alt+H / V (centre across / up and down).
- **Agent:** `layer.align {ids, edge, to}`, `layer.distribute {ids, axis}`, `layer.match_size {ids, to, dims}`.
- **3E:** *Efficient:* one pick replaces typing positions one by one (FINDINGS 3.3). Same keys as Figma.

### Auto layout · Now
- **Goal:** rows of buttons, columns of cards, grids of tiles that keep their spacing when content changes.
- **Steps:** select the layers → Shift+A (context bar **Auto layout**) → they become a row in the order they sit left to
  right (a column if they were stacked). In settings: **Direction** (row, column, grid as three icons), **Gap**,
  **Padding**, **Align** (a 9-dot picker), **Wrap**. On the canvas: hover the gap between two children → it shows pink
  with a small handle; drag to change the gap for all. Drag a child within the layout to reorder (Next). Each child gets
  **Size: Fixed / Hug / Fill** and **Ignore layout**. A child's place comes from the layout, so its settings show
  **Offset X Y** instead of X Y: a nudge from its laid-out place, animatable, which is how a card slides into its slot.
- **Feedback:** reflows live; animating a child's size or hiding it reflows the others every frame.
- **Undo and adjust:** one step per change; **Remove auto layout** keeps everything where it is.
- **Agent:** `group.make {ids, as: "layout"}`, `value.set {layout, gap, padding, …}`; eyes `inspect_layout`.
- **3E:** *Effective:* UI animation is built from layouts (Figma's model). *Easy:* gap handles on the canvas.
  *Rejected:* layout as a group setting you find after making an empty group (today).

## 3.17 Keys

### Start animating: the diamond · Now
- **Goal:** make a setting change over time.
- **Steps:** move the playhead to the start → click the **diamond** beside the setting (e.g. Opacity) → a key with
  today's value. Move the playhead → change the value (type, scrub, or drag on the canvas) → a second key is added there.
  From now on, changing the setting at any time adds a key at that time, or changes the key already there.
- **Where and when:** a diamond sits beside every setting that can animate: faint when not animated (always visible,
  not only on hover: FINDINGS 3.1), outlined when animated but no key here, filled when a key is here. Click a filled
  diamond to remove that key; right-click › **Stop animating** keeps the value at the playhead.
- **Feedback:** keys appear on the layer's bar at once; the row of an animated setting appears when the layer is open.
- **Undo and adjust:** each key action is one step.
- **Agent:** `key.add`, `value.set {at}` (adds or changes the key at that time), `key.remove`, `key.clear`.
- **3E:** *Effective:* the After Effects model, proven for precise keys. *Efficient:* no mode. *Easy:* the diamond's
  three states say everything. *Rejected:* a record / auto-key mode (people forget it is on and key by accident; Rive's
  modes); keys only in the timeline (separates the value from its key).

### K: key the selection here · Now
- **Goal:** block out a pose for many layers at once (the start of a move, a UI state).
- **Steps:** select layers → K → keys for position, scale, rotation and opacity on every selected layer at the playhead
  (for a rig: every bone; for text with letters animating: also the letter settings). From there, changes at other
  times add keys.
- **Feedback:** the context bar flashes "Keyed 4 settings on 3 layers".
- **Agent:** `key.add {ids, fields: "pose"}`.
- **3E:** *Efficient:* 1 key instead of 4 diamonds × n layers (Moho / Toon Boom's "key all"). *Easy:* one letter for
  "key". *Rejected:* auto-key on every change (a mode).

### Select, move, stretch, copy and paste keys · Now (select, move) · Next (stretch, paste)
- **Goal:** retime motion without re-keying.
- **Steps:** click a key on a bar; Ctrl+click adds or removes one, Shift+click picks the run of keys between *(S30: the list rule)*; drag a box over keys on several bars. Drag selected keys to move
  them (they snap to the playhead, markers, beats and other keys). Alt+drag the first or last selected key to
  **stretch** the whole selection in time (Next). Ctrl+C copies keys; move the playhead; Ctrl+V pastes them starting
  there, onto the same settings of the selected layers (Next).
- **Where and when:** keys sit on each layer's bar (all its keys) and on the open setting rows (that setting's keys).
- **Feedback:** while dragging, a label shows the time offset ("+6 f"); the key bar appears (3.18).
- **Undo and adjust:** one step per drag / paste.
- **Keys:** ← / → move selected keys 1 frame (Shift 10) when the timeline has focus (decision 6); Delete removes.
- **Agent:** `key.set {time}`, `key.scale {ids, around, by}` *(new)*, `key.paste {from, ids, at}` *(new)*.
- **3E:** *Efficient:* box-select and stretch are the daily retiming moves (FINDINGS 4.2 "keys one at a time").

## 3.18 Easing and curves

### The key bar · Now
- **Goal:** set how a move starts and lands, for one key or many.
- **Steps:** select keys → the **timeline header** shows the key bar: **Ease ▾** (Linear, Ease in, Ease out, Smooth,
  Spring, Jump (no in-between: the value jumps at the next key), Custom), a **small curve** you can drag (two handles, like a CSS cubic curve), and, for one key, its
  **Time** and **Value**. Pick or drag; every selected key changes. Right-click on a key gives the same Ease list.
- **Where and when:** in the timeline header, only while keys are selected; the settings panel keeps showing the
  layer, with the keyed setting highlighted (decision 5).
- **Feedback:** the ease shows on the bar between keys as a tiny shape (a straight line for linear, a curve for eased,
  a step for jump); the canvas plays the stretch once when you pick an ease (turn off in the key bar's ⋯), so you see
  the feel at once.
- **Undo and adjust:** one step per pick or curve drag.
- **Keys:** F9 smooth (the After Effects habit); Shift+F9 ease in; Ctrl+Shift+F9 ease out; Ctrl+Alt+J jump.
- **Agent:** `key.set {ease}`, `key.handles`; eyes `inspect_curve`.
- **3E:** *Effective:* the curve chip gives exact control without opening the curve editor. *Efficient:* one pick
  eases all selected keys. *Easy:* named eases first, the curve for those who want it. *Rejected:* the settings panel
  swapping to the key (Hem / today: you lose the layer's settings each time you touch a key, FINDINGS 3.1).

### After the last key · Now (H31)
- **Goal:** a spinner that keeps turning, a pulse that repeats, without copying keys.
- **Steps:** select the last key → key bar ⋯ › **After the last key: Stay · Repeat · Back and forth · Carry on**.
- **Feedback:** the repeat shows on the bar as faint copies of the keys.
- **Agent:** `key.set {after}` *(new)*.
- **3E:** *Efficient:* one pick, no expression needed. *Rejected:* `loop()` in an expression as the only way.

### Spring · Next
- **Goal:** the bouncy-but-settled feel of Apple's UI motion.
- **Steps:** Ease ▾ › **Spring** → two sliders appear in the key bar: **Bounce** (0 none – 1 a lot) and **Speed**. The
  move overshoots and settles by the next key's time (or past it, shown as a faint tail on the bar).
- **Agent:** `key.set {ease: "spring", bounce, speed}` *(new ease)*.
- **3E:** *Effective:* springs are the signature of modern UI motion; faking them with keys is slow and never right.
  *Easy:* two words, not mass / stiffness / damping (those are search aliases for experts).

### Curve editor · Now
- **Goal:** shape a motion by hand.
- **Steps:** timeline header **Keys | Curves** → Curves shows the selected layers' animated settings as lines over
  time, each in its own colour, listed on the left (click to show only one). Drag keys and handles; box-select; F fits
  all curves in view.
- **Where and when:** the bar area of the timeline turns into the curve view; the layers list stays on the left.
- **Agent:** `key.handles`, `key.set`; `inspect_curve`.
- **3E:** *Effective:* the professional tool for fine timing. *Easy:* one switch, same place. *Rejected:* a separate
  floating window.

### Speed view · Later
- Curves ▾ › **Speed**: how fast each setting changes, for smoothing a move across several keys.

## 3.19 Timing

### Layer bars: when a layer shows · Now
- **Goal:** decide when each thing appears and goes.
- **Steps:** drag a bar to move the layer in time (its keys and drawings go with it; several selected bars move
  together); drag a bar's ends to change when it starts or ends (keys stay where they are). Bars snap to the playhead,
  markers, beats, other bars' ends and keys. Alt+[ / Alt+] trim the selected layers' start / end to the playhead.
- **Where and when:** every row's bar. A new layer starts at 0 and lasts the whole scene (Hem).
- **Feedback:** a label shows start and length while dragging ("1.20 s → 3.40 s").
- **Agent:** `layer.shift {by | to}`, `layer.trim {start | end}`.
- **3E:** *Efficient:* 1 drag replaces two number boxes (Hem). *Easy:* After Effects / Premiere habit.

### Slip: change which part plays · Next
- **Goal:** keep a video's or a frame-by-frame loop's bar where it is, but change which part plays.
- **Steps:** Alt+drag inside the bar → the content slides under the bar; a ghost shows the full content.
- **Agent:** `value.set {offset}`.

### Stagger · Next
- **Goal:** cards, letters of a logo or icons start one after another.
- **Steps:** select the layers (or their keys) → context bar **Stagger…** → a small popover: **Each starts [2 f]
  after the one before**, **Order: stack · as picked · left to right · top to bottom · from the centre · random** →
  bars and keys spread live as you change the number → click away to keep it.
- **Feedback:** live; the bars form a staircase.
- **Undo and adjust:** one step; open Stagger again to change it (it re-spreads from the first one).
- **Agent:** `layer.stagger {ids, by, order}`; picked keys: `key.stagger {by, order}` (H31).
- **3E:** *Efficient:* 1 action replaces dragging n bars by hand (Hem's F3). *Effective:* "from the centre" and
  "random" give the cascades top motion design uses. *Rejected:* stagger as an expression only.

### Markers and ties · Now
- **Goal:** time things to named moments ("logo lands", "drop") that every app shares.
- **Steps:** M (or the marker button in the timeline header) adds a marker at the playhead and lets you type its name
  at once (Enter keeps it). Drag a flag to move it; double-click to rename; right-click › Delete / Colour. **Tie:** drop
  a bar's start or end on a marker (it snaps) → it is tied: a small flag on the bar end; when the marker moves (here,
  in Sound or anywhere), the layer moves with it. Drag the end away to untie. Keys dragged onto a marker tie the same
  way (Next).
- **Shared or this scene's own** *(S30)*: M's name field has a **Shared** switch, on by default in a project. Shared
  markers are drawn solid with a small chain, this scene's own hollow; the same name for both is refused.
- **Where and when:** flags on the ruler's marker band; names shown above the ticks (never over the time labels: FINDINGS / H25).
- **Feedback:** tied ends show the marker's name on hover.
- **Agent:** `marker.add / move / rename / remove / colour`; `layer.shift {to: "#name"}`; key times `"#drop+0.2"`.
- **3E:** *Effective:* cross-app sync by name (rule 8). *Efficient:* tie by dropping, 1 drag (Hem: from 3 + a scroll).
  *Easy:* the flag on the bar shows what is tied.

### Timeline heights · Now
- **Goal:** the right room for the moment: all rows for timing, a big canvas for drawing.
- **Steps:** drag the timeline's top edge, or the **⊟** button at the header's right (full ↔ compact). Each tool
  remembers its own height (Move full, Paint compact).
- **Compact** shows the header, the ruler with markers, the sound row (if any) and the **selected layer's row**; its
  name is a menu of all layers.
- **3E:** Hem's design, kept: each moment gets its room without a page.

## 3.20 Type animation

### Letters, words and lines · Now
- **Goal:** text that builds letter by letter, word by word, line by line.
- **Steps:** animate the text as a whole (e.g. Y and Opacity keys) → open **Letters** in settings → **Spread over:
  Letters / Words / Lines**, **Delay** (between each), **Order: forward / backward / from the centre / random** →
  each letter plays the same keys, one after another.
- **Where and when:** the Letters group is offered on any animated text; it also appears in the context bar as
  **Animate letters** after you add the first key to a text (a hint where you are, gone once used).
- **Feedback:** the canvas replays the build when you change Delay.
- **Agent:** `value.set {letterSplit, letterDelay, letterOrder, letterSeed}`.
- **3E:** *Effective:* the core of kinetic type. *Efficient:* animate once, spread to all. *Easy:* "Spread over
  letters" is the idea in words. *Rejected:* After Effects' range selectors as the first step (powerful, famously
  hard; see Later).

### Letter ranges · Later
- **Goal:** a wave of weight through the word; a highlight sweeping across.
- **Steps:** Letters ▾ › **Add a range**: a band (start, end, softness) that moves through the letters; settings inside
  the band are changed (Weight 300 → 800). The band's position animates.
- **Agent:** `value.set {letterRanges}` *(new)*.

### Type that follows music · Next (with 3.28)
- Lyric or word timing: select a text → **Words to markers** (when Sound has word markers from a voice line) → each word
  appears on its marker. `text.words_to_markers` *(new)*.

## 3.21 Motion paths

### See and shape the path of a move · Next
- **Goal:** make a ball arc, not slide in a straight line.
- **Steps:** a layer whose position is animated shows its **path** on the canvas while selected: a thin line, a dot
  per frame (spacing shows speed), and a square per key. Drag a key square to move that key's position; drag from a
  square with Alt to pull curve handles. Click on the path to add a position key there.
- **Where and when:** for the selected layer(s) with animated position, with the Move tool.
- **Feedback:** the dots re-space live as you drag keys or change easing.
- **Undo and adjust:** one step per drag. **Make it straight** (right-click on a key square) removes the handles.
- **Agent:** `key.set {value, spatial_in, spatial_out}` *(new: spatial handles)*.
- **3E:** *Effective:* arcs are basic to good motion. *Easy:* see the path where the layer moves.

### Move along a path · Next
- **Goal:** an arrow that travels along a drawn curve; a car along a road.
- **Steps:** select the layer and the path → context bar **Move along path** → the layer sits at the path's start;
  **Along** (0–100 %, animatable) moves it; **Turn along its path** on / off.
- **Agent:** `value.set {followPath, along}` *(new; the same follow-a-path maths as text on a path)*.
- **3E:** *Efficient:* 1 action instead of keying positions point by point. *Easy:* the same gesture as Put on path.

### Orient along path · Next
- **Goal:** a paper plane that points where it flies.
- **Steps:** settings **Motion › Turn along its path** (on / off), **Extra turn**.
- **Agent:** `value.set {orientToPath}` *(new)*.

## 3.22 Follow (parenting) and rigs

### Follow another layer · Next
- **Goal:** a label that moves with its card without being grouped with it; a hat on a head.
- **Steps:** select the layers that should follow, then the one to follow **last** (Shift+click) → context bar
  **Follow *head*** → they move, turn and scale with it from now on, staying where they are now. A small chain icon on
  their rows shows it; right-click › **Stop following** frees them where they are.
- **Feedback:** hover the chain icon: a line on the canvas joins follower and leader.
- **Agent:** `layer.follow {ids, to}` *(new)* / `layer.unfollow`.
- **3E:** *Effective:* keeps the stack free (a hat above the head, a shadow below, both following). *Easy:* select
  first, then act; the leader is the last picked, which the context bar names. *Rejected:* the After Effects
  pick-whip drag (precise but fiddly at small sizes); grouping as the only way.

### Make rig · Now
- **Goal:** turn a character's parts into one puppet.
- **Steps:** select the parts (head, body, arms, mouths…) → context bar **Make rig** → a rig holding them, everything
  where it was. With one group selected (a PSD's parts arrive as one group), **Make rig** turns that group into the rig. With the rig selected, the **Bone** tool appears in the tool strip (3.23).
- **Agent:** `rig.make {ids}`.
- **3E:** select first, then act; no empty rig.

## 3.23 Character: bones, poses, swap sets, lip sync, blinks

### Bones and attaching · Next (H30)
- **Goal:** a skeleton that moves the parts.
- **Steps:** select the rig → the Bone tool (J) appears in the strip → click at the shoulder, click at the elbow, click
  at the wrist (each click a joint; Esc ends the chain; click an existing joint to branch). Parts attach by themselves
  to the bone they overlap most; to fix: select a part and a bone → **Attach to bone**.
- **Faster start (Next):** on a rig with no bones whose parts are named like a body ("upper arm L", "forearm",
  "hand", "thigh" …), the context bar offers **Bones from part names**: a skeleton is proposed at the parts' joints;
  drag any joint to fix it. (Adobe Character Animator's naming idea, done as a tool you can check.)
- **Where and when:** Bone tool only while a rig is selected or entered. Bones draw as thin tapered shapes over the
  picture; parts show a colour tint of their bone on hover.
- **Agent:** `bone.add`, `bone.remove`, `bind.add`, `bind.remove`, `rig.guess_bones` *(new)*; eyes `look_rig`.
- **3E:** *Effective:* the Moho / Harmony model. *Easy:* auto-attach does the right thing most of the time.

### Posing: drag the hand, pin the feet · Next (H30)
- **Goal:** pose by pulling the end, like a puppet.
- **Steps:** with the Move tool, when the rig is selected or you are inside it: drag a bone to turn it (FK); drag the end of a chain (a hand) and the
  chain bends to reach (animators call this IK); right-click a joint › **Pin** keeps it in place (feet on the floor). Poses key like any
  setting (K keys all bones).
- **Agent:** `ik.add`, `ik.remove`, `value.set` on bones; eyes `inspect_rig_motion`.
- **3E:** *Efficient:* one drag sets a whole arm.

### Pose library · Next (H30)
- **Goal:** reuse expressions and hand shapes.
- **Steps:** with a rig selected, settings **Poses** shows saved poses as small pictures. **Save pose** (from the
  current pose, optionally only the selected bones). Click a pose to apply at the playhead; drag its slider to blend
  partway.
- **Agent:** `pose.save`, `pose.apply {amount}`, `pose.remove`.

### Swap sets · Now
- **Goal:** one mouth, eye or hand drawing shows at a time.
- **Steps:** select the drawings → context bar **Make swap set** → settings **Showing** lists them as pictures; click
  one to show it (keyed, held until the next choice, when animated). Next: drag a new drawing onto the set to add it.
- **Undo and adjust:** one step; **Ungroup** gives the drawings back.
- **Agent:** `group.make {as: "swap"}`, `swap.show`.
- **3E:** *Easy:* pick by picture. *Rejected:* a group with a Swap switch found in its settings (today).

### Lip sync · Next (H30)
- **Goal:** the mouth matches the voice.
- **Steps:** select the mouth swap set → context bar **Lip sync…** → pick the voice line (the project's Sound items
  with voice; or a voice region by its markers) → a small table maps each mouth shape (A, E, O, M B P, F V, rest…) to a
  drawing in the set, guessed from their names and shown as pictures; fix any by clicking → **Apply** → keys on the
  set, held per sound.
- **Feedback:** play with the voice (3.28) and watch; the keys show on the set's bar labelled with the sound.
- **Undo and adjust:** one step; drag individual keys; run again to replace.
- **Agent:** `lipsync.apply {set, voice, map}`; eyes `inspect_lipsync`.
- **3E:** *Effective:* reads Sound's word timings (one source of truth), not a loose audio file. *Easy:* pictures, not
  phoneme codes.

### Blinks · Next (H30)
- **Steps:** select the eye swap set → **Add blinks…** → **How often** (seconds, with a little randomness), which
  drawing is "closed" → Apply → keys you can move.
- **Undo and adjust:** one step; drag single blink keys; run again to replace them.
- **Agent:** `blink.add`.
- **3E:** *Efficient:* a minute of blinks in one action, still editable keys.

### Bend weights · Later
- Paint how much each part bends with each bone (a weight brush shown only inside a rig).

## 3.24 Camera and depth

### Camera and the Camera tool · Now (layer) · Next (tool)
- **Goal:** push in, pan, tilt, with parallax.
- **Steps:** + › **Camera** (one per scene, so the + menu offers it only while there is none; it frames exactly what
  the scene showed, so nothing jumps). The **Camera
  tool** (C) appears in the strip once there is a camera: drag on the canvas to move the camera, Alt+drag up / down to
  move it closer / further, Shift+drag to turn it. Ctrl+wheel still zooms your view, never the camera, so looking
  closer never adds a key. Keys like any layer.
- **Where and when:** the camera's row is pinned at the top of the layers list; Camera tool only when a camera exists.
- **Feedback:** the canvas always shows what the camera sees (that is the export). With the camera selected, its whole
  move shows as a faint path.
- **Agent:** `layer.add {type: camera}`, `value.set` on camera fields.
- **3E:** *Easy:* moving the camera by dragging the picture is how people think of a camera move. *Rejected:* moving
  the camera only by numbers (today).

### Depth, focus and blur · Now (depth) · Next (focus by clicking)
- **Goal:** layers at different distances; a rack focus.
- **Steps:** each layer's **Depth** (in the Depth group; 0 = the screen plane, positive = further). With a camera:
  **Depth of field** on → **Focus on**: click the eyedropper and click a layer on the canvas to focus on it; key it to
  move the focus from one layer to another (a rack focus). **Blur amount**.
- **Agent:** `value.set {z, focus, aperture}`.

### Side view · Later
- **Goal:** see and set depths at a glance.
- **Steps:** view controls ▾ › **Side view**: the canvas shows the layers from above as lines at their depths, with the
  camera; drag a line to change its depth. Esc returns.

### Camera shake and keep in frame · Next
- **Goal:** handheld feel; keep a moving thing in frame.
- **Steps:** select the camera → context bar **Shake…** (amount, speed, fades in and out with the bar) or **Keep in frame…**
  (pick a layer; how loosely the camera follows it). Both write ordinary keys you can edit; run again to replace.
- **Agent:** `camera.shake {amount, speed}`, `camera.keep_in_frame {target, lag}` *(new)*.
- **3E:** tools that make keys (not a look preset); the result stays editable.

### Tilt (2.5D) · Now
- **Steps:** settings **Depth › Tilt across / Tilt up and down** and **Perspective** on groups. Next: on the canvas,
  Alt+drag a rotate handle tilts instead of turning.
- **Agent:** `value.set {tiltX, tiltY, perspective}`.

## 3.25 Look: fill, outline, effects, blend, colour

### Fill, outline and gradients · Now (settings) · Next (handles)
- **Goal:** colour a shape or text; gradients that look intentional.
- **Steps:** settings essentials: **Fill** (a swatch: click → the colour picker with an eyedropper, the project's
  colours, and **Solid / Linear / Radial / Conic**), **Outline** (colour, width; folded: dashes, ends, corners). For a
  gradient, its handles show on the canvas while the Fill picker is open: drag the ends, click the line to add a stop,
  drag a stop off to remove it.
- **Feedback:** live on the canvas.
- **Agent:** `value.set {fill, stroke, gradient}`.
- **3E:** *Easy:* gradient handles where the gradient is (Figma). *Rejected:* typing angles and stop positions.

### Effects · Now (blur, glow, shadow, frosted glass, trail, smear) · Next (grain, displace, distort, light wrap)
- **Goal:** glow on the landing beat; frosted glass behind a card; film grain.
- **Steps:** select one or many layers → settings **Effects (n) +** → a short list by name with a one-line description
  each ("Frosted glass: blurs what is behind it") → the effect is added to **each** selected layer, open, with its few
  settings; drag effects to reorder; the eye turns one off; ⋯ › Remove.
- **Where and when:** the Effects group is always listed (folded, showing its count and +), so adding one is one click
  from any layer. Ctrl+K "glow" finds it too.
- **Feedback:** live; an effect that can't apply to this kind is not in the list (rule of individuality), with Ctrl+K
  saying why if searched ("Gradient: not on pictures").
- **Undo and adjust:** one step per add / change; every effect setting has a diamond.
- **Agent:** `effect.add {targets, kind}`, `effect.remove`, `value.set`.
- **3E:** *Effective:* the effects motion design actually uses, each a tool with its own settings. *Easy:* one name per
  effect (FINDINGS: "Backdrop" vs "Frosted glass"). *Rejected:* effects only in Ctrl+K (today); an effects browser
  with looks (taste).

### Effects on the whole picture · Next
- **Goal:** grade or grain the whole shot.
- **Steps:** nothing selected → settings **Effects +** applies to the scene's picture (after all layers).
- **Agent:** `effect.add {target: scene}`.
- **3E:** *Easy:* "nothing selected = the whole piece", again. *Rejected:* adjustment layers (another kind of layer
  to learn; groups and the scene cover the need).

### Blend modes and colour adjust · Now
- **Steps:** settings **Look › Blend** (16 + Add, by name, with a live preview as you move through the list),
  **Colour** group: Exposure, Contrast, Saturation, Temperature, Tint, Hue, then folded Curves, Levels, Look file (LUT).
- **Agent:** `value.set {blend}`, grade fields.
- **3E:** *Efficient:* preview while browsing blends (no pick-look-undo).

### Smears, trails and motion blur · Now
- **Steps:** smear and trail are effects (above). Motion blur: scene settings **Motion blur** (on, shutter in words:
  "Light / Film / Heavy" with the angle behind), and per layer **Motion blur: As the scene / Off**.
- **Agent:** `value.set {shutter, shutterSamples}`.

## 3.26 Expressions and links

### Link a setting to another · Now (operation) · Next (on screen)
- **Goal:** the shadow's opacity follows the card's; a dial turns as a bar fills.
- **Steps:** right-click a setting › **Link to…** → the pointer becomes a link pointer → click the setting to follow
  (in the panel of another layer, or its row in the timeline) → the field shows a link chip "= card · Opacity" with
  **× 1** and **+ 0** you can edit. Or drag a setting's name onto another setting's name.
- **Feedback:** the linked field shows the chip instead of a number; a canvas drag on a linked value is refused in
  words ("Opacity is linked to card: unlink it to change it here").
- **Undo and adjust:** one step; **Unlink** (on the chip) keeps the current value.
- **Agent:** `link.set {field, from, scale, offset}`.
- **3E:** *Effective:* PLAN's "links between values". *Easy:* click the source, no syntax. *Rejected:* typing the
  link as an expression only (today).

### Expressions · Now
- **Goal:** a little code on one setting: wiggle, follow a marker, loop.
- **Steps:** in any number field type `=` → the field becomes a code line with name suggestions (other layers, their
  settings, `marker("drop")`, `noise`, `time`, `loop`, and `beat` / `pulse()` when Sound has a tempo) → Enter. Errors show under the field in words ("No layer called
  'titel'. Did you mean 'title'?") and the field keeps its last good value until fixed.
- **Undo and adjust:** one step; the × on the code line removes it and keeps the current value.
- **Agent:** `expr.set`, `expr.clear`.
- **3E:** *Efficient:* `=` is the spreadsheet habit; no menu needed. *Easy:* suggestions as you type. *Rejected:*
  a separate expression editor window.

## 3.27 Reuse: symbols, styles, saved motions, the library, repeat

### Symbols · Next
- **Goal:** one button design used twelve times; a lower third made once and used with different names; a scene
  inside a scene.
- **Steps:** select layers → context bar **Make symbol** (Ctrl+Alt+K) → they become one symbol; the original becomes
  its first **copy**. More copies: Alt+drag, Ctrl+D, or drag the symbol from the library. **Edit the symbol:**
  double-click a copy → you are inside it (the path shows `Main › Button`); changes show in every copy. **Change one
  copy:** select it → settings show the symbol's **changeable settings** (its texts, colours and swap choices; the
  maker marks which, by right-click › **Changeable in copies**) plus the copy's own **Start**, **Speed**, **Loop** and **Time** (keyable, Next: freeze, reverse or ramp the symbol's own time).
  **Detach** turns a copy back into plain layers.
- **Where and when:** a copy's row shows a symbol icon; its bar shows the symbol's own length (loop marks if looping).
- **Feedback:** while editing a symbol, other copies update live; outside, a copy with changes shows a dot by the
  changed setting, with **Reset** on hover.
- **Undo and adjust:** every step is one change; editing inside a symbol is undone like any other change.
- **Agent:** `symbol.make {ids}`, `symbol.place {source, at}`, `symbol.set {copy, field, value}`, `symbol.detach`
  *(all new)*; Make symbol on a scene's layers from another scene is `symbol.place {source: scene}`.
- **3E:** *Effective:* covers Figma's components, After Effects' precomps and Flash's movie clips with one idea: a
  piece with its own time. *Efficient:* change once, everywhere. *Easy:* one word, one icon. *Rejected:* separate
  precomps and components (two ideas for one need); nested comps without per-copy changes (forces duplicates).

### Colour and text styles · Next
- **Goal:** brand colours and type set once; change the brand blue everywhere.
- **Steps:** in any colour picker, **+ Save as style** names the colour; text: right-click a text › **Save type as a
  style**. Applying: the picker's **Styles** list; a text's **Style ▾**. Changing a style (in the library) changes every
  use. A field using a style shows the style's name instead of a number; **Detach** keeps the value.
- **Agent:** `style.define {name, values}`, `style.use {ids, name}` *(new)*; `style.apply` (copy / paste style).
- **3E:** *Effective:* real brand work. *Easy:* the Figma model.

### Copy and paste style · Now
- Select a layer → right-click › **Copy style**; select others → **Paste style** (fill, outline, opacity, blend,
  colour adjust, effects). Keys: Ctrl+Alt+C / Ctrl+Alt+V. `style.apply {from, ids}`.

### Saved motions · Later
- **Goal:** reuse your own animation (the way you bring cards in) on other layers.
- **Steps:** select keys → right-click › **Save motion…** (type a name in place) → later, select layers → library › Motions → click to
  apply at the playhead (relative: it moves from where each layer is).
- **Agent:** `motion.save`, `motion.apply` *(new)*.
- **3E:** tools, not taste: only motions people or agents saved themselves; none ship.

### The library drawer · Next
- **Goal:** find the project's pieces, brand kit, symbols, styles, brushes, saved motions, and outside assets.
- **Steps:** the **Library** button at the top of the tool strip (or Ctrl+L) opens a drawer on the left of the canvas
  (it pushes the canvas, never covers it). Sections: **This project** (scenes, 3D items, Sound items, files),
  **Symbols**, **Styles**, **Brushes**, **Motions**, **Brand kit** (your saved colours, fonts, logos, shared across
  projects), **Connectors** (Poly Haven, Freesound … only if switched on). Drag anything onto the canvas. **Filling the
  brand kit:** right-click a colour or text style, a font, or a logo layer › **Add to brand kit**, or drop files on the
  Brand kit section.
- **Where and when:** closed by default; remembers open / closed per project.
- **Agent:** the library is project data (`inspect_library`, `library.add` *(new)*).
- **Width:** 280 px. Drawers: Library 280, Guides 360, History 320. Below 1600 px wide only one drawer is open at a
  time, so the canvas keeps at least half the window.
- **3E:** *Easy:* one place for "things I can reuse". *Rejected:* a permanent left panel (Hem moved the layers list
  into the timeline to give the canvas width; a permanent library would take it back).

### What ships: tools, not templates · Now
- **Ships:** named sizes, the shared brushes (tools: shapes of marks, not finished looks), how-to guides for each tool
  (technique, with neutral examples), an empty project. **Never ships:** look presets, animated templates, finished
  pieces, story templates, "motion packs".
- **For agents:** the same: guides, `inspect_tools`, look tools. Agents build from operations; they never start from a
  template.
- **3E:** *Effective:* the reference bar is reached by craft, and templates make every piece look the same (Sam's rule).

### Repeat · Next
- **Goal:** a row of dots that light up one after another; a ring of petals; copies along a path.
- **Steps:** select a layer (or a group) → context bar **Repeat** → copies in a row; settings **Repeat**: **Arrange:
  Row / Grid / Circle / Along a path**, **Count**, **Spacing**, and **Each copy changes by** (position, rotation, scale,
  opacity, time offset), each animatable. Edit the original; every copy follows. **Make into layers** bakes them.
- **Agent:** `repeat.make {id, arrange, count, step}` *(new)*.
- **3E:** *Effective:* Cavalry's duplicator is how procedural motion design is done. *Efficient:* one setting
  instead of n copies. *Undo and adjust:* **Make into layers** (`repeat.bake` *(new)*) is one step like any other.

## 3.28 Sound and music

### Hear the project's sound · Now (H31)
- **Goal:** time to music and voice by ear.
- **Steps:** when the project has sound (a RostrumSound item, a placed sound file, a video's own sound), a **Sound
  row** appears at the bottom of the layers list with its waveform. Play plays it in sync; dragging the playhead scrubs
  it. The 🔊 button in the timeline header mutes it (2D only, not the project). **Scene settings › Soundtrack** picks
  which Sound item plays (the project's main mix by default). **Open in RostrumSound** on the row's right-click.
- **Where and when:** the row exists only when there is sound.
- **Feedback:** waveform; markers from Sound on the ruler.
- **Agent:** `comp.set {soundtrack}` (the scene field; as built in H31) and `inspect_soundtrack` (what plays, its length, tempo, bars, markers); eyes from Sound's tools.
- **3E:** *Effective:* the one audio engine renders it (rule 9), so what you hear in 2D is the mix. *Rejected:* a 2D
  audio engine (a second engine to keep in step), or no sound at all (today: timing to music blind).

### Beat grid · Now (H31)
- **Goal:** land things on the beat.
- **Steps:** when Sound has a tempo map, the ruler's ▾ › **Show beats** draws faint beat lines and bar numbers;
  snapping includes beats (bars stronger). Shift+`,` and Shift+`.` jump to the previous / next beat.
- **Agent:** key times can be written as beats `"bar 5"` *(new form)*.

### Sync sound · Next
- **Goal:** a video's own sound; a click tied to a button press.
- **Steps:** a video's sound plays as a sub-row tied to its bar (moves with it). A one-off cue: drag a sound file onto
  a layer's bar → it is tied to the layer's start (Sound places and renders it). Everything else (music, voice, sound
  design) is made in RostrumSound; **Motion samples** export (3.30) lets Sound place whooshes where things move.
- **Agent:** `sound.cue {layer, file, at}` *(new; stored in Sound's document)*.
- **3E:** follows rule 9 exactly.

## 3.29 Preview and playback

### Play, loop, step, scrub · Now
- **Goal:** watch it, again and again.
- **Steps:** Space plays / pauses; playing loops over the **time range** (drag on the ruler's top band to set it;
  right-click a bar › **Play only this layer's time**; Shift+I / Shift+O set its start / end at the playhead; double-click the band
  to clear; **⟳ Loop, Shift+L**, turns looping on and off *(S30)*). Shift+Space plays from the selection's start. Drag the playhead to scrub. Ctrl+← / → step one frame, Ctrl+Shift+← / → ten; Home / End go to the start /
  end; `,` and `.` jump to the previous / next key, marker or drawing of the selection (of everything when nothing is
  selected). The time in the header: click to type a time (seconds, frames or a marker name).
- **Feedback:** the playhead moves; if playback can't keep up, Auto preview size drops to Half and a small "Half" label
  shows; if it still can't, the header shows the real frame rate in amber.
- **Agent:** none (agents look with `look_frame`, `look_sheet`, `look_motion`).
- **3E:** *Easy:* Space is universal. *Efficient:* loop a layer in one click.

### Hide the panels · Now
- Ctrl+\ hides the settings panel and folds the timeline to its header; Ctrl+\ again brings them back. Escape does not
  (it is busy clearing selections). For watching and for drawing on a small screen.

## 3.30 Export

### Export panel · Now
- **Goal:** the right file, fast, where you can find it.
- **Steps:** **Export** (top bar, Ctrl+E) → the settings panel's place is taken by the export sheet (the canvas stays
  visible) → **What for** as a short list, each with its file type: **Video (MP4)**, **Video with transparency**
  (Format: **ProRes 4444** for editing, the default, or **WebM** for the web), **GIF**, **Image sequence (PNG)**, **For the Editor (EXR)**, **Lottie (for apps and the
  web)**, **Still image (PNG) of this frame**, **Motion for Sound** → only the settings for that choice appear (MP4:
  Quality Standard / High / Best; GIF: colours, size; PNG: 8 / 16 bit) → **Range: whole scene / time range / marker to
  marker** → **Size: 100 % / 50 % / other** → **Save to** (the project's Renders folder by default; Choose… once,
  remembered) → **Export**.
- **Where and when:** the sheet closes when you start the export (it runs in the background through the jobs queue);
  Esc closes it without exporting. Lottie lists, before you export, what it can't carry in this scene ("2 effects, 1
  painted layer"), in words.
- **Feedback:** progress in the top bar ("Exporting Main.mp4 · 42 %"); when done: "Exported · **Show in folder** ·
  **Play**". A failure says what failed, never a broken file with success (rule 6).
- **Undo and adjust:** export is not a document change. An existing file is never replaced without asking (Replace /
  Keep both / Cancel).
- **Keys:** Ctrl+E; **Ctrl+Shift+E export again** with the last settings, no sheet.
- **Agent:** `render_export {format, range, size, quality, path, overwrite}`, `render_video`.
- **3E:** *Effective:* every delivery format the pipeline needs. *Efficient:* 3 clicks the first time, 1 key after.
  *Easy:* purposes in words with the format behind, files in a folder you can see. *Rejected:* an export panel over
  the canvas (today: covers the title at 1280 px); format names only.

## 3.31 Undo, history and versions

### Undo and redo · Now
- **Goal:** take back a mistake.
- **Steps:** Ctrl+Z / Ctrl+Shift+Z (Ctrl+Y too); the ↶ ↷ buttons in the top bar appear only when they can act, with
  the step's name on hover ("Undo: Move title").
- **Where and when:** Undo takes back **your** last step only. If someone else has since changed the same thing, it
  changes nothing and says so ("Can't undo 'Move title': Claude changed it since. Undo that first, in History.") *(S30)*.
  Also: an agent's steps are undone from the History drawer or
  its review strip (3.34). Every gesture is one step (a drag, a typed value, a stroke, an action).
- **Feedback:** the top bar's message says what was undone ("Undid: Move title"); the selection returns to what it was.
- **Agent:** `undo` / `redo` (its own steps), shared history.
- **3E:** *Easy:* one gesture = one step, never half a drag. *Rejected:* one shared undo stack (pressing Ctrl+Z would
  undo the agent's work under you).

### History drawer · Next
- **Goal:** see who changed what, and take back one thing that is not the last.
- **Steps:** click the top bar's **N changes** or its message (or Ctrl+H) → a **sheet in the right column, in the settings
  panel's place** *(S30: was a drawer)*, lists steps newest first, grouped by who
  (You, Claude, a script), each with a name and, on hover, a before / after picture of the affected area. **Undo this**
  on any step takes back just that step if nothing later depends on it (else it says which later step depends on it).
- **Agent:** `history.list`, `history.undo {step}` *(new: undo a chosen step)*.
- **3E:** *Effective:* safe to let an agent work. *Easy:* pictures, not only names.

### Versions · Next
- **Goal:** keep "the one I showed the client" and go back to it.
- **Steps:** Ctrl+S → **Save a version**: name it (default: the time) → listed at the top of the History drawer.
  **Open** a version to look at it (read-only, with a banner), **Restore** it (a new step that brings everything back;
  nothing is lost), **Duplicate as a new scene**. Rostrum also keeps an automatic version each day you work. Naming happens in place in
  the drawer (no dialog).
- **Agent:** `version.save`, `version.restore`, `version.to_comp` *(new)*.
- **3E:** gives Ctrl+S a real meaning in an app that saves everything by itself. *Rejected:* Ctrl+S doing nothing.

## 3.32 Files, saving and recovery

### Saving is automatic · Now
- Every change is saved as it happens (PLAN: files hidden, saving automatic). The top bar says **Saved** after each
  change. There is no "unsaved" state, no Save As (Duplicate project, from ≡, makes a copy). Projects live in the
  user's Rostrum projects folder; ≡ › **Show project folder** opens it. Agent: `project.duplicate` (project service).

### Recovery · Now
- If the app stops, the launcher shows one plain sentence and where the log is (S27); opening again returns to exactly
  the last step, with the same scene, selection and playhead. Nothing to recover by hand.

### Missing files and fonts · Now
- A missing picture or font shows in Problems (3.36) and on its layer's row (a small warning). **Find it…** relinks
  every layer using that file at once (`asset.relink` *(new)*); a missing font offers **Use another font** (a list) or installs from the brand
  kit.

## 3.33 Help and learning

### Hover names, key list, guides · Now
- Every button has a hover name with its shortcut after 0.5 s. Ctrl+/ opens the key list (searchable, grouped by
  job). **?** in the top bar: **Guides** (also **F1**, S30) (the how-to guides, searchable, opened in a side drawer next to the canvas so
  you can follow along), **Shortcuts**, **Connect an AI agent**, **Report a problem** (opens the log folder and copies
  the version).
- **3E:** *Easy:* help sits where you are working; nothing pops up uninvited. *Rejected:* a first-run tour (people
  skip it, then the hints are gone).

## 3.34 Working with an agent

### Connect an AI agent · Now
- **Goal:** let Claude (or another agent) work in Rostrum2D.
- **Steps:** ? › **Connect an AI agent** → a short sheet lists the AI apps found on this computer, each with **Connect**
  (or the one command to paste, shown in the code font) → done once per AI app (S25).
- **Feedback:** the sheet says "Connected" per app; the agent chip appears the first time an agent works.
- **3E:** *Easy:* one button per app; nothing to configure.

### Live changes that never move you · Now
- **Goal:** watch the agent work without losing your place.
- **Steps:** none: when an agent changes the document, the canvas and rows update live. Your selection, playhead,
  zoom, scroll, open groups and the field you are typing in **never change** because of the agent. If the agent removes
  a layer you had selected, it simply leaves your selection.
- **Where and when:** while an agent works, the top bar shows a chip **Claude is working · 6 changes**; layers it changed
  in the last minute get a small dot on their row; the canvas outlines a changed layer briefly (1 s, S30) the first time.
- **Agent:** all operations; it is named in every step it makes.
- **3E:** *Easy:* nothing jumps. *Rejected:* follow-the-agent (moving the person's view to the agent's change: steals
  the screen).

### The agent's run as a group · Next
- **Goal:** keep or drop what the agent did, all at once or one by one.
- **Steps:** when the agent finishes a run (or pauses for 5 s), the chip becomes **Claude: 12 changes · Review · Undo
  all**. Review opens the History drawer filtered to that run: each step with before / after, **Undo this**; **Keep**
  closes the review.
- **Agent:** runs are named by the agent (`run_script` or a group of `edit_document` calls).
- **3E:** *Effective:* trust. *Efficient:* one click to take it all back. *Easy:* a single place to look.

### Your edits win · Now
- If you change a setting and the agent's script is run again, your change stays (rule 3). If the agent tries to change
  a layer you locked, or a value you set after its last look, the operation is refused **to the agent** with the reason
  ("Sam changed title.Y at 14:02; look again before changing it"). You see nothing unless you open the run's review,
  where it is listed as "Not changed: you had changed it".
- **3E:** the person never has to defend their work.

### The agent sees what you see · Next
- **Goal:** say "make **this** warmer" and mean the thing you selected.
- **Steps:** none: the agent can read your selection, playhead, time range and open scene through `inspect_screen`
  *(new)*. Right-click › **Copy for an agent** *(S30)* copies a short reference ("2D · Spring launch › Main › title ·
  2.40 s") to paste into the AI app.
- **3E:** pointing beats describing.

### Built-in AI panel and variations · Later
- An AI panel inside the app with the selection as context; **Make variations** (3 takes as alternate scenes you flip
  between). Later, because today the agent lives in the person's AI app and reaches 2D through its server.

## 3.35 Notes: directions on the picture

### Paint-over notes · Next
- **Goal:** direct by pointing and scribbling, at a moment, the way a director marks a frame.
- **Steps:** N (Notes tool) → draw or write on the canvas (a red marker by default) and type a line ("push this
  pose", "darker here") → the note is pinned to this place and **this stretch of time** (the time range, or ±0.5 s). Notes
  show as small pins on the ruler; click one to jump there. **Resolve** hides it (kept in history).
- **Where and when:** notes show only while the Notes tool is on or the 💬 toggle in the view controls is on; they
  **never export**, and they are not layers (they are not in the timeline rows).
- **Agent:** `look_notes` *(new)* gives the agent each note's marks drawn over the frame, its words, place and time;
  `note.resolve` *(new)*. PLAN tool 20.
- **3E:** *Effective:* the agent knows exactly where and when. *Efficient:* scribble beats typing a description of a
  place. *Easy:* a marker on a frame needs no explanation.

## 3.36 Problems

### Problems list · Now
- A **Problems** chip appears in the top bar only while something is wrong ("2 problems"). Click → a short list in
  words, each with what to do: "Font 'Söhne' is missing · Use another font", "title is never seen (it ends before it
  appears)", "Logo mask points at a layer that was deleted". Click an item to select the layer and jump to the moment.
- **Agent:** `inspect_diagnose`.
- **3E:** *Easy:* gone when nothing is wrong (rule of individuality).

## 3.37 Command search and finding a setting

### Ctrl+K: every action, setting and how-to · Now
- **Goal:** do anything by name.
- **Steps:** Ctrl+K → type → results in three groups: **Do** (actions valid for the current selection, applied to
  **all** selected layers: fixes FINDINGS 1.2), **Go to a setting** (opens its group in the panel and puts the cursor
  in it), **Learn** (guide sections, Next). An action that is not valid now is not listed; if you typed its exact name,
  one line says why ("Combine needs two or more shapes selected").
- **Keys:** Ctrl+K; ↑ ↓ Enter.
- **Agent:** the same list is the agent's `inspect_tools`.
- **3E:** *Efficient:* pros never leave the keyboard. *Easy:* beginners find what they can't see.

### Ctrl+F: find a setting · Now
- Typing in the settings panel's **Find a setting** shows every matching setting of the selection, from any group, open
  and editable; Esc clears. Words people use find the right setting ("transparency" → Opacity, "trim" → Draw from / to).

---

# Part 4 · The screen

## 4.1 Regions

| Region | Where | Always there | What it holds |
|---|---|---|---|
| **Top bar** | the top row, 44 px | yes | ≡ menu · project › scene ▾ · the message (what just happened) · **Saved · N changes** (never cut; a click opens History) *(S30)* · agent chip (while an agent works) · Problems chip (while something is wrong) · export progress (while exporting) · ↶ ↷ (when they can act) · Search Ctrl K · **Export** · ? |
| **Tool strip** | floating on the canvas's left edge: 40 px wide, 8 px in (56 px kept clear) | yes | Library · Move V · Shape R/O ▾ · Pen P ▾ · Text T · Paint B · then tools that appear: Camera C (a camera exists), Bone J (a rig selected), Notes N · and at the bottom **+** (Add from a file… *(S30)*, From Figma…, Camera while there is none, 3D render with Rostrum3D, a Symbol from the library) |
| **Context bar** | floating, top-centre of the canvas, one row | when there is something to say | With Move and a selection: what is selected ("3 layers") and the actions it allows, most used first, the rest under ⋯. With another tool: that tool's few options. With nothing to say: hidden. Hidden while dragging. |
| **Canvas** | the middle | yes | The frame at the playhead, exactly as exported; handles, guides, motion paths, onion skin, notes. Bottom-left: the group path when inside a group. Bottom-right: view controls (Fit · zoom % ▾ · preview size · Fast/Final · notes toggle). |
| **Settings panel** | right, 296 px (drag its edge: 256–420) | yes (folds away with Ctrl+\) | The header (name, kind or "3 layers", Find a setting), the essentials, the folded groups, Effects (n) +. With nothing selected: the scene. With Paint: Brush, then Paint on <element>. While exporting: the export sheet. |
| **Timeline** | bottom, full width | the header and ruler always | Header: ▶, time, play-range toggle · the key bar or frame tools when they apply · marker button, Keys / Curves (once something is animated), 🔊 (when there is sound), ⊟ full / compact. Ruler with markers (and beats). Rows: layers list on the left (name, eye, lock), bars and keys on the right. The Sound row last. |
| **Drawers** | left (Library 280 px, Guides 360 px) | no | Open from the tool strip or Ctrl+L (Library), ? or F1 (Guides). History and Export open as **sheets in the settings panel's place** *(S30)*. A drawer pushes the canvas aside; it never covers it. One drawer per side; below 1600 px wide, one drawer at a time. |

## 4.2 What shows when

| Tier | What | Why |
|---|---|---|
| **Always** | Top bar; tool strip (base tools); canvas; settings panel (scene settings when nothing is selected); timeline header and ruler | Every job ends in the picture, plays it, and needs project-wide actions (Export, Undo, Search). |
| **With a selection** | Handles; the context bar's actions; the settings of the selection; highlighted rows and bars; motion path (animated position); the group path (inside a group); kind-specific tools: Bone (rig), Camera tool (camera), frame tools (frame-by-frame), Replace (picture), Paint on (painted element) | Rule of individuality, driven by the one action list and each setting's "valid when". |
| **With a tool** | Pen: the "click / drag / close" line and Close, Done · Paint: brush, size, opacity, colour, eraser, painting on · Text: font, size, weight, colour while typing · Shape: the shape list · Notes: marker colour, Resolve · Camera: Reset view to camera | A tool's options belong with the tool. |
| **With keys selected** | The key bar in the timeline header (ease, curve chip, time and value for one key) | Easing is chosen while looking at the keys. |
| **On hover** | Hover outline on the canvas (what a click picks); eye and lock on rows; diamonds stay visible (not hover-only); gap handles in auto layouts; hover names with shortcuts; history before / after pictures | Previews of what a click would do. |
| **One click away** | + menu; Library; Ctrl+K; Find a setting; the folded groups; Curves; right-click menus; the History drawer; Guides; the scene list; view controls menus; Export | Used at a moment, not all the time. |
| **Gone (compared with today)** | Design / Draw / Animate pages; the separate Layers panel; + Add's Group / Rig / empty containers; the separate Import button; the More row; the key replacing the settings panel | Each split one job, doubled a list, made things backwards, or meant nothing to a person. |

## 4.3 The context bar, in every state

The context bar shows the **five highest-ranked** actions this selection allows, then ⋯ for the rest in the same order.
Ranks come from the one action list (`apps/2d/screen/screen2d/actions.py` on `team/hem`), so the context bar,
right-click and Ctrl+K always agree. Some selections **promote** the action they most likely want to the front (column
"Promoted when").

| Selection (Move tool) | Context bar, in rank order (first five shown) | Promoted when | Under ⋯ |
|---|---|---|---|
| nothing | hidden | — | — |
| one shape or path | Mask ▾ (with Draw a mask) · Repeat · Make symbol · Align to frame ▾ | — | Copy style, Lock, Hide, order *(S30: Duplicate and Delete are keys and right-click only)* |
| one text | Animate letters (once it has a key) · Make symbol · Mask ▾ · Align to frame ▾ | — | as above |
| one picture or video | Replace… · Fill the frame · Crop · Mask ▾ · Make symbol | — | as above |
| one drawing | Set depth ▾ (with a camera) · Mask ▾ · Make symbol | — | as above |
| 2+ layers | Group · Mask ▾ · Align ▾ · Distribute ▾ (3+) · Stagger… | all shapes → **Combine ▾** first · one is a path → **Put on path** (a text) or **Move along path** first · all drawings or pictures → **Make swap set** first · the last picked is named → **Follow *x*** | Make symbol · Auto layout · Make rig · Clip · Make swap set · Follow *x* · Match size · Paste style · Lock, Hide, order |
| one group | Ungroup · Make rig · Auto layout · Clip · Make symbol | parts named like a body → **Make rig** first | as above |
| a rig | Bones from part names (no bones yet) · Poses ▾ · Make symbol | — | as above |
| a swap set | Lip sync… · Add blinks… | — | as above |
| a camera | Shake… · Keep in frame… · Focus on ▸ | — | Lock, Hide |
| a mask group | Release mask · Mode ▾ | — | as above |

| Tool | Context bar |
|---|---|
| Pen | Click: corner · Drag: curve · Click the first point to close · **Close path** · **Done** |
| Editing points | **Smooth / Corner** · **Delete point** · **Done** |
| Text, while typing | Font ▾ · Weight ▾ · Size · Colour ■ · **Done** |
| Paint | brush ▾ · Size · Colour ■ · Opacity · Eraser E · Painting on: *x* ▸ |
| Paint, strokes selected | *12 strokes* · Move to depth ▾ · Copy · Delete · **Done** |
| Notes | Marker colour ■ · Write a note… · Resolve |

**When the bar is too wide** (at 1280 px, the Paint bar), the lowest-ranked items move under ⋯ one by one; for Paint,
Opacity then Eraser fold first, and Size and Colour never do. The bar never wraps to two lines and never covers the
tool strip.

## 4.4 The settings panel, per kind

The panel is built from data (each setting's group, importance and "valid when"), never by hand. Pairs share a row.
Every group not listed in Essentials is folded to its name; the panel remembers which groups you opened.

| Kind | Essentials (always open, in this order) | Folded groups (only those that apply) |
|---|---|---|
| Text | Text · Font · Weight · Size · Colour · Align · X Y · Scale · Rotation · Opacity | Spacing · Type features · Letters · Path · Outline · Look · Colour adjust · Effects (n) + · Depth · Motion · Timing |
| Shape | Fill · Outline · W H · Corners · X Y · Rotation · Opacity | Paint · Look · Colour adjust · Effects · Depth · Motion · Timing |
| Path | Fill · Outline · Draw from / to · X Y · Rotation · Opacity | Line (ends, taper, width) · Paint · Look · Colour adjust · Effects · Depth · Motion · Timing |
| Picture | Fit · W H · X Y · Rotation · Opacity | Crop · Paint · Look · Colour adjust · Effects · Depth · Motion · Timing |
| Video | Speed · Loop · W H · X Y · Opacity | Same as picture, plus Start at |
| Drawing | Paint (layers, Draw each frame) · X Y · Scale · Rotation · Opacity | Onion skin (if drawing each frame) · Look · Colour adjust · Effects · Depth · Timing |
| Group | X Y · Scale · Rotation · Opacity | Layout (if auto layout) · Clip · Look · Effects · Depth · Timing |
| Symbol copy | Its changeable settings · Start · Speed · Loop · X Y · Scale · Rotation · Opacity | Look · Effects · Depth · Timing |
| Camera | Zoom · X Y · Rotation · Depth of field (on/off) | Focus (if on) · Motion blur · Timing |
| Rig | Poses · the selected bone's turn | Reach (pins, how limbs reach) · Timing |
| 3D render | Version · Speed · Loop · W H · X Y · Opacity | Same as picture |
| Several | The settings they share (Mixed where they differ); of different kinds, also a line per kind ("2 texts ›") that narrows the selection *(S30)* | The groups they share |
| Every kind | Last line: "Last changed by Claude, 3 min ago (Add glow)", click → History at that step *(S30)* | — |
| Nothing | Scene: Size · Length · Frame rate · Background | Timing (Steps) · Motion blur · Colour · Effects · Soundtrack · Layout grid |

Words: values in the words of the trade: Opacity **100 %**, Weight **Bold**, Motion blur **Film**, Anchor as a 9-dot
picker, Steps **On twos**, sizes **16:9 HD**. One spelling: **Colour**, **Centre** (FINDINGS 4.3).

## 4.5 Wireframes of the main states

*(At Sam's size, about 1646 × 900. The HTML version draws these to scale.)*

**W1 · A new, empty project**

```
┌ ≡ Rostrum2D │ Untitled › Main ▾ ················ Saved ·············│ Search Ctrl K │ Export │ ? ┐
├──┬──────────────────────────────────────────────────────────────────────┬─────────────────────────────┤
│📚│                                                                      │ Main · Scene                 │
│V │      ┌──────────────────────────────────────────────────────┐        │ Size   16:9 HD ▾ 1920×1080  │
│▭ │      │                                                      │        │ Length  10 s                │
│✒ │      │   Draw a shape (R), type (T), paint (B),             │        │ Frame rate  25 ▾            │
│T │      │   or drop a file here.                               │        │ Background  ■ none          │
│🖌 │      │                                                      │        │ ▸ Timing  ▸ Motion blur      │
│  │      └──────────────────────────────────────────────────────┘        │ ▸ Colour  ▸ Effects (0) +    │
│+ │                                                  Fit 52 % ▾  Full ▾  │                             │
├──┴──────────────────────────────────────────────────────────────────────┴─────────────────────────────┤
│ ▶ 0.00 s  ⟲ │                                                                      │ ◇ Marker  ⊟ │
│ LAYERS       │0s      1s      2s      3s      4s      5s      6s      7s      8s      9s             │
│              │  Your layers appear here as bars. Drag a bar to change when it shows.                 │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**W2 · One text selected, Move tool (the everyday state)**

```
┌ ≡ Rostrum2D │ Spring launch › Main ▾ ····· Saved · You: Typed text │ ↶ │ Search Ctrl K │ Export │ ? ┐
├──┬──────────────────────────────────────────────────────────────────────┬─────────────────────────────┤
│📚│             ┌ title · Animate letters  Make symbol  ⋯ ┐              │ title · Text                │
│V │      ┌──────────────────────────────────────────────────────┐        │ [Find a setting     Ctrl F] │
│▭ │      │                                                      │        │ Text   Spring launch        │
│✒ │      │              ╔══════════════════╗                    │        │ Font   Inter ▾  Weight Bold ▾│
│T │      │              ║  Spring launch   ║ ← handles          │        │ Size 120 px   Colour ■       │
│🖌 │      │              ╚══════════════════╝                    │        │ X 960  Y 540            ◇   │
│  │      │                                                      │        │ Scale 100 %   Rotation 0°◇  │
│+ │      └──────────────────────────────────────────────────────┘        │ Opacity 100 %           ◆   │
│  │                                                  Fit 52 % ▾  Full ▾  │ ▸ Spacing ▸ Type features   │
│  │                                                                      │ ▸ Letters ▸ Effects (0) +   │
├──┴──────────────────────────────────────────────────────────────────────┴─────────────────────────────┤
│ ▶ 2.48 s  ⟲ │                                                       │ ◇ Marker  Keys│Curves 🔊 ⊟ │
│ LAYERS        │0s      1s      2s ▼drop  3s      4s      5s      6s                                  │
│ T title   👁🔒│      ██████◆██████◆████████████████████████████                                      │
│ ▢ card        │████████████████████████████████████████████████████████████████                       │
│ 🔊 Music      │▁▃▅▇▅▃▁▃▅▇█▇▅▃▁▃▅▇▅▃▁▃▅▇▅▃▁▃▅▇▅▃▁▃▅▇▅▃▁▃▅▇▅▃▁▃▅▇                                   │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**W3 · Keys selected (the key bar)**

```
├───────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ▶ 2.48 s  ⟲ │ 2 keys · Ease: Ease out ▾  [╭─ curve ─╯]  Spring: Bounce ─●─ │ ◇ Marker Keys│Curves ⊟ │
│ LAYERS        │0s      1s      2s ▼drop  3s                                                         │
│ ▾ T title     │      ██████◆━━━━━━◆██████████████                                                    │
│     Y         │            ◆╭━━━━━╯◆           ← selected keys, the ease drawn between them           │
│     Opacity   │      ◆━━━━━◆                                                                         │
```

**W4 · Painting on a shape (Paint tool, compact timeline)**

```
┌ ≡ Rostrum2D │ Poster › Main ▾ ················· Saved · You: Stroke │ ↶ │ Search Ctrl K │ Export │ ? ┐
├──┬──────────────────────────────────────────────────────────────────────┬─────────────────────────────┤
│📚│ ┌ ▣ Dry brush ▾  Size ──●  Opacity ───●  ■  Eraser E  Painting on: Hill ▸ ┐ │ Brush             │
│V │      ┌──────────────────────────────────────────────────────┐        │ [▣][▣][▣][▣][▣][▣]        │
│▭ │      │        ░░▒▒▓▓  the hill shape, its paint inside      │        │ ▸ Shape ▸ Grain ▸ Pressure  │
│✒ │      │     ░▒▒▓▓▓▓▓▓▓▒▒░  its outline (dashed while painting)│        │ Paint on Hill               │
│T │      │  ░▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒░                                  │        │ Layers: Paint ●  + layer    │
│🖌◀│      │                                                      │        │ Keep inside outline  ● on   │
│  │      └──────────────────────────────────────────────────────┘        │ Draw each frame      ○ off  │
│+ │                                                 Fit 100 % ▾  Full ▾  │                             │
├──┴──────────────────────────────────────────────────────────────────────┴─────────────────────────────┤
│ ▶ 0.00 s  ⟲ │                                                      │ ◇ Marker  Keys│Curves  ⊞ │
│ ▢ Hill ▾      │████████████████████████████████████████████████████████████████████████████████████████│
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**W5 · Frame-by-frame (a drawing with Draw each frame on)**

```
├───────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ▶ 0.52 s  ⟲ │ ◀ ▶  New  Copy  Hold − +  Onion ● 1·1 ▾                │ ◇ Marker  Keys│Curves  ⊞ │
│ ✎ Smoke ▾     │[1 ][2 ][3   ][4 ][5 ][6     ][7 ][8 ]                                              │
│               │  ↑ each block is one drawing; its width is how long it is held                     │
```

**W6 · Several layers selected (select first, then act)**

```
│📚│        ┌ 3 layers · Group  Mask ▾  Align ▾  Distribute ▾  Stagger…  ⋯ ┐ │ 3 layers                  │
│V │      ┌──────────────────────────────────────────────────────┐        │ Fill  Mixed                 │
│  │      │   ╔════╗   ╔════╗   ╔════╗   ← one box around all     │        │ W 320  H Mixed              │
│  │      │   ║card║   ║card║   ║card║                           │        │ Y 540   Opacity 100 %   ◇   │
```

**W7 · A rig selected (character)**

```
│📚│               ┌ Max · Poses ▾  Bones from part names  ⋯ ┐          │ Max · Rig                   │
│V │      ┌──────────────────────────────────────────────────────┐        │ Poses                       │
│▭ │      │          (o_o)    bones drawn over the parts           │        │ [🙂][😮][😠][+ Save pose]    │
│🦴│ ←Bone│          /|\      drag a hand: the arm follows (IK)   │        │ Selected bone: forearm 32°  │
│T │      │          / \      pinned feet show a pin               │        │ ▸ Reach  ▸ Timing           │
```

**W8 · Exporting (the export sheet takes the settings panel's place)**

```
│📚│      ┌──────────────────────────────────────────────────────┐        │ Export                    × │
│V │      │                                                      │        │ What for                    │
│  │      │              (the canvas stays visible)              │        │ ● Video (MP4)               │
│  │      │                                                      │        │ ○ Video with transparency   │
│  │      │                                                      │        │ ○ GIF  ○ Image sequence     │
│  │      └──────────────────────────────────────────────────────┘        │ ○ For the Editor (EXR) …    │
│  │                                                                      │ Quality  High ▾             │
│  │                                                                      │ Range  Whole scene ▾         │
│  │                                                                      │ Save to  Renders ▾          │
│  │                                                                      │ [        Export        ]    │
```

**W9 · An agent at work, then its review**

```
┌ ≡ Rostrum2D │ Spring launch › Main ▾ ··· Saved · Claude: Added glow │ ● Claude is working · 6 changes │ ↶ │ … ┐
...
│ T title  •    │  ← a dot: the agent changed this row in the last minute
...
┌ … │ Claude: 12 changes · Review · Undo all │ … ┐   ← when the run ends
```

**W10 · 1280 × 720 (the smallest size)**

```
┌ ≡ │ Spring launch › Main ▾ ·· Saved │ ↶ │ 🔍 │ Export │ ? ┐   ← message shortened, search as its icon
├──┬───────────────────────────────────────────────┬────────────────────┤
│V │ ┌ title · Animate letters ⋯ ┐                 │ title · Text       │  settings 256 px
│▭ │   ┌───────────────────────────────────┐       │ Text  Spring…      │
│✒ │   │      frame at ~50 %               │       │ Font Inter ▾       │
│T │   └───────────────────────────────────┘       │ Size 120 Col ■     │
│🖌 │                                               │ X 960  Y 540   ◇   │
├──┴───────────────────────────────────────────────┴────────────────────┤
│ ▶ 2.48 s │ (compact by default under 800 px tall)        │ Keys│Curves ⊞ │
│ T title ▾ │      ██████◆██████◆█████████████                              │
└────────────────────────────────────────────────────────────────────────┘
```

## 4.6 Window sizes

The canvas must never drop below **half the window's width**, and the frame at Fit must stay at least **480 px wide**. The frame's Fit leaves room for the tool strip (56 px kept clear), the context bar (48 px) and the view controls (32 px), so they never sit on the picture at Fit.

| Window (screen points) | Settings panel | Timeline at start | Canvas (about) | Frame at Fit (16:9) | Notes |
|---|---|---|---|---|---|
| **1280 × 720** | 256 | compact (≈ 120) | 1024 × 556 | ≈ 846 × 476 at compact; ≈ 615 × 346 at full (250) | The top bar's message shortens first; search becomes its icon. Full timeline on demand. |
| **1366 × 768** | 264 | compact (≈ 120) | 1102 × 604 | ≈ 932 × 524 | Rows end on a whole row, never cut mid-row (FINDINGS 5). |
| **1440 × 900** | 280 | full (≈ 280) | 1160 × 576 | ≈ 882 × 496 | |
| **1646 × 900 (Sam)** | 296 | full (≈ 300) | 1350 × 606 | ≈ 935 × 526 (about half of 1920) | The reference size for looks. |
| **1920 × 1080** | 320 | full (≈ 340) | 1600 × 696 | ≈ 1095 × 616 | |
| **2560 × 1440** | 360 | full (≈ 420) | 2200 × 976 | ≈ 1593 × 896 | |

The timeline starts **compact when the window is under 800 px tall**, full otherwise; after that, each tool remembers the
height you gave it. Resizing the window never changes which tool or groups are open.

### The top bar never overlaps

Fixed order, left to right: ≡ · project › scene · **message** (flexible) · **Saved · N changes** *(S30)* · agent chip · Problems chip · export progress
· ↶ ↷ · Search · Export · ?. When the width runs short, things give way in this order and **never slide under each
other**: (1) the message shortens with "…" (hover shows all of it), (2) the project name shortens (the scene name
never does), (3) Search becomes its icon, (4) chips show only their dot and count. Saved · N changes, ↶ ↷, Export and ? never shrink.
Every state is checked automatically at 1280, 1366, 1646 and 1920 wide (the look-pass checker that found the old top-bar
overlap).

## 4.7 Every dialog, sheet and popover

Rostrum2D has **one blocking dialog** (Replace a file on disk, because it is outside the history) and **one first-time
question** (the Figma token). Everything else is a sheet or popover that leaves the canvas visible and never blocks
the rest of the screen.

| Name | Kind | Opens from | Contents | Closes |
|---|---|---|---|---|
| Start screen | full window | launch with no project; ≡ | New (named sizes), recent projects as pictures, Open, Guides | opening a project |
| Scene list | menu | the scene name | scenes with pictures, New / Duplicate / Rename / Delete | a pick, Esc |
| + Add menu | menu | + in the tool strip | Add from a file… *(S30)* · From Figma… · Camera (while there is none) · 3D render (with Rostrum3D) · Symbol ▸ | a pick, Esc |
| System file window | the operating system's own | Add from a file, Replace, Save to › Choose…, Find it… | files and folders | a pick, Cancel |
| Effects list | popover | Effects + | the effects that apply to this selection, each with a one-line description | a pick, Esc |
| Add progress / report | small panel, canvas right edge | placing a file | progress; "Placed …"; Show what didn't come across | itself after 3 s if clean; × |
| PDF pages | inline question in that panel | a multi-page PDF | This page / All pages as scenes | the answer |
| Figma token | small dialog, first time only | pasting a Figma link | where to get a token; the field; "never stored in the project" | OK / Cancel |
| Font list | popover | Font field | search, recent, brand, all; live preview | Enter / Esc / click away |
| Colour picker | popover | any colour swatch | picker, eyedropper, project colours, styles, gradient type | click away |
| Ease and spring | in the key bar | selecting keys | Ease ▾, curve chip, bounce / speed | deselecting keys |
| Stagger | popover | context bar | by how much, order | click away (kept) |
| Link to… | pointer mode | right-click a setting | click the source; Esc cancels | a click, Esc |
| Lip sync | popover | context bar on a mouth set | voice line, mouth-shape map with pictures, Apply | Apply / Esc |
| Add blinks | popover | context bar on an eye set | how often, closed drawing, Apply | Apply / Esc |
| Shake / Keep in frame | popover | context bar on a camera | amount, speed / target, how loosely | Apply / Esc |
| Export sheet | sheet in the settings panel's place | Export, Ctrl+E | what for, its settings, range, size, save to, Export | starting the export, Esc, × |
| Replace file? | **blocking dialog** | exporting onto an existing file | Replace / Keep both / Cancel | a choice |
| Library | left drawer | tool strip, Ctrl+L | project items, symbols, styles, brushes, motions, brand kit, connectors | the button again, Esc |
| History | sheet in the settings panel's place *(S30)* | the top bar's N changes or message, Ctrl+H | steps by who, before / after, Undo this, versions (Save a version names it in place) | the same, Esc |
| Save pose · Save motion | a name field in place (Poses group · the library) | Save pose · right-click › Save motion… | the name | Enter / Esc |
| Connect an AI agent | sheet | ? › Connect an AI agent | AI apps found, Connect per app | × |
| Guides | left drawer | ? › Guides, F1 *(S30)* | searchable how-tos | × |
| Key list | overlay | Ctrl+/ | searchable shortcut list by job | Esc |
| Problems | popover | the Problems chip | problems in words with fixes | click away |
| Ctrl+K | overlay at the top | Ctrl+K | Do / Go to a setting / Learn | Enter / Esc |
| Crash message | message from the launcher | a crash (S27) | one plain sentence, the log's place, Open again | a click |
| Preferences | dialog *(S30)* | ≡ › Preferences, Ctrl+, | pen pressure curve, scratch space cap, interface size, connected agents | × |

## 4.8 Hem's H28 draft: kept, changed, added

| Hem's H28 | Verdict | Why |
|---|---|---|
| One workspace, no pages | **Kept** | Right, and decided (PLAN). |
| Timeline = layers list with bars; two heights remembered per tool | **Kept** | Right. Added: compact by default under 800 px tall. |
| Animate in place with the diamond | **Kept**, diamonds always faintly visible (not hover-only) | Discoverable without a manual (FINDINGS 3.1). |
| Click a key → the settings panel shows the key | **Changed**: a key bar in the timeline header; the panel stays on the layer | You keep seeing the layer; many keys eased at once (FINDINGS 3.1, 2.14). |
| Action bar floating under the selection | **Changed**: one context bar at the top-centre of the canvas | Fixed place, never covers the art, never jumps or falls off-screen; also carries tool options, so there is one place for "what can I do now". |
| Action bar also above the settings | **Dropped** | Two places for the same actions. |
| "Comp" as the word on screen | **Changed (S30): Scene**, on every screen and in every guide (`comp.*` operation names kept) | PLAN › Decided 2026-10-22: plain word, and the Editor uses "Comp" for its compositing page. |
| One action list for bar, right-click, Ctrl+K, shortcuts | **Kept** | The core of select-then-act. Extended (Follow, Put on path, Stagger, Repeat, Make symbol, Lip sync, Blinks, Replace, Draw a mask). |
| + Add, Import, Export in the top bar | **Changed**: + Add in the tool strip (one door for files and drops; S30: named Add, not Place); Export stays in the top bar | One door; creation beside the canvas; a shorter top bar that cannot overlap. |
| Change count in the top bar | **Kept** *(S30, was Dropped)*: "Saved · N changes", never cut, click → History | Proof that every step is recorded and can be taken back, and the door to History (shared spec 1.14). |
| Settings panel: essentials, folded groups, search, several selected = Mixed | **Kept** | Right. Added: pairs on one row, words of the trade, Effects (n) + always listed. |
| Draw tool B with brush in the settings panel | **Kept and extended**: Paint on any element; quick controls in the context bar; brush library and the element's paint in the panel | PLAN's painting model; painters' controls near the hand. |
| Tool strip Move / Pen / Draw | **Extended**: Shape, Text, Library, +, and tools that appear with their thing (Camera, Bone, Notes) | Creation in one place; tools only when usable. |
| Click picks outer group, double-click in, Ctrl+click deepest | **Kept** | Figma's proven rule. |
| Arrows nudge | **Kept and generalised**: arrows move the selection in the place you work (canvas: space; timeline: time); Ctrl+arrows step the playhead | One rule covers both. |
| Drag feel: overlays drawn from the shown picture's state | **Kept** | The right base fix; budgets in 6.1. |
| Agent edits never move the person | **Kept**; added the review group, per-run Undo all, dots on rows, Notes, `inspect_screen` | Collaboration needs review and pointing, not only non-interference. |
| Make rig, Make swap set from a selection | **Kept** | Select first, then act. |
| Later list (music, parenting, live booleans, history by who) | **Pulled forward**: music and history are Next, not Later | Timing to music and trusting an agent are core jobs, not extras. |

---

# Part 5 · Ten real jobs, from an empty project to an export

**How clicks are counted:** one click, one drag, one key press, or typing one value (a word, a number, a name) counts as
**1**. Pressing Enter after typing counts separately. Moving the playhead by clicking the ruler counts 1. Painting
strokes are not counted (they are the work itself). The route is the one a person would take on their first good day:
visible buttons, plus the shortcuts named on them. F4, F7 and F8 start from a project that already holds RostrumSound's
voice or music (made in that app, rule 9); F7's layers were made as in F1–F3. "Today" says what the current screen (main plus Hem's H28 in
progress) can't do or does with more steps.

## F1 · Type animation: "Spring launch" rises in letter by letter and cuts out on the "out" marker (Maya)

| # | Step | Action | Count |
|---|---|---|---|
| 1 | New project | Start screen › **New** · 16:9 HD is chosen · **Create** | 2 |
| 2 | Add the title | **T** · click on the canvas · type "Spring launch" · Esc | 4 |
| 3 | Font and weight | Font field · pick **Inter** in the previewing list · Weight ▾ · **Bold** | 4 |
| 4 | Centre it | Drag it until it snaps to the centre lines | 1 |
| 5 | End pose | Click the ruler at 1.2 s · Y diamond · Opacity diamond | 3 |
| 6 | Start pose | Click the ruler at 0.5 s · drag the title down on the canvas (adds a Y key) · Opacity field · type 0 | 4 |
| 7 | Letter by letter | Context bar **Animate letters** (opens Letters, Delay 0.03 s) · Delay field · type 0.04 | 3 |
| 8 | Ease | Drag a box over the four keys · Ease ▾ · **Ease out** | 3 |
| 9 | The "out" marker | Click the ruler at 4 s · **M** · type "out" · Enter | 4 |
| 10 | Cut on "out" | Drag the title bar's end onto the "out" flag (snaps and ties) | 1 |
| 11 | Watch | Space | 1 |
| 12 | Export | **Export** · Video (MP4) is chosen · **Export** | 2 |
| | | **Total** | **32** |

With the marker already made in Sound, 28. **Today:** no text tool (+ Add, then type in the panel), no font list, no
"Animate letters" hint, easing one key at a time with the panel swapping to the key, tying by a setting deep in Timing
(FINDINGS 3.1).

## F2 · Logo reveal: outlines draw on one after another, the fill wipes in, a glow, a springy settle, exported with transparency (Maya)

| # | Step | Action | Count |
|---|---|---|---|
| 1 | New project | New · Create | 2 |
| 2 | Bring the logo in | Drag `logo.svg` from the desktop onto the canvas (lands centred as the group "logo") | 1 |
| 3 | Go into it | Double-click the logo | 1 |
| 4 | Pick the four outlines | Click the first outline row · Shift+click the last | 2 |
| 5 | Draw them on | Open **Line** · click the ruler at 1.0 s · **Draw to** diamond (100 %) · Home · Draw to field · type 0 | 6 |
| 6 | One after another | Context bar **Stagger…** · type 3 (frames) · Enter | 3 |
| 7 | A wipe for the fill | **R** · drag a rectangle over the logo · Shift+click the two fill rows · context bar **Mask** | 5 |
| 8 | Animate the wipe | Click the rectangle's row · click the ruler at 1.2 s · X diamond · click the ruler at 0.8 s · drag the rectangle off to the left | 5 |
| 9 | A glow | Shift+Enter (back to the logo group) · Effects **+** · **Glow** | 3 |
| 10 | Springy settle | Click the ruler at 1.6 s · Scale diamond · click the ruler at 1.0 s · Scale field · type 90 · box the two keys · Ease ▾ · **Spring** | 8 |
| 11 | Transparent background | Esc · Esc (keys, then layers) · Background ▾ · **None** | 4 |
| 12 | Watch | Space | 1 |
| 13 | Export | Export · **Video with transparency** (ProRes 4444, the default) · Export | 3 |
| | | **Total** | **44** |

**Today:** keys on several outlines at once and the action bar are being built in H28; no stagger (each bar dragged by
hand), the mask is a 200 px box placed by typing, no spring ease, glow only through Ctrl+K on the first selected layer.

## F3 · UI and product animation: three app cards slide into place with a spring, a cursor taps a button, the phone from Rostrum3D sits behind (Maya)

| # | Step | Action | Count |
|---|---|---|---|
| 1 | New project | New · Create | 2 |
| 2 | Bring in the screen | In Figma: copy the frame's link · in 2D: Ctrl+V on the canvas (first time only: paste the token · OK) | 1 (+2 the first time) |
| 3 | Cards in a column | Double-click the frame · drag a box over the three cards · **Shift+A** (a column, as they were stacked) · drag the pink gap to 24 px | 4 |
| 4 | End pose | Click the ruler at 1.0 s · **K** (keys Offset, Scale, Rotation, Opacity on all three) | 2 |
| 5 | Start pose | Click the ruler at 0.4 s · Offset X field · type 400 · Opacity field · type 0 (all three at once) | 5 |
| 6 | Spring | Box the keys · Ease ▾ · **Spring** | 3 |
| 7 | Cascade | **Stagger…** · type 4 · Enter | 3 |
| 8 | Frosted glass | (cards still selected) Effects **+** · **Frosted glass** | 2 |
| 9 | Cursor | Drag `cursor.svg` onto the canvas · click the ruler at 1.6 s · K · click the ruler at 2.2 s · drag the cursor onto the button | 5 |
| 10 | Tap | Click the ruler at 2.3 s · Scale field · type 90 · click the ruler at 2.4 s · Scale field · type 100 | 6 |
| 11 | The phone | **+** · **3D render** · click the phone's picture · Ctrl+Shift+[ (send to back) | 4 |
| 12 | Watch, export | Space · Export · Export | 3 |
| | | **Total** | **40** (42 the first time) |

**Today:** no paste of a Figma link (the Import panel's Figma tab works, untested on the live API), no K, no stagger,
no spring, auto layout needs an empty group first (fixed in H28), 3D item picked by typing its name.

## F4 · A character who says "Hello", blinks and waves (Kenji)

The project already has the voice line "hello" made in RostrumSound.

| # | Step | Action | Count |
|---|---|---|---|
| 1 | Open the project | Start screen · click the project | 1 |
| 2 | Bring the parts in | Drag `max.psd` onto the canvas (the group "max" with named parts) | 1 |
| 3 | Make a puppet | (the new group is selected; its parts are named like a body, so Make rig is first) context bar **Make rig** | 1 |
| 4 | Bones | Context bar **Bones from part names** · drag 4 joints that are slightly off (elbows, knees) | 5 |
| 5 | Mouths | Double-click into the rig · click the "mouth A" row · Shift+click "mouth rest" · **Make swap set** | 4 |
| 6 | Lip sync | **Lip sync…** · click "hello" in the voice list · (shapes guessed from names, all right) **Apply** | 3 |
| 7 | Eyes | Click "eyes open" · Shift+click "eyes closed" · **Make swap set** · **Add blinks…** · **Apply** | 5 |
| 8 | Wave | Shift+Enter (the rig) · click the ruler at 1.0 s · K · ruler 1.4 s · drag the hand up · ruler 1.8 s · drag the hand · ruler 2.2 s · drag the hand | 9 |
| 9 | On twos | Timing ▸ · Steps ▾ · **On twos** | 3 |
| 10 | Watch with the voice | Space | 1 |
| 11 | Export | Export · Export | 2 |
| | | **Total** | **35** |

Drawing bones by hand instead of step 4: about 26 clicks (each joint a click). **Today:** a person can't do steps 4,
6, 7 (blinks) and 8 at all; only an agent can (FINDINGS 3.4).

## F5 · Frame-by-frame: a 12-drawing smoke puff on twos, colour under the lines, a looping GIF (Kenji)

| # | Step | Action | Count |
|---|---|---|---|
| 1 | New project | New · 24 fps · Create | 3 |
| 2 | First drawing | **B** · draw (a new drawing is made around the strokes) | 1 + strokes |
| 3 | Hand-drawn frames | New drawings hold ▾ · **2 frames** · **Alt+N** (Draw each frame turns on; drawing 2 starts) · **Alt+O** (onion skin) · draw | 4 + strokes |
| 4 | Drawings 3–12 | Alt+N before each, then draw (10 ×) | 10 + strokes |
| 5 | Colour layer | **+ Paint layer** · drag it under "Paint" | 2 |
| 6 | Colour each drawing | **G** (fill) · Home (back to drawing 1) · for each of the 12 drawings: click inside the puff · Alt+→ to the next | 25 |
| 7 | Repeat it | Right-click the bar · **Play only this layer's time** · Space | 3 |
| 8 | Export | Export · **GIF** · Range ▾ · **Time range** · Export | 5 |
| | | **Total** | **≈ 53, plus the strokes** |

**Today:** Draw page, + Add › Drawing first, no colour layer, no fill bucket, no zoom; the rest of the timing is hidden
while drawing.

## F6 · A painted scene with depth: far, middle and near hills, a camera push-in, drifting smoke, grain (Kenji)

| # | Step | Action | Count |
|---|---|---|---|
| 1 | New project | New · Create | 2 |
| 2 | A camera | **+** · **Camera** | 2 |
| 3 | Paint the far hills | **B** · paint (a new drawing) | 1 + strokes |
| 4 | Middle and near | Painting on ▸ **New drawing** · paint · Painting on ▸ **New drawing** · paint | 4 + strokes |
| 5 | Set the depths | **V** · click the far drawing · Set depth ▾ · **Far** · click the middle one · Set depth ▾ · **Middle** · click the near one · Set depth ▾ · **Near** | 10 |
| 6 | A textured house | **R** · drag · Fill swatch · pick · **B** · paint grain inside it | 5 + strokes |
| 7 | Push in | Click the camera row · Home · K · End · **C** · Alt+drag up on the canvas (camera closer) · box the two keys · Ease ▾ · **Smooth** | 9 |
| 8 | Smoke | **B** · Painting on ▸ **New drawing** · paint · **V** · Home · K · End · drag the smoke up and right | 8 + strokes |
| 9 | Grain on everything | Esc · Effects **+** · **Grain** | 3 |
| 10 | Watch, export | Space · Export · Export | 3 |
| | | **Total** | **≈ 47, plus the strokes** |

**Today:** depths only through an agent (`background.add`), painting only on drawing layers, no Camera tool, no grain.

## F7 · Timing to music: a piece cut to Sound's track (anyone)

The project has music from RostrumSound with the markers "intro", "drop" and "out" and a tempo.

| # | Step | Action | Count |
|---|---|---|---|
| 1 | Open | Click the project on the start screen (the music's row and markers are already there) | 1 |
| 2 | Listen | Space · Space | 2 |
| 3 | See the beat | Ruler ▾ · **Show beats** | 2 |
| 4 | Tie to the moments | Drag the title bar's start onto "intro" · the logo bar's start onto "drop" · the cards' bar end onto "out" | 3 |
| 5 | Pulse on the beat | Click the logo · Scale field · type `=100 + 6 * pulse()` · Enter | 4 |
| 6 | The music changes | Sound moves "drop" later: nothing to do; the logo follows | 0 |
| 7 | Export | Export · Export | 2 |
| | | **Total** | **14** |

**Today:** no sound at all in 2D; markers show but you can't hear what they mark; tying is a setting, not a drop.

## F8 · Working with an agent: Sam directs, Claude builds, Sam adjusts (Sam)

| # | Step | Action | Count (in 2D) |
|---|---|---|---|
| 1 | Open the project | Click it on the start screen | 1 |
| 2 | Ask | In the AI app: "Make a 10 s launch title for Lull, timed to the music" | (1 in the AI app) |
| 3 | Watch | The chip says "Claude is working"; layers appear; your selection and playhead stay | 0 |
| 4 | Adjust while it works | Click the title · Colour swatch · pick a warmer colour | 3 |
| 5 | Point at a problem | **N** · circle the logo · type "lands too early, should hit 'drop'" · Enter | 4 |
| 6 | Ask it to read notes | In the AI app: "see my notes" | (1 in the AI app) |
| 7 | Review its run | **Review** on the chip · **Undo this** on "Added lens flare" · **Keep** | 3 |
| 8 | Export | **Ctrl+Shift+E** (export again) | 1 |
| | | **Total** | **12 in 2D, 2 messages** |

What makes it work: the agent's second run did not touch the title colour Sam set (refused to the agent, listed in the
review as "Not changed: you had changed it"); the note told it where and when; Ctrl+Z was never needed for the agent's
steps. **Today:** live updates and per-person undo work; no review group, no notes, no dots on changed rows.

## F9 · A social post: 9:16 from the brand kit, in five minutes (Priya)

| # | Step | Action | Count |
|---|---|---|---|
| 1 | New project | New · **9:16 vertical** · Create | 3 |
| 2 | Logo | **Library** · Brand kit · drag the logo onto the canvas | 3 |
| 3 | Photo | Drag the photo from the desktop · right-click › **Send to back** · context bar **Fill the frame** | 4 |
| 4 | Title | **T** · click · type "Summer drop" · Esc · Style ▾ · **Brand heading** | 6 |
| 5 | Title and logo come in | Shift+click the logo · click the ruler at 0.8 s · **K** · Home · Opacity field · type 0 · drag both down a little | 7 |
| 6 | Feel | Box the keys · Ease ▾ · **Ease out** · **Stagger…** · Enter (2 f default) | 5 |
| 7 | Slow push on the photo | Click the photo · Home · K · End · Scale field · type 110 | 6 |
| 8 | Export | Export · Export | 2 |
| | | **Total** | **36** |

**Today:** no 9:16 by name, no library or brand kit, no K, no stagger, no "Fill the frame".

## F10 · An explainer: four labelled icons, eight dots that light up in turn, an arrow travelling along a curve (Maya, Priya)

| # | Step | Action | Count |
|---|---|---|---|
| 1 | New project | New · Create | 2 |
| 2 | One icon | **O** · drag · **T** · click under it · type "Plan" · Esc · Shift+click the circle | 7 |
| 3 | Make it a symbol | **Make symbol** (2 layers: in the first five) · double-click it · right-click the text › **Changeable in copies** · Shift+Enter | 5 |
| 4 | Three more | Alt+drag × 3 | 3 |
| 5 | Their labels | For each of the three copies: click it · Label field · type the word | 9 |
| 6 | Space them | Drag a box over all four · **Distribute ▾** · **Even gaps across** | 3 |
| 7 | Dots | **O** · drag a small dot · **Repeat** · Count field · type 8 | 5 |
| 8 | Light up in turn | Each copy changes by ▸ Time offset · type 2 (frames) · click the ruler at 0.5 s · Opacity diamond · Home · Opacity field · type 0 | 7 |
| 9 | The curve | **Shift+P** (pencil) · draw the curve | 2 |
| 10 | The arrow | Drag `arrow.svg` onto the canvas · Shift+click the curve · **Move along path** · **Turn along its path** | 4 |
| 11 | Travel | Home · Along diamond (0 %) · End · Along field · type 100 | 5 |
| 12 | Watch, export | Space · Export · Export | 3 |
| | | **Total** | **55** |

**Today:** no symbols, no repeat, no pencil, no move along a path; each would be done by copying layers and keying
positions one by one.

## What the flows show

1. **The selection is the input to almost everything** (F2 steps 4–7, F3 3–8, F4 3–7, F10 2–6). Multi-select must
   work everywhere and every relating action reads it.
2. **K and Stagger save the most clicks** in motion-design jobs (F3, F9): without them F3 is about 30 clicks longer.
3. **The playhead + a value change is the core rhythm** of keying. Clicking the ruler is the most repeated action:
   Home, End, `,` `.` and typing a time in the header shorten it for people who want speed.
4. **Painting jobs are long by nature**; what matters there is that the canvas is big and nothing interrupts the
   strokes (F5, F6): the compact timeline and quick brush controls on the context bar serve that.
5. **A person can now do every job an agent can** (F4 and F6 were agent-only before).

---

# Part 6 · Feel

## 6.1 Speed budgets

Measured from the input (pointer move, key press, pen sample) to the change on the screen, on Sam's laptop (RTX 3050,
16 GB) with a typical launch-film scene (about 40 layers, effects, 1080p). "p95" = 95 times out of 100.

| What | Budget (median / p95) | How it is met |
|---|---|---|
| The pointer itself | 0 (the system cursor) | Never draw our own cursor. |
| Handles, box, guides during a drag | **the same frame as the picture** | Overlays are drawn from the state of the picture on screen (Hem's base fix): box and picture never disagree (0 px gap, measured in H28). |
| The picture during a drag | **≤ 33 ms / ≤ 50 ms** (2–3 frames at 60 Hz) | Half size while dragging, full size on release; only the changed layers are re-described (the main thread's 15–45 ms scene re-description is today's biggest cost: H28 drag-feel `numbers.md`). |
| Full-quality picture after release | ≤ 150 ms | One full-size frame. |
| A paint stroke under the pen | **≤ 16 ms / ≤ 25 ms** (the next screen refresh) | Strokes are drawn by the screen straight away as a preview with the real brush, and the engine's stroke replaces it when it lands (the same brush engine, so they match). |
| Timeline bars, keys, rows | ≤ 16 ms | Drawn by the screen (Qt) at once; the picture follows. |
| Typing in a field, scrubbing a number | value at once; picture ≤ 50 ms | As a drag. |
| Scrubbing the playhead | ≤ 50 ms / ≤ 80 ms a frame at Half; sound ≤ 40 ms | Auto preview size; cached frames reused. |
| Playback | real time at the chosen size; if not, Auto drops to Half before dropping frames | The rate shows in amber only when it is below the scene's. |
| Opening a menu, drawer, popover | ≤ 50 ms, no animation longer than 120 ms | Interface motion is short and never blocks input. |
| Selecting something | ≤ 16 ms for the highlight; settings ≤ 50 ms | The panel is built from data; no per-panel code. |
| Opening a project | ≤ 2 s to a usable screen (the picture may follow) | The picture is fetched in the background. |
| Undo | ≤ 50 ms for the change; picture ≤ 100 ms | |

Every budget is checked by the drag-feel style measurement Hem built in H28
(`C:\Users\Sam\.rostrum\waves\results\2d-redesign\h28\drag-feel\`), extended to strokes, scrubbing and playback, run once
per brief that touches them.

## 6.2 Snapping

- **On the canvas** a dragged layer (or a resize edge) snaps when within **6 screen px** of: the frame's edges and
  centre lines; other visible layers' edges and centres (in the same group first); guides; equal spacing between
  neighbours; the layout grid; whole pixels above 600 % zoom (when the pixel grid shows). A thin magenta line shows what it snapped to, and equal
  gaps show their distance.
- **In time** bars, keys and the playhead snap within **6 screen px** to: the playhead, markers, beats (when shown),
  other layers' bar ends and keys, whole frames always.
- **Ctrl pressed after a drag has started** stops snapping for that drag; Ctrl pressed *before* pressing on a layer
  picks its deepest piece (6.4), so the two never meet. The view menu has **Snapping** on / off for those who
  want it off all the time (it stays on by default).
- Snapping never changes a value the person typed.

## 6.3 Nudging

- Arrows move the selection in the place you are working (decision 6): on the canvas 1 px (Shift: 10 px); in the
  timeline 1 frame (Shift: 10 frames) for selected bars or keys.
- **Alt+arrows** move a fine step (0.1 px on the canvas; nothing in the timeline, where frames are whole) *(S30)*.
- A burst of presses (less than 1 s apart) is **one** undo step.
- An animated setting nudged at the playhead adds or changes the key there, like any change.
- Ctrl+arrows always move the playhead, wherever focus is.

## 6.4 Selection rules

- One selection, shared by canvas, rows and panel.
- Click: canvas picks the painted layer under the pointer, outer group first; rows pick the row.
- Add or remove: Shift+click on the canvas; Ctrl+click in rows **and among keys and bars in the timeline**; Shift+click
  there selects the run between *(S30)*.
- Right-click on an unselected layer first selects it alone; on a selected one it keeps the selection *(S30)*.
- Box: on empty canvas (touching layers; Shift+box adds; Ctrl+box picks the deepest pieces *(S30)*); on empty bar
  area (keys; Ctrl+box adds).
- Deeper: double-click or Enter goes into a group, a path's points, a text's letters, a symbol; Ctrl+click picks the
  deepest; Shift+Enter goes out.
- Escape clears one level at a time: typing → keys → points → layers → nothing.
- Several selected: one box on the canvas; "3 layers" in the panel; shared settings with "Mixed"; actions apply to
  all; drags move all.
- Locked layers can't be picked on the canvas (they can in rows, to unlock them); hidden layers can't be picked on the
  canvas.
- Undo restores the selection that belonged to the step.
- An agent never changes the person's selection.

## 6.5 Focus and the keyboard

- **Focus is visible:** the region that has the keyboard (canvas, timeline, settings) shows a faint top edge
  highlight. Clicking in a region gives it focus; Esc in a field returns focus to the canvas.
- In fields: Tab and Shift+Tab move between fields; Enter commits; Esc cancels; ↑ / ↓ change a number by 1 (Shift 10).
- Single-letter keys (V, R, O, L, P, T, B, C, J, N, K, M, A, F, and E / G while painting; S30: A replaces U) work only when no field has focus, so typing a name
  never switches tools.
- **F6** moves the keyboard to the next area *(S30)*.
- Every action reachable by mouse is reachable by Ctrl+K; every shortcut is on its button's hover name and in Ctrl+/.
- Pen and touch: pressure and tilt from any pen; the pen's back end erases; two-finger pinch zooms, twist turns the
  view (when on), two-finger drag pans; a long press = right-click.

## 6.6 Errors in plain words

Every refusal and failure says **what happened, in words, and what to do**, and names the thing. Never a code, never
an internal name, never silent (rule 6).

| Situation | Says |
|---|---|
| An action that needs more selected (from Ctrl+K by exact name) | "Combine needs two or more shapes selected." |
| A canvas drag on a value that follows a link or expression | "Opacity is linked to *card*. Unlink it to change it here." |
| A locked layer | "*Background* is locked. Unlock it to change it." (and an Unlock button) |
| A missing font | "The font *Söhne* isn't on this computer. Pick another, or install it and it will be used." |
| An export that failed | "The MP4 couldn't be made: this Windows has no video encoder (Media Feature Pack). Install it, or export ProRes." |
| An expression mistake | "No layer called *titel*. Did you mean *title*?" under the field; the last good value stays. |
| A refused agent change (shown in its review) | "Not changed: you had changed *title · Colour* after Claude last looked." |
| An import that left things out | "Placed *logo.pdf*: 14 layers. 2 gradients on outlines came in as flat colour. Show what." |

## 6.7 Empty states that teach

| Where | Empty state |
|---|---|
| A new scene's canvas | "Draw a shape (R), type (T), paint (B), or drop a file here." |
| The layers list with no layers | "Your layers appear here as bars. Drag a bar to change when it shows." |
| A layer with no keys, when its row is opened | "Click a diamond beside a setting to animate it, or press K." |
| The context bar the first time several things are selected | Its actions are the hint; nothing extra. |
| Effects with none | "Effects (0) +" (the + is the hint). |
| Library with no symbols | "Select layers and choose Make symbol to reuse them here." |
| History with no steps | "Your changes and your agent's will be listed here." |
| Notes with none | "Press N to draw a note on the picture for your agent or team." |

Empty states disappear as soon as there is something, and never come back as pop-ups.

## 6.8 First use, without a manual

1. The start screen shows **New** big, the sizes by name, and three **guides** as cards ("Your first title", "Paint and
   animate a drawing", "Work with an AI agent"); no sample project opens by itself.
2. The empty canvas says what to do (6.7).
3. Every tool's options appear on the context bar the moment it is picked, so the next step is always visible.
4. Diamonds are visible beside every setting, so "this can move" is never hidden.
5. Hover names give every button its name and key after half a second.
6. Ctrl+K finds anything by name, including what isn't shown right now, and says why it isn't.
7. Every mistake is one Ctrl+Z, and Ctrl+Z only ever takes back your own last step.

No tours, no tip-of-the-day, no modal welcome. The screen itself is the teacher.

## 6.9 The look of the interface

The dark, clean look decided for all apps (GUI_DESIGN §9): dark grey panels, one accent colour for selection, a second
for keys, magenta for snapping, red only for errors and Notes. Every control is drawn once in the shared kit and reused
(PLAN › GUI kit). Every screen state in this spec is checked by the automatic look pass (overlaps, cut-off text) at
1280, 1366, 1646 and 1920 wide before it is shown to Sam.

---

# Part 7 · Gaps against today

**Today** = `main` plus Team Hem's H28 work committed on `team/hem` by 2026-10-22 (one workspace, layer bars, two
timeline heights, the select-then-act operations and action bar, lock / hide, copy / paste, picking by what is painted,
outer-group picking, drag feel, the settings panel with essentials, folded groups, search and several layers, the new
top bar). Read from the code and the H28 notes; not every row was run.

**Size of the change:** **S** = a few hours of one member; **M** = one member for a whole brief (~2 h of agent time
plus checks); **L** = a whole team brief; **XL** = several briefs, or engine or shared-layer work first. **Where:**
screen (QML / screen code), Py (the 2D Python document and operations), eng (the Rust engine), kit (the shared GUI kit),
core (the shared operations and history), svc (the project service).

| Feature | Today | The spec says | Size | Where |
|---|---|---|---|---|
| **Project and scenes** | | | | |
| Start screen and recent | Launch opens the newest recent, which is often an agent's scratch folder (FINDINGS 1.4) | Hub with New by named sizes; people's projects only; never open an agent's scratch | M | kit, svc |
| Sizes by name | Width / height typed | 16:9 HD, 4K, 9:16, 1:1, 4:5, Custom | S | screen |
| Several scenes | Operations `comp.add` / `comp.remove`; PDF pages as scenes; no scene list on screen found | Scene name in the top bar is the list | S | screen |
| Scene settings when nothing selected | Done (H28) | Same, plus Soundtrack, Layout grid, scene Effects | S | screen, Py |
| **Canvas view** | | | | |
| Zoom, pan, fit, 100 % | None (planned in H28) | Ctrl+wheel at the pointer, Space-drag, Ctrl+0, Ctrl+1, Shift+2, view controls | M | screen |
| Rotate the view | None | Shift+Space+drag, compass | S | screen |
| Rulers, guides, safe areas, grids | None | As 3.2 | M | screen, Py (guides are document) |
| Preview size, Fast / Final | Full / Half / Quarter in the timeline header | In the view controls, Auto, labelled when not Full / Final | S | screen |
| **Making things** | | | | |
| Rectangle, ellipse, text by drawing on the canvas | Not yet (H28 "if time") | R, O, T: drag or click where it goes | M | screen |
| Polygon, star, line | Not on screen | In the Shape button's list | M | Py, screen |
| Corner dots | None | Drag inside the corners | S | screen |
| Pencil (vector freehand) | `path.fit` exists | Shift+P | M | screen |
| Width along a line on the canvas | Settings only (`path.width`) | Alt+drag on the line | M | screen |
| Typing on the canvas | Text typed in the panel | Click and type; double-click to edit; styled runs | L | screen, Py, eng (cursor / selection geometry) |
| Font list with previews | A text box | Searchable list drawn in each font, weights by name; `inspect_fonts` | M | kit, Py |
| Glyph alternates | Free features text | Tiles per letter | M | screen, eng |
| Put text on a path | A picker field (S18) | Select text + path → Put on path | S | screen (action list) |
| Add from a file: one door, drop, Ctrl+I | + Add and an Import panel (background job) | One + Add, file drop on canvas and rows | S | screen |
| Paste from other apps | Rostrum's own clipboard (H28) | SVG / image / text from any app | M | screen, Py |
| Replace a picture or video | None | Replace…, drop on its row | S | Py, screen |
| Crop, fit, Fill the frame | Size only | Double-click to crop; Fit; Fill the frame | M | Py, eng |
| Slip a video | `offset` field | Alt+drag inside the bar | S | screen |
| Time of a video or symbol (freeze, reverse, ramps) | Speed and offset only | Keyable Time | M | Py, eng |
| 3D render picked by picture, Open in 3D | Item typed in a field | List with pictures; Open in Rostrum3D | S | screen, svc |
| **Painting and drawing** | | | | |
| Paint on any element (inside its outline) | Drawing layers only | B paints on the selected element; on nothing makes a drawing (that part is in H28) | XL | eng, Py, kit (painting kit), screen |
| Paint layers inside an element | None | + Paint layer | L | Py, eng, screen |
| Quick brush controls on the canvas | Brush panel in the settings | Size, opacity, colour, eraser on the context bar; [ ] size; Alt picks | M | screen |
| Fill bucket with gap closing | None | G | L | painting kit |
| Lasso and move strokes | `stroke.set` exists | Ctrl+lasso, transform, copy | M | screen |
| Set depth / Move to depth on screen | Agent only (`background.*`) | Context bar on drawings | M | screen |
| Stroke reveal | None | Reveal % | M | Py, eng |
| Shape morphing | Path-shape keys (H14); points edited on screen | The Shape diamond; Start point | S | screen |
| Brush steadiness | None | A Steadiness slider | M | painting kit |
| Mirror the view | None | Shift+H | S | screen |
| Frame-by-frame | Done on screen (frames, holds, onion, Alt keys) | Plus "New drawings hold", light table, flip, `,` `.` | S (hold, flip) · M (light table) | screen |
| **Selecting and arranging** | | | | |
| Picking by paint, outer group, double-click in, Ctrl+click deep, Shift / Ctrl rules | Done (H28) | Same, plus hover outline, group path at bottom-left, Tab to next layer, Shift+Enter out | S | screen |
| Handles | Done; resize pointers don't turn with a turned box | Pointers turn | S | screen |
| X Y / W H pairs, scrubbing labels, maths in fields | One per row; no scrub | Pairs; scrub; `+20`, `*2`, `50%`, `=` | M | kit |
| Anchor point | Fields "Anchor X 0.50" | Alt+drag on canvas, 9-dot picker | M | screen, kit |
| Find a layer, U for animated settings | None | Search box over 12 layers; U | S | screen |
| Layer rows, reorder, rename, hide, lock | Done (H28) | Plus solo with its banner, smart duplicate | S | screen |
| Group, ungroup, clip, mask, align, distribute, match size, copy / paste style, from the selection | Done (H28: operations, action bar, right-click, Ctrl+K on all) | Same list, moved to the fixed context bar, plus the new actions below | M (move to context bar) | screen |
| Draw a mask on one layer | None | Mask ▾ › Draw | M | screen |
| Live booleans with Flatten | Baked only | Live combined shape | L | eng, Py |
| Auto layout gap handles, reorder by drag, child Offset | Settings only | On the canvas; Offset X Y | M | screen, Py (layout bake) |
| **Motion** | | | | |
| Diamond, animate in place | Done (H28); diamond only on hover | Always faintly visible | S | kit |
| K: key the selection | None | K | S | screen, Py |
| Box-select, move keys | Single key drag | Box-select across bars; move together | M | screen |
| After the last key (repeat, back and forth) | Expressions only | Key bar ⋯ | M | core, Py |
| Stretch and paste keys | None | Alt+drag ends; Ctrl+C / V at the playhead | M | Py, screen |
| Key bar (ease for many keys, curve chip) | The settings panel swaps to one key | Key bar in the timeline header | M | screen |
| Spring ease | None | Bounce and Speed | M | core (easing), Py |
| Curve editor | Done | Same | — | — |
| Stagger | None | Stagger… popover | M | Py (`layer.stagger`), screen |
| Markers: M, type the name at once; tie by drop | Marker button, rename by double-click; tie by drop (H28) | M key, name typed at once, ties on keys too | S | screen, kit |
| Time range, play only a layer's time | Not found | Band on the ruler, right-click a bar | S | screen |
| Letter animation | Done (fields) | Plus "Animate letters" in the context bar | S | screen |
| Letter ranges | None | Later | L | Py, eng |
| Motion paths on the canvas | None | Path, dots, key squares, spatial handles | L | screen, core (spatial keys) |
| Move along a path, turn along it | Text only | Any layer | M | Py |
| Follow (parenting) | None | Follow *x* from the selection | L | eng, Py |
| **Characters** | | | | |
| Make rig, Make swap set | Done (H28) | Same | — | — |
| Bone tool, attach, IK drag, pins, poses, lip sync, blinks on screen | Agent only (operations done) | As 3.23 (H30) | XL | screen |
| Bones from part names | None | Context bar on a rig with no bones | M | Py |
| Bend weights | Two-bone bend only | Later | L | eng |
| **Camera and depth** | | | | |
| Camera tool | None (layer and fields) | C: drag, move closer, turn | M | screen |
| Focus by clicking a layer, rack focus | Fields | Eyedropper on the canvas | S | screen |
| Shake, follow | None | Helpers that write keys | M | Py |
| Side view | None | Later | L | screen, eng |
| **Look** | | | | |
| Gradient handles on the canvas | Fields | Handles while the picker is open | M | screen |
| Effects + on the panel, to every selected layer | Ctrl+K and H28's panel (to all selected since H28) | Effects (n) + always listed | S | kit |
| Grain, displace, distort, light wrap | None | Four new effects | L | eng |
| Scene effects | None | Effects on the whole picture | M | Py, eng |
| Blend preview while browsing | Pick then see | Preview as you move through the list | S | kit |
| **Expressions and links** | | | | |
| Expressions | Done; typed in a field | `=` starts one, suggestions, `beat` / `pulse()` | S (entry) · M (suggestions) | kit, Py |
| Link to… on screen | Operation only (`link.set`) | Right-click › Link to…, then click the source | M | screen |
| **Reuse** | | | | |
| Symbols (copies, changeable settings, own time) | None (groups, scenes) | As 3.27 | XL | Py, eng, screen |
| Colour and text styles | None | Saved styles, change once | L | Py, screen |
| Saved motions | None | Later | M | Py, screen |
| Library drawer, brand kit | None | Left drawer | L | screen, svc |
| Repeat | None | Row, grid, circle, along a path | L | Py, eng |
| **Sound** | | | | |
| Hear the project's sound, scrub it | None (FINDINGS 3.7) | Through Sound's engine, in sync | XL | svc, Sound engine, screen |
| Waveform row | None | Under the layers | M | screen |
| Beat grid, snapping to beats | None | From Sound's tempo map | M (after the sound row) | screen, svc |
| Sync sound cues | None | Drop a sound on a bar | M | Sound, screen |
| **Watching and delivering** | | | | |
| Space, scrub | Done | Same | — | — |
| Ctrl+arrows, `,` `.`, Home / End, typing a time | Partly | All of 3.29 | S | screen |
| Hide the panels | None | Ctrl+\ | S | screen |
| Export | Panel over the canvas; names, Show in folder, no replace without asking (H25) | Sheet in the settings panel's place, purposes in words, progress in the top bar, Export again | M | screen |
| **Safety and files** | | | | |
| Undo per person, ↶ ↷ only when they act | Done | Same | — | — |
| History drawer, undo a chosen step | None | As 3.31 | L | core, screen |
| Versions (Ctrl+S) | Ctrl+S saves (nothing to save) | Save a version, restore, daily versions | M | core, svc, screen |
| Recovery | Done (S27) | Same | — | — |
| Relink missing files | Problems lists them | Find it… relinks all uses | M | Py, screen |
| **Help** | | | | |
| Hover names, Problems, Ctrl+K on the whole selection | Done (H25, H28) | Same | — | — |
| Shortcut sheet | None (H29 planned) | Ctrl+/ | S | kit |
| Guides in a drawer, Ctrl+K "Learn" | Guides open in Help | Drawer beside the canvas; search finds guide sections | M | kit |
| Empty states | Some (layers, canvas) | The table in 6.7 | S | screen |
| **Working with an agent** | | | | |
| Live changes that never move the person | Done (H28) | Same | — | — |
| "Claude is working" chip, dots on changed rows | Top bar names the last change | Chip, dots, brief outline | M | kit, screen |
| Run as a reviewable group, Undo all | None | As 3.34 | L | core, kit |
| Refuse agent changes to values the person changed since the agent looked | Script re-runs keep the person's items (S18) | Per value, told to the agent, listed in the review | L | core |
| Agent reads the person's selection and playhead | None | `inspect_screen` | M | screen, Py (MCP) |
| Notes (paint-over directions) | None | N, `look_notes` | L | screen, Py, painting kit |
| Copy link for an agent | None | Right-click › Copy link | S | screen |
| **Screen structure** | | | | |
| Top bar | Rebuilt in H28 (message gives way, count never shrinks) | Drop the count, move + Add and Import to the tool strip, chips | S | kit, screen |
| Context bar at a fixed place, with tool options | Action bar under the selection (H28) | Top-centre of the canvas; tool options there too | M | screen |
| Tool strip with creation tools and + | Move, Pen, Draw | As 4.1 | M | screen |
| Timeline compact under 800 px tall | Two heights per tool (H28) | Plus the size rule | S | screen |

## Suggested order of work

Built in this order because each step makes the most-used jobs better before the rarer ones (effective first), and
because later steps lean on earlier ones.

1. **Finish H28, then the frame of the screen:** the fixed context bar (with tool options), the tool strip with R / O /
   T and + Add, zoom and pan, canvas snapping. *Every job uses these.*
2. **Keys that work at speed:** the key bar, K, box-select and move keys, Stagger, Spring, always-visible diamonds,
   time keys (`,` `.`, Ctrl+arrows). *F1, F2, F3, F9, F10.*
3. **H29 painting:** paint on any element, paint layers, quick brush controls, fill, lasso, Set depth on screen. *F5, F6.*
4. **Sound in 2D** (with Team Sam / Priyam: the project service plays Sound's mix in sync) and the beat grid. *F7, and
   every job cut to music.*
5. **H30 characters on screen:** Bone tool, Bones from part names, IK drag, poses, Lip sync, Add blinks. *F4.*
6. **Reuse:** symbols, styles, the library drawer, Repeat. *F9, F10.*
7. **Motion paths, Move along a path, Follow, the Camera tool.** *F6, F10.*
8. **Working with an agent:** the run as a group, dots, notes, `inspect_screen`, the History drawer, versions. *F8.*
9. **New effects and live booleans:** grain, displace, distort, light wrap, live combine. *The reference look.*

---

# Appendix A · Every shortcut

Ctrl = ⌘ and Alt = ⌥ on the Mac. Single-letter keys work only when no text field has focus.

| Job | Keys |
|---|---|
| **Tools** | V Move · R Rectangle · O Ellipse · L Line · P Pen · Shift+P Pencil · T Text · B Paint · E Eraser (while painting) · G Fill (while painting) · C Camera (with a camera) · J Bone (with a rig) · N Notes |
| **Make and add** | Ctrl+I Add from a file · Ctrl+Shift+N New scene · Ctrl+N New project · Ctrl+O Open · Ctrl+Shift+S Duplicate *(S30)* · Ctrl+Q Quit *(S30)* |
| **Select** | Click · Shift+click (canvas) · Ctrl+click / Shift+click (rows), also keys and bars in the timeline *(S30)* · Shift+box adds, Ctrl+box deepest (canvas) *(S30)* · Ctrl+A · Esc · Enter / double-click (go in) · Shift+Enter (go out) · Ctrl+click (deepest) · Tab / Shift+Tab (next / previous layer) |
| **Move and size** | Arrows nudge 1 px / Shift 10 px (canvas) / Alt 0.1 px *(S30)* · Shift while dragging (proportions, straight) · Alt while dragging (from the centre) · Alt+drag (a copy) · Ctrl while dragging (no snapping) · drag the anchor circle |
| **Edit** | Ctrl+Z · Ctrl+Shift+Z / Ctrl+Y · Ctrl+C · Ctrl+X · Ctrl+V (in place) · Ctrl+Shift+V (at the pointer) · Ctrl+D · Delete · F2 rename |
| **Arrange** | Ctrl+] / Ctrl+[ forward / back · Ctrl+Shift+] / [ front / back · Ctrl+G group · Ctrl+Shift+G ungroup · Shift+A auto layout · Ctrl+Alt+M mask · Ctrl+Alt+U / S / I / X combine (union, subtract, intersect, exclude) · Alt+A / D / W / S align left / right / top / bottom · Alt+H / V centre across / up and down · Ctrl+Shift+H hide · Ctrl+Shift+L lock · Alt+click an eye (solo) · Ctrl+Alt+K make symbol · Ctrl+Alt+C / V copy / paste style |
| **Animate** | K key the selection · M add a marker · F9 smooth · Shift+F9 ease in · Ctrl+Shift+F9 ease out · Ctrl+Alt+J jump (no in-between) · Alt+[ / Alt+] trim start / end to the playhead · arrows move selected keys or bars 1 frame / Shift 10 (timeline) · Alt+drag a key selection's end (stretch) · F fit curves (Curves) · **A** show animated settings *(S30, was U)* |
| **Time** | Space play / pause · Ctrl+← / → one frame · Ctrl+Shift+← / → ten frames · Home / End · `,` / `.` previous / next key, marker or drawing · Shift+`,` / Shift+`.` previous / next beat · Shift+I / Shift+O time range start / end · **Shift+L** loop on / off *(S30)* · Shift+Space play from the selection's start *(S30)* · Alt+M / Alt+Shift+M next / previous marker *(S30)* |
| **Frame-by-frame** | `,` / `.` previous / next drawing *(S30: Alt+arrows are the fine nudge now)* · Alt+N new drawing · Alt+Shift+N copy of this drawing · = / − hold longer / shorter *(S30)* · Alt+O onion skin · hold `,` or `.` to flip through |
| **Paint** | E eraser · G fill · [ / ] size · Shift+[ / ] softness · 1–0 opacity · Alt (hold) pick a colour · Shift+drag straight line · Ctrl+drag lasso strokes |
| **View** | Shift+H mirror the view · Ctrl+wheel / pinch zoom · Space+drag pan · Shift+Space+drag turn the view · Ctrl+0 fit · Ctrl+1 100 % · **F** (or Shift+2) zoom to selection *(S30)* · Ctrl+= / Ctrl+− · Shift+0 straighten the view · Shift+R rulers · Ctrl+\ hide panels |
| **Find and help** | Ctrl+K search and run · Ctrl+F find a setting · Ctrl+Shift+F find a layer · Ctrl+/ key list · F1 guides *(S30)* · Ctrl+L library · Ctrl+H history · Ctrl+S save a version · Ctrl+, preferences *(S30)* |
| **Export** | Ctrl+E export · Ctrl+Shift+E export again |

# Appendix B · The operations the screen calls

Every on-screen action is one change made of these operations; agents call the same ones through Rostrum2D's agent
server. *(new)* = to be added.

| Area | Operations |
|---|---|
| Scenes | `comp.add` · `comp.duplicate` *(new)* · `comp.remove` · `item.rename` · `value.set` (scene settings) · `guide.add` / `guide.remove` *(new)* |
| Layers | `layer.add` · `asset.relink` *(new)* · `layer.remove` · `layer.duplicate` · `layer.paste` · `layer.arrange` · `layer.hide` · `layer.lock` · `layer.unlock` · `layer.replace` *(new)* · `run_import` |
| Values and keys | `value.set {at}` · `key.add` (with `fields: "pose"` for K *(new)*) · `key.set` · `key.remove` · `key.clear` · `key.handles` · `key.scale` *(new)* · `key.paste` *(new)* · `key.set {after}` *(new)* · spatial handles on `key.set` *(new)* · spring ease *(new)* |
| Timing | `layer.shift {by | to: "#marker"}` · `layer.trim` · `layer.stagger` *(new)* · `marker.add` / `move` / `rename` / `remove` / `colour` |
| Paths | `path.add_point` · `path.set_point` · `path.remove_point` · `path.close` · `path.fit` · `path.width` · `shape.to_path` · `path.flatten` *(new)* |
| Relating (select first, then act) | `group.make {as: group | clip | layout | swap | boolean (new)}` · `group.release` · `mask.make` · `mask.release` · `shape.boolean` · `layer.align` · `layer.distribute` · `layer.match_size` · `style.apply` · `layer.follow` / `layer.unfollow` *(new)* · `rig.make` · `symbol.make` *(new)* · `repeat.make` *(new)* |
| Look | `effect.add` · `effect.remove` · `value.set` (fill, gradient, blend, colour) |
| Expressions | `expr.set` · `expr.clear` · `link.set` |
| Painting | `paint.stroke` (any element; H30) · `stroke.set` · `stroke.remove` · `paint.set` / `paint.move` / `paint.remove` (H30) · `paint.fill` (H30) · `frame.add` · `frame.hold` · `frame.remove` · `background.add` · `background.fit` · `background.move` |
| Characters | `bone.add` · `bone.remove` · `bind.add` · `bind.remove` · `ik.add` · `ik.remove` · `pose.save` · `pose.apply` · `pose.remove` · `swap.show` · `lipsync.apply` · `blink.add` · `rig.guess_bones` *(new)* |
| Camera | `camera.shake` *(new)* · `camera.keep_in_frame` *(new)* |
| Reuse | `symbol.place` · `symbol.set` · `symbol.detach` · `style.define` · `style.use` · `motion.save` · `motion.apply` · `library.add` · `repeat.bake` *(all new)* |
| Sound | `value.set {soundtrack}` *(new field)* · `sound.cue` *(new)* · `text.words_to_markers` *(new)* |
| Notes | `note.add` · `note.resolve` *(new)* |
| History | `undo` · `redo` · `history.list` · `history.undo {step}` *(new)* · `version.save` · `version.restore` · `version.to_comp` *(new)* · `project.duplicate` (project service) |
| Export | `render_export` · `render_video` |
| Eyes (agents only) | `look_frame` · `look_sheet` · `look_motion` · `look_at` · `look_drawing` · `look_drawing_change` · `inspect_drawing_at` · `inspect_stroke_landed` · `look_rig` · `inspect_rig_motion` · `inspect_lipsync` · `look_background` · `inspect_background` · `inspect_curve` · `inspect_layout` · `inspect_item` · `inspect_diagnose` · `inspect_tools` · `inspect_fonts` *(new)* · `inspect_screen` *(new)* · `look_notes` *(new)* · `inspect_library` *(new)* |

Screen-only state (not operations, never in the history): the selection, the playhead, the tool, zoom and pan, the
timeline's height, open groups, the search text, solo, the view's turn and mirror, and the time range (passed as the
range to operations that need one, such as export and notes). Everything else is an operation.
