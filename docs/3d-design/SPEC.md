# Rostrum3D: the screen and how people work in it (UX spec)

*Team Hem, 3D design round, 2026-10-24. Design only, no app code. The lead's frame is binding:
`C:\Users\Sam\.rostrum\waves\results\3d-design\BRIEF.md`. The model this spec follows is the 2D v2 spec
(`C:\Users\Sam\.rostrum\waves\results\2d-design-v2\SPEC.md`); where this file says nothing, that spec, the shared kit's
`C:\Users\Sam\Documents\CODE\Rostrum\shared\gui-kit\INTERACTION.md` and today's 3D docs
(`C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\apps\3d\DOCUMENT.md`, `ENGINE_CONTRACT.md`, `app\README.md`) still hold.*

*Running example everywhere: the "Aurora" product film from BRIEF.md (a matte black earbud case on a plinth, the
brushed-aluminium wordmark "AURORA", a softbox key, a strip rim, the "studio_small_09" sky; shots "Hero 01", "Close 02",
"Drop 03"; the shared marker "logo lands" at 3.2 s).*

*Mockups use real Rostrum3D renders from Stage 2 (a black puck stands in for the case, the "Rostrum" logo for AURORA, a glass for the bowl); their names follow the picture.*

Mockups (1646 × 900 unless the name says otherwise), in `C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\docs\3d-design\mockups\`:

| # | Picture | Shows | Section |
|---|---|---|---|
| 1 | `01-workspace-build.png` | The Build page, the case selected: rail, viewport through Hero 01, settings panel, scene list + thin timeline | §1, §3 |
| 2 | `02-shapes-flyout.png` | The Shapes flyout open beside the rail; nothing selected, so the settings panel is the Scene | §2, §3.3 |
| 3 | `03-logo-extrude.png` | "AURORA" as 3D text, bevel and face materials in the settings panel | §4.4 |
| 4 | `04-material-picker.png` | The material picker open from the case's Material row: this project's materials, then starting points | §6 |
| 5 | `05-lighting.png` | The softbox selected, placed by "Place highlight", light linking row, the rim's strip | §7 |
| 6 | `06-paint-on-model.png` | Paint mode on the case lid: brush cursor, paint layers, the coverage tint of what Hero 01 sees | §5 |
| 7 | `07-animate-timeline.png` | The Animate page: the lid's Turn stretch selected, the settings panel is that animation, "logo lands" flag | §9 |
| 8 | `08-render-sheet.png` | The Render sheet with the time estimate; the Render page's queue | §11 |
| 9 | `09-boolean-two-solids.png` | Case and cutter selected: Combine · Union / Subtract / Intersect at the top of the settings panel | §4.2 |
| 10 | `10-simulate.png` | "Drop 03": twelve buds set to fall, the Simulate row in the timeline, the stored result as a filled bar | §10 |

---

## 0 · The yardstick and the rules

Every decision is judged **effective** (gets a top-tier product film or stylized shot), **efficient** (fewest steps,
no detours), **easy** (seen, not remembered), in that order. Binding:

1. **Rule of individuality.** Only what you can use right now, most important first. Nothing greyed out: absent. Every
   control comes from operation data (`valid_when`, `importance` in `apps\3d\python\rostrum3d\fields.py`); no panel is
   hand-made. A tool that isn't built yet is not in the rail (no "coming soon").
2. **A tool, not a tutorial.** No helper sentences where a label or a hover does. No control twice on one screen.
3. **Every GUI action is an operation first.** Existing operations are written plain (`mesh.add`, `value.set`); new
   ones are marked **(new)**; a change to the file format is marked **Data change**.
4. **The document is the single source of truth.** A person and an agent edit the same `.trd`; one history; an agent
   re-running its script never wipes what a person moved (the shared merge on re-run).
5. **Built for the camera.** The shot camera is the default view. What the shot camera can't see is dimmed; scatter,
   paint coverage and simulation report "seen by the camera" first.
6. **Preview ≡ export.** The viewport's Final look, `look_frame quality=final` and the Render button are one render
   path (the core's Cycles engine at the same settings).
7. **Fail loudly.** A render, a simulation, a bevel that doesn't fit or an import that can't be read says what failed
   in plain words, in red, and never leaves a broken file that looks finished.
8. **Analyse once, store as data.** Simulations and UV unfolding are computed on request, stored, keyed by content +
   engine version; scrubbing and rendering only read them.

### What is new compared with today's 3D screen

Today's screen: `C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\apps\3d\app\` (H13–H22).

| # | Today | This spec |
|---|---|---|
| 1 | Outliner on the left with three tabs (Scene, Materials, Shots) | Scene list in the bottom panel's left column, lined up with its keys (2D's layers list); Materials = header chip + settings panel; Shots = the header crumb "Hero 01 ▾" |
| 2 | "+ Add" menu in the top bar | Icon rail on the left with flyouts (Shapes, Type & logo, Edit mesh, Paint, Lights, Camera, Simulate, Import) |
| 3 | Viewport bar floats over the picture (Shot camera, Exposure, Studio light, Scene lights, Contact shadows, DoF) | Nothing floats over the viewport except the gizmo and the brush. View options live in the Scene state of the settings panel; "View: Shot camera ▾" in the header |
| 4 | No way to move things in the viewport | One combined move / turn / scale gizmo; new things are placed by clicking on a surface |
| 5 | Inspector shows every applicable group open, long panels clip | Groups holding a changed value are open; the rest sit as one row of names ("Bevel · Shadow · Visibility") |
| 6 | Picking a material = a drop-down of ids; colours are hex | Material picker (project materials + starting points); colour = swatch + hex, swatch opens the kit's colour picker |
| 7 | Timeline: diamonds you can drag | 2D's timeline: clickable stretches, the settings panel becomes the animation (presets + curve), a second line only for overlaps |
| 8 | Render button = one Cycles still at default settings | Look: Quick / Final in the viewport; Render sheet (frame / shot / all shots, quality, size, passes) with a measured time estimate; a queue on the Render page |
| 9 | One shot on screen (`--shot-id`) | Several shots; switch with the crumb; each has its own camera, range and render settings |
| 10 | Modelling = primitives, text, SVG, 2D paths | Plus cone, capsule, booleans, edit faces (extrude, inset, bevel, loop cut), smooth subdivision, copies and scatter, painting on models, simulation |

---

## 1 · The window

```
┌ ≡ Rostrum3D  Aurora › Hero 01 ▾  [Build|Animate|Render]  Saved   ↶ ↷  Look: Quick|Final  View: Shot camera ▾  Materials  [Ctrl K]  Render  ? ┐
├────┬──────────────────────────────────────────────────────────────────────────────────────────┬────────────────────────────┤
│ ↖◢ │                                                                                          │ SETTINGS                   │
│ ▢◢ │   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │ (what is selected:         │
│ T◢ │   ░░┌──────────────────────────────── Hero 01 ─────────────────────────────────┐░░░░   │  an item, several items,   │
│ ◇◢ │   ░░│                                                                         │░░░░   │  faces, an animation,      │
│ 🖌◢ │   ░░│            the shot camera's picture (Quick or Final)                   │░░░░   │  a material, the Scene)    │
│ ── │   ░░│            outside the frame: the scene, dimmed                         │░░░░   │                            │
│ ☀◢ │   ░░└─────────────────────────────────────────────────────────────────────────┘░░░░   │                            │
│ 🎥◢ │   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │                            │
│ ≋◢ │                                                                                          │                            │
│ ⇩◢ │                                                                                          │                            │
├────┴──────────────────┬───────────────────────────────────────────────────────────────────┴────────────────────────────┤
│ ▶ 1.20 s / 5.00 s ⟲ ◇ │ 0s     0.5s     1s  ▼  1.5s     2s      2.5s     3s ⚑logo lands   4s       4.5s                 │
│ ▾ ▣ case              │        ◆──────⌒──────◆                                                                          │
│   ◧ lid               │                ◆────⌒────◆                                                                      │
│   ◯ bud_L             │                      ◆───⌒───◆                                                                  │
│ T AURORA              │                                       ◆──⌒──◆                                                   │
│ ☀ key  ☀ rim  ◌ sky   │                                                                                                 │
└───────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Why this layout (follows the 2D v2 window, so a person who learnt 2D knows 3D; C4D and KeyShot both keep the
viewport as the big centre with one attribute panel at the right):** the viewport gets every pixel that isn't a
control, the tools sit beside it but never on it, and the scene list's rows line up with their keys, so you never read
across two lists. *Effective:* the shot is never covered. *Efficient:* every control is one eye-move from the picture.
*Easy:* each area has one job, and it's the same job in 2D.

### 1.1 Sizes

Fixed areas, as the brief: header 44 · rail 48 (icons only) · settings panel 300 at 1646 (280 min, 340 at 1920 and
up) · bottom panel with a 240 px scene list column. The bottom panel's height depends on the page:

| Page | Bottom panel | Why |
|---|---|---|
| Build | **204 px** (header row 30 + 6 rows of 28 + foot): scene list + the keys on the same rows | Six rows show a product scene's top level; building needs the viewport tall |
| Animate | **284 px** (header row 30 + 9 rows) | Timing work needs rows |
| Render | **204 px**: shots list (left) + render queue (right) | The picture is the point of this page |

The viewport (centre) and the shot frame inside it, 16:9 shot, 16 px clear on the tighter side:

```
window     page            viewport      shot frame inside it
1646x900   Build/Render    1298 x 652    1102 x 620
1646x900   Animate         1298 x 572     960 x 540
1280x720   Build/Render     952 x 472     782 x 440      (settings 280)
1280x720   Animate          952 x 392     640 x 360
1366x768   Build/Render    1038 x 520     867 x 488      (settings 280)
1366x768   Animate         1038 x 440     725 x 408
1920x1080  Build/Render    1532 x 832    1422 x 800      (settings 340)
1920x1080  Animate         1532 x 752    1308 x 736
```

**The viewport is never letter-boxed with empty bands.** Unlike a 2D canvas, a 3D view has something to show outside
the frame: the scene itself, dimmed to 35 % (C4D's and KeyShot's "safe frame" darkening). So the 2D rule "the frame
drives the layout" becomes "the frame is fitted inside the viewport, and the margin shows the scene". A 9:16 shot keeps
the timeline below too (the dimmed scene fills the sides); no side arrangement is needed. *Built for the camera:* you
always see what's in the picture and what's just out of it.

**The person's sizes win**, as in 2D: dragging the settings panel's edge or the bottom panel's top edge sets that size
(remembered per page in the user's view settings, never in the document); double-click the edge gives it back.

**Layout check:** `apps\3d\app\layout_states.py` **(new)** lists each page × selection state (nothing, mesh, text,
light, camera, rig, two solids, faces, an animation, material picker open, Render sheet, paint mode, simulate) at the
four sizes.

### 1.2 The header

Left to right:

1. **≡** menu (New, Open, Open recent, Save as, Guides, Licences).
2. **Rostrum3D**, then the crumb **project › shot ▾**: "Aurora › Hero 01 ▾". Click opens the shots list: each shot
   (name, size, length), **+ New shot from this view**, Rename, Duplicate, **Send to 2D**, **Send to Editor**
   (§12). Choosing a shot switches the viewport to its camera and the timeline to its range. *Why a crumb:* a shot is
   "where you are", like 2D's scene, not a tab of a list.
3. **Build | Animate | Render** page tabs (Ctrl+1 / 2 / 3). Same document, same viewport camera, same selection.
4. **Saved · N changes** (click: History in the settings panel's place).
5. Right: **↶ ↷**, **Look: Quick | Final** (and **Stylized**, only when a material uses a stylized block, §6.4),
   **View: Shot camera ▾** (Shot camera · Free camera · Through the selected light / camera · each other camera),
   **Materials** chip (the project's materials, §6.1), **Search or run a command (Ctrl K)**, **Render** (F12), **?**.

A running job (render, simulation, unfolding) shows as the kit's job chip in place of "Saved" with "frame 34 of 120 ·
2 min left" and a ✕ to cancel.

### 1.3 What each panel shows on each page

| Area | Build | Animate | Render |
|---|---|---|---|
| Rail | Select, Shapes, Type & logo, Edit mesh, Paint, Lights, Camera, Simulate, Import | Select, Poses, Bones, Onion skin, Lights, Camera, Simulate | Select, Camera (focus pick, look through) |
| Viewport | Quick (or Final when chosen) | Quick, with the motion path of the selected item and onion skins | Final, progressive, through the shot camera |
| Settings panel | The selection (§3) | The selection; a clicked stretch = the animation (§9.3) | The shot's render settings + estimate (§11.3); a selected item still shows its settings |
| Bottom left | Scene list | Scene list | Shots list (check boxes: what "All shots" renders) |
| Bottom right | Keys on the same rows (short) | Full timeline, markers, Simulate row | Render queue |

---

## 2 · The tool rail and flyouts

Icon only, 48 px, outside the viewport. Hover shows name + key. A small corner triangle marks a flyout; the
**last-used tool sits on the group icon**, and pressing the group key again cycles its tools (2D's rule, from
Figma / Illustrator). A flyout shows icon + name + key, opens beside the rail at the icon's height, closes on a pick,
Esc or a click elsewhere. After placing a shape or light, the tool returns to Select; Paint stays on.

| Group | Key | Flyout holds | Notes |
|---|---|---|---|
| **Select** | V | Select & move (all handles), Move only (W), Turn only (E), Scale only (S) | The combined gizmo (arrows, rings, corner cubes) is the default, as in Spline and Plasticity; the three single gizmos are for precise work, as in C4D |
| **Shapes** | R | Box, Sphere, Cylinder, Cone **(new)**, Torus, Capsule **(new)**, Plane, Disc | Click on a surface places it there (§4.1) |
| **Type & logo** | T | 3D text, Logo from SVG, From a 2D drawing | §4.4 |
| **Edit mesh** | Tab | Points (1), Edges (2), Faces (3), then the actions Extrude, Inset, Bevel, Loop cut, Knife | Shown only when a mesh is selected; Tab enters and leaves (§4.3) |
| **Paint** | B | The painting kit's brushes, Eraser (E in paint mode), Fill, Pick colour (I), Smudge | Shown only when a mesh is selected or under the pointer (§5) |
| — | | | |
| **Lights** | L | Softbox, Strip, Round softbox, Spot **(new)**, Bulb, Sun, Sky (HDRI), Light card | §7 |
| **Camera** | C | Camera, Orbit rig, Crane rig, Dolly rig, Handheld (toggle on the selected rig) | §8 |
| **Simulate** | — | Falls (rigid body), Stays still (collider), Cloth, Particles from this surface | Acts on the selection straight away, like 2D's Sound flyout (§10). Smoke & fire join when built |
| **Import** | Ctrl+I | USD, glTF, FBX, OBJ, Alembic, A 2D item (as a picture or extruded), Asset library | Dragging a file onto the viewport works at any time |
| *Animate page* | | **Poses** (P), **Bones** (shown when a mesh is selected), **Onion skin** (O, a toggle) | §9 |

**Disagreement with BRIEF (rail):** the brief lists **Sculpt (later)** and **Smoke & fire** in the rail. By rule 1 a
tool that doesn't work isn't shown, so Sculpt joins the rail (between Edit mesh and Paint) on the day it works, and
Smoke & fire join the Simulate flyout then. Edit mesh and Paint appear only when they can act (a mesh exists).

**Navigation needs no tool** (there is no Hand tool): middle-drag orbits around the point under the pointer, Shift+middle
pans, wheel zooms toward the pointer; Alt + left / middle / right do the same for pen and laptop users (Maya / C4D's
keys). Orbiting while "View: Shot camera" switches the view to Free camera and says so in the header ("View: Free
camera ▾"); the shot camera never moves by accident (a lesson from C4D, where people nudge the render camera).
**Ctrl+Alt+0** puts the shot camera where the free view is (asks nothing; one undo step).

---

## 3 · The settings panel and right-click

### 3.1 What it shows

| Selection | Settings panel shows |
|---|---|
| Nothing | **Scene** (§3.4) |
| One item | That item's settings by kind (mesh, text / logo, light, camera, rig, group, import, part) |
| Several items | **Actions** that fit the mix, then shared values with *Mixed* (§3.3) |
| Faces / edges / points (Edit mesh) | The selection count and the edit actions with their numbers (§4.3) |
| A stretch between two keys | **The animation** (§9.3) |
| A material (from the Materials chip, or "Edit" on a Material row) | The material's settings (§6) |
| A shot (crumb or the Render page's shots list) | The shot: camera, range, size, frame rate, background, motion blur |
| A marker | Its name, time, colour (shared markers: the name and a chain; moved in the app that owns it) |
| Paint mode | The brush, then the paint layers of the mesh (§5) |

**Header line** (2D's): kind icon · **name** (click to rename) · kind in grey ("case  Box"; "AURORA  3D text";
"2 solids  Box, Cylinder", each kind a link that narrows the selection).

### 3.2 Groups: open if changed, the rest as one row of names

The kit's settings grid (2D spec §8.0): label | field | key diamond, 28 px rows, one value per row, pairs only for
X | Y | Z position (three thirds here, the one place three fit, because a 3D position is one thing) and size.

The rule for 3D, where one item has many groups (a material has seven):

1. **The kind's own group is always open** (Shape for a mesh, Light for a light, Lens for a camera, Rig for a rig):
   it is the thing itself. **Position** and **Turn** follow rule 2 like every other group (Turn absent while Aim is
   on); since a shape lands where you click (§4.1), Position is almost always changed and so open.
2. **Any other group that holds a non-default value is open**, in importance order.
3. **The rest sit as one row of names** under the open groups: "Bevel · Scale · Aim · Shadow · Visible". Click a name:
   that group opens in place and stays open while the item is selected (and becomes "changed" the moment you change
   something). Hover a name: a tip lists what's inside ("Aim: point, item, roll").
4. A group whose fields are all `deep` importance sits after the names under **More** (one row).

*Example, the case (a bevelled box with a material):* Shape (Width 0.064, Height 0.030, Depth 0.048, Bevel 0.004 —
open, own group) · Position · Turn · Material (swatch "Matte black" ▾ — open, changed) · then
"Scale · Aim · Smooth · Visible". Eleven rows, no scrolling at 900 px.

*Lead's ruling:* the kind's own group is always open (otherwise a fresh box needs a click before its size can be
typed); every other group, Position and Turn included, opens only when changed, as in 2D.

**Values:** drag a label to scrub (Shift ×10, Alt ×0.1); type maths (`0.064*2`, `+5`); units are typed or shown
("6.4 cm" is accepted and stored as metres; the panel shows centimetres when the value is under 1 m, as KeyShot does).
**Colour:** swatch + hex in one field; the swatch opens the kit's colour picker (square, hue, eyedropper over the
viewport, project swatches). **Item references** (aim at, lights only, follow) are a field with the item's name and a
target icon: click the target, then click the thing in the viewport or the scene list (2 clicks, no ids typed).

**Renderer badges.** A setting the Quick look can't show (anisotropy, sheen, coat tint, light spread, light linking)
carries a small "Final" tag after its label. Changing it while Look is Quick shows one line under the header for 4 s:
"Shows in Final (F)". *Why:* Lull friction 6/15/17: an agent and a person both lost time on settings that did
nothing visible in the look they were using.

### 3.3 Several items: actions first

| Selection | Actions (top, in this order) | Then |
|---|---|---|
| 2+ solids (mesh, text, logo) | **Combine:** Union · Subtract · Intersect (live, §4.2) · **Group** · **Copy material from…** | Align (to first / to floor / centres), shared values |
| Anything + a surface (mesh / plinth / floor) | **Scatter on 'plinth'** (§4.5) · **Drop onto 'plinth'** (sits each on the surface below it) | — |
| A light + items | **Light only these** (sets `lightsOnly`) · **Aim at** | Shared values |
| A camera + an item | **Aim at 'case'** · **Focus on 'case'** · **Orbit 'case'** (puts the camera on an orbit rig around it) | — |
| Any 2+ | **Group** (Ctrl G) · Align · Distribute (3+) · Stagger (when 2+ have animations) | Shared Position / Turn / Scale |
| A group | **Ungroup** (Ctrl Shift G) · Make copies (§4.5) | Group settings |
| One item | Make copies · Simulate › … (only on the item's right-click and Ctrl K; not on the panel) | — |

**Hovering an action previews it in the viewport** (Subtract shows the cut in a red-tinted ghost before you press;
2D's rule). Shared values: equal values show plainly, different ones show *Mixed*; typing sets all, scrubbing adds
the same amount to each.

### 3.4 Nothing selected: the Scene

Everything that was floating over the viewport, plus the shot:

| Group | Rows | Open when |
|---|---|---|
| **Shot** | Hero 01: camera, frame rate, length, size (one row "1920 × 1080 · 24 fps · 5.00 s"; click opens the shot) | Always |
| **View** | Exposure (stops), Contact shadows (on → strength), Studio light (only while the scene has no sky of its own), Scene lights, Dim outside the frame (on) | Always (it's the viewport's own) |
| **Sky** | The scene's dome: HDR image, Turn, Seen by the camera | When a sky exists; else a row "Sky +" |
| **Simulation** | "Drop 03: 12 bodies · stored · up to date" / "out of date" + **Simulate** | When the scene has simulated items |
| **Ground** | A shadow-catcher floor: on / off, height, shadow strength **(new)** | Row of names |

View settings are screen state (never the document, never undone), as today.

### 3.5 Right-click (≤ 6 items, only those that apply)

On an item in the viewport or the scene list: **Duplicate** (Ctrl D) · **Delete** (Del) · **Group** (Ctrl G) ·
**Frame it** (F) · **Look through** (cameras and lights only) · **Copy material** / **Paste material** (meshes only:
one item that says Paste when a material was copied). Six at most, from one action list (the same rows Ctrl K finds).
On empty viewport: **Paste** · **Frame all** (Home) · **New shot from this view**.

---

## 4 · Job a: modelling

### 4.1 From primitives

**The case, from nothing — 3 clicks + typing four numbers:**

1. Click **Shapes** (1) → flyout opens, the last-used shape on top (mockup 2).
2. Click **Box** (2). The pointer shows a small box ghost that sits on whatever surface is under it (the plinth's top,
   the ground grid), lying flat on it.
3. Click on the plinth (3): a box of the **scene's size class** sits there, selected, its gizmo shown, the settings
   panel showing Shape open. *Size class:* the first shape in an empty scene is 10 cm (product scale, a choice the
   person makes once in the empty-scene line "Product · Room · Landscape"); after that, a new shape is a fifth of the
   thing it was placed on. **Drag instead of click** = draw the footprint on the surface, release, then move the
   mouse up for height and click (SketchUp's push / pull, Womp's drop-on-surface).
4. Type Width 6.4 cm, Height 3 cm, Depth 4.8 cm, Bevel 4 mm (Tab between fields).

*Why:* effective (exact sizes typed, rounded edges by default, since "real products almost never have razor edges" is
already the field's help); efficient (no "add at origin, then move up onto the plinth" detour: C4D adds at the origin,
which is almost never where you want it); easy (it lands where you clicked). We differ from Spline (adds at the
centre of the view) because a product film is always built *on* something.

Screen at each step: (1) flyout; (2) ghost under the pointer, surface highlighted thin blue; (3) the box, gizmo,
settings panel; (4) the viewport updates live while scrubbing.

**Operations:** `mesh.add` (exists; new args: placement is computed by the screen from a pick, sent as `x y z rx ry
rz`); the core's pick gives point and **surface direction** **(new reply field `normal` on pick)**. Cone and capsule
are new mesh shapes **(Data change; core `primitives.cpp`)**.
**Agent:** `run_script` `mesh("case", shape="box", width=.064, height=.03, depth=.048, bevel=.004)`; to place on a
surface: `place_on` **(new script helper and op arg `on="plinth"`)**, which drops the item onto the named item's
top; then `look_frame` to see it.

### 4.2 Booleans (Manifold), live

**Cut the charging port into the case — 3 clicks + one drag:** select the case (1), Shift+click a small capsule
placed as the cutter (2), **Combine › Subtract** at the top of the settings panel (3) (mockup 9). Drag the cutter
afterwards to move the hole: the result stays live.

- The result is a **combine** item named "case" (the first selected) holding both as children; the scene list shows it
  as a group with a Combine icon; the cutter row is indented with a minus sign. Selecting the cutter shows it as a
  thin outline in the viewport; it is never rendered.
- The combine's settings: Operation (Union / Subtract / Intersect), **Bevel the cut edges** (a fillet width, Manifold
  + our outline bevel; absent until built), **Bake** (turns it into one plain mesh; one undo step).
- A cut that leaves nothing, or a non-closed input, fails loudly: "Subtract gave an empty shape: 'cutter' covers
  'case' entirely" / "'lid' is not a closed solid (an import part with holes), so it can't be combined".

*Why live:* effective (product shapes change late); efficient (no re-doing the cut after a resize); easy (the cutter
is just another item you move). Follows Plasticity / Spline (live booleans) and 2D v2 §8.3. Not a rail tool (brief).

**Operations:** `combine.make(items, op)` **(new)**, `combine.set` **(new)**, `combine.bake` **(new)**.
**Data change:** item type `combine` (holder, `op`, children). Core: Manifold (Apache-2.0) builds the result once per
change (cached by the children's content + engine version).
**Agent:** `run_script` `combine("case", op="subtract", items=["body", "port"])`; `look_frame` + `look_at` on the
port to check the cut is where it should be.

### 4.3 Edit mesh: extrude, inset, bevel, loop cut, knife, smooth

**Push the lid's top face up 2 mm and round it — 6 clicks + one drag:**

1. With the lid selected, press **Tab** (or click **Edit mesh**, 1). The settings panel says "Turns the box into an
   editable mesh · Edit" only the first time for a shape with size fields; click **Edit** (2). (The box's Width / Height
   fields go; a **Back to box** action appears and stays until you save and close, then it's an undo step like any.)
2. Click **Faces** (3) in the flyout or press 3, click the top face (4); it tints blue.
3. **Extrude** (5): drag the arrow that appears on the face up (one drag), or type Distance 2 mm in the panel.
4. Press 2 (edges), Ctrl+click the loop around the top (6), **Bevel**: type Width 1 mm, Segments 4.

Faces selected → the panel shows "1 face" and the actions that fit, each with its numbers below once used: **Extrude**
(distance, along the face / along each face), **Inset** (width, depth), **Delete**, **Material** (a face set gets its
own material, as text already does). Edges selected: **Bevel** (width, segments, shape), **Loop cut** (count, slide),
**Mark seam** (for painting, §5). Points: **Merge**, **Snap to grid**. **Knife** is a tool: click points across faces,
Enter. Each action is one undo step and leaves its numbers editable until the next action (C4D's "last command"
idea, without a floating box).

**Smooth (subdivision):** a mesh's Shape group gets **Smooth surface: Off / 1 / 2 / 3** and **Keep edges sharp**
(per-edge crease from the bevel's edges). Uses OpenSubdiv through USD's subdivision scheme, which Storm and Cycles both
read. One row, no modifier stack.

*Why:* effective (the four actions cover hard-surface product work; Plasticity and C4D show that's enough); efficient
(Tab in, number keys 1–3, out; the actions live where the numbers are); easy (no modifier stack to learn; only the
actions for the current selection type are shown). We don't copy Blender's mode menu: Tab is the only mode.

**Operations:** `mesh.edit` **(new: shape → `poly` with points / faces, one step)**, `faces.extrude`, `faces.inset`,
`edges.bevel`, `edges.loopcut`, `mesh.knife`, `faces.delete`, `faces.material`, `points.merge` **(all new)**;
`mesh.set smooth=…` **(new field `subdivide`, `creases`)**. **Data change:** mesh shape `poly` holding points, faces,
face sets, creases, seams, UVs. Selections of faces / edges / points are screen state; agents name them by
**selectors** (`"top"`, `"faces facing +y"`, `"edges of face set lidTop"`) so a script doesn't depend on face numbers.
**Agent:** `edit_document` with those operations and selectors; `look_frame` with `highlight="faces facing +y"`
**(new arg)** to see what a selector picks before acting.

### 4.4 Text and logo extrusion (built: text / svg / path2d)

**"AURORA" — 3 clicks + typing:** **Type & logo › 3D text** (2 clicks), click on the plinth's front (3): a text
cursor appears in the viewport, type AURORA, Esc. The text stands upright facing the shot camera (never flat on the
floor: Lull friction 7, the agent couldn't tell mirrored from upside-down). The panel (mockup 3): Text group (font,
weight, size, tracking, align — always open), **Depth** and **Bevel** (open), **Face materials** row of names
("Front · Bevel · Side · Back"; clicking one gives it its own material picker).

**Logo:** **Type & logo › Logo from SVG** (2), pick the file (3), click where it goes (4). **From a 2D drawing**: pick the
2D item and its path layer in a two-level list (4 clicks); it stays linked to the 2D drawing: change the drawing in
Rostrum2D and the 3D logo updates.

A bevel too big fails loudly as today, and the field shows the largest that fits under it in red ("at most 1.84 mm
here") with one click to use it.

**Operations:** `mesh.add shape=text|svg|path2d` and `mesh.set` (exist; `outline*.py`, core `extrude.*`).
**Agent:** exists; add to `look_frame`'s reply for text: which way it reads from the camera ("reads left to right,
upright") **(new)**.

### 4.5 Copies and scatter

**Twelve buds in a row — 3 clicks + one number:** select the bud (1), right-click › **Make copies** (2, 3): the bud
becomes a **copies** item holding it, with Kind (Line · Grid · Circle · On a surface), Count, Spacing (or Radius),
and **Vary** (position, turn, scale ranges, seeded). Type Count 12.

**Scatter pebbles on the plinth — 3 clicks:** select the pebble (1), Shift+click the plinth (2), **Scatter on
'plinth'** (3). Settings: Count (or Density), Spacing (minimum distance, no overlaps), Vary, **Only where the camera
sees** (on by default: built for the camera), **Seen count** in grey ("212 of 400 in Hero 01").

**Effectors** (C4D's idea, plain names): a copies item's **Change near…** row: pick an item (a sphere, a plane) and
what changes near it (scale, turn, push, colour) with a falloff distance. Keyable, so a wave runs through the copies.

**Operations:** `copies.make`, `copies.set`, `copies.effector.add` **(all new)**. **Data change:** item type `copies`
(holder + layout + seed + effectors); the core gets instances (USD point instancer; Storm and Cycles both instance).
**Agent:** `run_script` `copies("buds", of="bud", kind="line", count=12, spacing=.03)`; `look_coverage` reports seen
count (§13).

### 4.6 Import

**Import › glTF** (2 clicks), the file (3), it lands on the surface under the viewport's centre, scaled to fit the
scene's size class if its units are off ("Imported 'earbud.glb' at 1/100: it was in centimetres" shown once, with
**Keep original size** as a one-click undo). Dragging a file onto a surface in the viewport places it there.
Parts show indented under the import (today's `part`), each with its own material picker and visibility.
**Asset library:** the flyout's last row opens a sheet in the settings panel's place: CC0 sources the person has
switched on (Poly Haven, ambientCG), with thumbnails, search, size. Nothing downloads until clicked.

**Operations:** `import.add` (exists for USD; **new formats** glTF via USD's plug-in, OBJ, FBX via ufbx (MIT),
Alembic via USD's plug-in), `import.set scale` (exists through `sx sy sz`). **Agent:** `inspect_usd_file` (exists;
extend to every import format **(new)**).

---

## 5 · Job b: painting textures on models

The shared painting kit (`C:\Users\Sam\Documents\CODE\Rostrum\shared\painting-kit\`): the same brushes, layers,
strokes-as-data and agent tools as 2D Draw. What 3D adds: the canvas is a mesh's surface.

**Paint a worn edge on the lid — 2 clicks, then strokes:**

1. With the lid selected, click **Paint** (B) (1). If the lid has no good UVs, it is **unfolded for you** (xatlas,
   one job, a second for a product part; the job chip says "Unfolding lid…"); nothing is asked. Seams you marked in
   Edit mesh are kept.
2. The settings panel becomes paint mode (mockup 6): **Brush** (the kit's brush list as a picker row, size, opacity,
   colour swatch + hex; the kit's `fields.BAR` rows), then **Layers** (+ new layer; each layer: name, **Paints:**
   Colour · Roughness · Height · Metal · Glow, opacity, blend, eye). Click the first layer's "Paints" and pick
   Roughness (2).
3. Paint on the lid: the brush cursor (a disc lying on the surface, sized in screen pixels or millimetres, one toggle)
   follows the surface. Each stroke is one undo step.

**Paint from the camera** (one toggle in the Brush group: **On the surface | From the view**): strokes are drawn flat
on the view and projected onto whatever they cover, across meshes and seams (for painting through the shot camera
exactly what it sees, and for sweeping strokes across several parts).

**Projection painting** (PLAN tool 3, the painted background wrapped onto simple shapes): select the simple shapes
(room walls, a ground plane), right-click › **Project a picture from Hero 01**, choose a 2D drawing or an image (3
clicks + choosing). The picture lands on the shapes from the shot camera; moving the camera then shows depth. The
picture stays linked: repaint it in Rostrum2D, it updates.

**Coverage** (built for the camera): in paint mode the viewport tints, for the active layer, what the shot camera
sees but isn't painted yet (a faint orange hatch), and the Layers group's header reads "Seen by Hero 01: 62 % painted".
A toggle **Show coverage** turns the tint off.

**Materials meet paint:** a material row "Base colour" shows "Painted (2 layers)" when a colour layer covers it, and
the paint sits over the material's own value where painted.

*Why:* effective (Substance's layer-per-channel model, which is what painters know; Pinkman / Arcane-style work needs
colour, roughness and height painted); efficient (no unwrap step, no "create texture" dialog: Womp and Substance's
auto-UV first-run); easy (one mode, the same brushes as 2D). We differ from Substance by putting paint on the item
(the model you click), not on a separate texture set.

**Operations:** the kit's `paint.add / set / move / remove`, `stroke.add / set / remove`, `fill.set`,
`paintmask.add` (exist, registered with `canvas_types=("mesh",)`); `mesh.unfold` **(new, a job)**;
`stroke.add` gains `space: "surface" | "view"` with the view's camera **(new arg)**: a view stroke is stored as
drawn and projected when the canvas is made, so it stays editable; `project.picture(items, camera, source)` **(new)**.
**Data change:** a mesh may hold a paint canvas (`paints`, `paintmasks`, UV size, default 2048) and `uvs`.
**Agent:** `edit_document` with `stroke.add` batches in surface pixels *or* view pixels of a `look_frame` picture;
`look_paint` **(new)** shows the canvas unfolded with a grid, or the model from any view; `look_where` (surface spot
→ screen) and `look_at` (screen → surface spot + UV) **(look_at gains `uv`)**; `look_coverage` (§13).

---

## 6 · Job c: materials

### 6.1 Where materials live

- **On a mesh:** its Material row, swatch + name ▾ (mockup 4). Below it, the material's own changed groups, inline,
  with a grey line "Used by 3 items" when shared; editing changes every user (that's what sharing means);
  **Make its own** splits it off (one click).
- **The Materials chip** (header): the project's materials as a list in the settings panel's place (swatch ball,
  name, how many use it). Click one to edit it; drag one onto an item in the viewport to give it that material;
  **+ New**; right-click: Duplicate, Rename, Delete (users go to none, in the same step, as today).

### 6.2 Picking — 2 clicks

Click the Material row's swatch (1): the picker opens under it: **This project** (ball previews rendered in Quick, one
row each), then **Start from** (2): Plastic · Rubber · Metal · Brushed metal · Glass · Frosted glass · Ceramic ·
Fabric · Car paint · Screen (glows a picture) · Painted (ramp) · Ink & flat. Choosing a starting point makes a **new
material** from those values, named after the item ("case material"), and assigns it. Then the panel shows its
settings; change anything.

*Starting points, not looks* (tools, not taste): each is the physical settings of a substance (glass = transmission 1,
IOR 1.5, roughness 0), never a colour scheme or a lighting look. There is no "Moody chrome". The list is short because
the settings do the rest.

### 6.3 The settings (today's fields, sorted by the §3.2 rule)

Surface (Base colour / image, Metallic, Roughness) always open; Glass, Coat, Sheen, Brushed, Relief, Glow, Thin film as
the row of names until changed. **Brushed metal** = Metallic 1 + Brushed (amount, along: uv / around x y z, turn);
**frosted glass** = Glass + Roughness: both exist (`material_fields.py`). Images: a path field with a small preview and
**Choose…**; a 2D item's render as a screen picture is "Glow from 2D item" (exists).

### 6.4 Blocks (MaterialX) and stylized blocks

A material's last row: **Edit as blocks**. The bottom panel switches to the **block view** (its full height, the
timeline returns with Esc or the ‹ Back at its top left): the material as nodes, the output at the right, today's
settings as one "Surface" block. Add blocks from a list on the left (search as you type): Image, Noise, Mix, Ramp,
Curve, Colour adjust, Bevel shading, Ambient occlusion, and the **stylized blocks**:

| Block | Does | Renderer |
|---|---|---|
| **Light to colour** | Chosen colours for lit, mid and shadow (steps or smooth), from the real light and cast shadows | Cycles (proven in `proofs\3d-painterly`), Stylized |
| **Halftone** | Dots or lines whose size follows the light | Stylized |
| **Hatching** | Pen strokes in the shadows, density by darkness | Stylized |
| **Paper** | Paper grain over the surface, in screen space | Stylized |
| **Brush strokes** | Breaks light / shadow edges into dabs | Stylized |
| **Ink lines** | Outline and creases: width, colour, taper, wobble, crease angle | Stylized |

When a material uses a Stylized-only block, the header's Look gains **Stylized** (and Render's quality offers it).
Ink lines are also offered without blocks: a material's row of names includes **Lines** (the block's same settings),
because outlines are the first stylized thing people want.

*Why:* effective (the stylized look is ours to build, PLAN's tools 5, 8, 9); efficient (most materials never need
blocks; the panel covers them); easy (blocks only when asked, in the wide bottom area, not a separate window: C4D and
KeyShot's material graph is a separate window, which on a 1646 px screen covers the viewport).

**Operations:** `material.add / set / assign / remove` (exist); `material.from(start)` **(new: a starting point's
values as one `material.add`)**; `material.split(item)` **(new)**; `graph.add / connect / set / remove` **(new)**.
**Data change:** a material may hold a block graph (MaterialX document, with our stylized nodes as a MaterialX node
library); a material without a graph stays today's one-surface material. **Agent:** `run_script`
`material("alu", start="brushed metal", baseColor="#c9ccd1")`; `look_frame quality=final` (glass, metal, coat need
Final); `look_material` **(new)**: one ball / one plane turntable of a material under the scene's lights, for
checking a material alone.

---

## 7 · Job d: lighting

**Key light for the case — 3 clicks + one click on the case:**

1. **Lights › Softbox** (2 clicks).
2. Click on the case where you want its **highlight** (3). The softbox is placed so its reflection lands there, seen
   from the shot camera, at a distance of 4 × the case's size, aimed at the case, **with a starting brightness worked
   out from that distance** so the first look is neither black nor white (Lull friction 5: the agent needed eight
   tries to find 0.004).
3. The panel shows Light (colour swatch + hex, Intensity, Exposure, Temperature), Shape (width, height), and the row
   "Spread · Card · Lights only · Shadow".

**Place highlight** (HDR Light Studio's and KeyShot's best idea): with any light selected, **Alt+click** on a surface
moves the light so its highlight (or, for a sun, the lit side) lands where you clicked. One click per adjustment.

**The rim — strip:** **Lights › Strip** (2), click the case's back edge (3): a 1.2 × 0.15 m strip behind, standing
upright (Roll 90 is set for strips placed behind; the roll after aim exists). Mockup 5.

**Sky (HDRI):** **Lights › Sky** (2): the Sky group opens in the Scene state with the image picker (the project's
images and the asset library's skies). **Turn it:** Ctrl+Shift+drag left / right anywhere in the viewport turns the
sky live (KeyShot's Ctrl-drag); the Turn field follows. Seen by the camera: toggle (off = it lights and reflects, the
shot background shows).

**Light card:** **Lights › Light card**: a softbox with Visible card on, for a bright panel seen in reflections.

**Spot (new):** cone angle, softness; for a pool of light.

**Light linking:** the light's **Lights only** row: item chips + a target icon (click items in the viewport); or
select the light and the items, **Light only these** (§3.3). The rim lighting only the case: 3 clicks.

**Look through the light:** right-click › **Look through** (2 clicks): the view becomes the light's view (what it
shines on is the middle); orbiting moves the light (C4D / Blender convention). Esc returns. Exists today in the viewport
(`through.py`).

**Light mixer (Render page, later):** the Scene state on the Render page lists every light with one Exposure slider
and Solo (KeyShot's light manager), so balancing three lights isn't three selections.

*Why:* effective (lights are placed by the highlight they make, which is what a product photographer judges);
efficient (one click to place and aim); easy (no light starts black or blown out).

**Operations:** `light.add / set` (exist, all kinds and fields incl. strip, card, spread, lightsOnly, turn,
seenByCamera); `light.place_highlight(light, item, point)` **(new: computes x y z + aim from the camera and the
surface's direction)**; `light.add kind=spot` **(new kind; USD shaping cone)**; starting brightness = `light.add`'s
default worked out from distance and the scene's exposure **(new rule in the add op)**.
**Agent:** `run_script` `light("key", kind="rect", ...)` plus `place_highlight("key", on="case", at=(x, y))`
**(new)** in pixels of the last look; `look_frame through="key"` (exists); `look_frame` reply gains **"clipped: 3 %
of pixels"** and **"applied in Final: spread on rim, linking on rim"** **(new)** (Lull 5, 6, 15).

---

## 8 · Job e: cameras and shots

**A camera and a shot from where you are looking — 2 clicks:** orbit the free view to a good angle, then **Hero 01 ▾ ›
+ New shot from this view** (2): a camera is made at the view, a shot "Shot 2" with it (rename by typing; 1920 × 1080,
24 fps, 5 s from the first shot's settings), and View switches to Shot camera.

**Lens:** the Lens group: **Focal length** with a list of real lenses (24, 35, 50, 85, 105, 135 mm; type any),
Sensor (Full frame 36 mm, Super 35, Micro 4/3, under More).

**Focus — 2 clicks:** turn on **Depth of field** (1) (f-stop and Focus appear); click the target icon on the Focus row
and then the case in the viewport (2): focus distance set to that point. **Focus on item** (the target held with Alt):
focus follows the item as it moves (stored as `focusItem` **(new)**). The f-stop row shows the blur preview live in
Quick (exists: viewport DoF through a scene camera).

**Motion blur:** the shot's row of names gets **Motion blur** (Shutter: 180° default, i.e. half a frame; off by
default) **(new field; USD camera shutter open / close; Cycles reads it, Quick shows none and says "Final" tag)**.

**Rigs — 3 clicks:** select the camera (1), **Camera › Orbit rig** (2), click the case (3): the camera now rides an
orbit around the case's middle; the panel shows Rig (distance, height, angle, pan, tilt) and Handheld as a name.
Crane and dolly the same way (dolly: the track runs the way the camera looks). **Handheld:** the toggle on any rig
(amount, speed). Turntable: key Angle 0 → 360 (or the rig's **Turn once over the shot** action, which writes those two
keys).

**Several shots per scene:** each shot = camera + range + size + render settings. "Hero 01", "Close 02", "Drop 03" in
the crumb; the Render page's shots list. A camera may serve several shots. Shots share the scene and its animation;
a shot's range is a window of the scene time (exists: `start`, `end` in seconds).

*Why:* effective (real lenses, real f-stops, a focus you pick); efficient (camera from view in 2 clicks, rigs in 3);
easy (rigs are named for what a camera operator does). Follows C4D's camera + rig tags and KeyShot's camera list; the
orbit-around-the-clicked-thing is Spline's.

**Operations:** `camera.add`, `camera.set`, `rig.add`, `shot.add`, `shot.set` (exist); `shot.from_view(view)`
**(new: one step = camera.add + shot.add)**; `camera.set focusItem` **(new field)**; `shot.set motionBlur`
**(new field)**; `rig.wrap(camera, kind, around)` **(new)**.
**Agent:** `inspect_shot` (exists), `look_frame` (exists), `look_shots` **(new)**: one contact sheet row per shot.

---

## 9 · Job f: animation and simple rigs (Animate page)

The 2D v2 timeline, unchanged in behaviour (2D spec §9): one row per item, keys as diamonds, a slim bar from first to
last key, **a stretch between two keys is clickable**, a second line only where animations overlap, shared markers as
flags.

**The lid opens 0.8–1.6 s — 4 clicks + one drag:**

1. Click the lid (1). Move the playhead to 0.8 s (click the ruler, 2).
2. Click the ◇ on **Turn X** (3): animating starts, a key at 0.8 s.
3. Move to 1.6 s (4), drag the lid's rotate ring 105° up (one drag): a key at 1.6 s (value.set at the playhead on an
   animated setting adds a key; exists).

The stretch appears between them. **Click the stretch** (mockup 7): the panel becomes the animation: header "‹ Turn ·
lid · Turn X", From → To (0° → −105°), Start, Length, **easing presets** (Linear, Smooth, In, Out, Spring, Bounce,
Hold) and the **curve** with two handles. One click on "Out" eases it.

**Key everything I just moved — K:** after moving an item with the gizmo while it's not yet animated, **K** keys its
Position, Turn and Scale at the playhead (C4D's record key). The diamond stays the way to key one setting.

**Snap to markers:** keys and stretches snap to marker flags; the logo's landing key dropped on "logo lands" ties to
it (it moves if the music moves; exists in the kit's marker model).

**Onion skin (O):** ghosts of the selected item at the previous and next keys (or ±2, ±4 frames: one choice in the
timeline header's ◌ menu), tinted, in the viewport. For timing a lid's arc by eye.

**Poses (Animate rail, P):** select items (a hand's bones, a lid and buds), **Poses › Save pose** (names it); the
flyout lists saved poses as thumbnails; click one = keys at the playhead for every field the pose holds. Breakdown
(Shift+click a pose): 50 % between the neighbouring keys, a slider in the panel for the share.

**Stepped timing:** an item's (or group's) row of names has **Timing: Smooth · On 2s · On 3s** (holds every key's
value for n frames between; the camera can stay smooth while the character steps: PLAN tool 12).

**Constraints:**
- **Aim** (exists): at a point or an item, with roll.
- **Follow** **(new)**: rides on another item from a time (picking up a bud, a lid hinge); a "Follow" group with the
  item and a keyable Amount, so it can let go.
- **Stick to surface** **(new)**: stays on a surface below as it moves.

**Parenting and pivots:** drag a row onto another in the scene list = put it inside (its world place kept; exists:
`item.arrange`). **Pivot:** hold **D** with the gizmo: drag the gizmo to set where the item turns around (the lid's
hinge) without moving it (C4D's axis mode). **Data change:** items gain `pivotX/Y/Z` **(new fields)**.

**Simple bone chains (now):** **Bones** (Animate rail, mesh selected): click points along the mesh to place a chain
(a strap, a cable, a tail), Enter. The mesh is bound with automatic weights; each bone is a row with Turn keys.
**Auto-rig for humanoids** joins later (PLAN): a "Make a humanoid rig" action on a humanoid mesh.

**Lip sync from Sound:** a mouth (a set of mouth shapes: swapped meshes or blend shapes) gets **Lip sync from…**
(right-click › Lip sync): pick a voice line from RostrumSound (its word and sound markers): mouth keys are written
on the timeline (2D's lip-sync sheet, the same shape table), one undo step, editable after.

*Why:* effective (the curve and presets are the craft of timing; onion skin and poses are PLAN tool 14);
efficient (the stretch is the handle; K keys a whole move); easy (identical to 2D). Follows After Effects / Rive for
the stretch, C4D for the record key and axis mode, Maya for poses and breakdowns.

**Operations:** `key.add / remove / clear / set`, `value.set` (exist, `rostrum_core.keys`); `anim.list`, `anim.ease`,
`key.scale`, `key.stagger`, `key.paste` (exist **in 2D only**: `apps\2d\python\rostrum2d\anims.py`, `ops_anim.py`;
must move to `rostrum_core`, Team Sam); `key.record(items, at)` **(new)**; `pose.save / apply / remove`
**(new; Data change: doc-level `poses`)**; `item.set timing` **(new field)**; `follow.add / set`, `stick.add`
**(new)**; `bone.chain(mesh, points)`, `bone.bind` **(new; Data change: `bone` items, USD skel)**; `lipsync.make(mouth,
voice line)` **(new, reusing 2D's)**.
**Agent:** `run_script` `.key("rx", {0.8: 0, 1.6: -105}, ease="out")` (exists); `look_sheet` (exists);
`look_motion` **(new)**: the motion check (§13).

---

## 10 · Job g: simulation

**Twelve buds fall into a bowl, shot "Drop 03" — 5 clicks:**

1. Select the twelve buds (click the first, Shift+click the last in the scene list: 2).
2. **Simulate › Falls** (2 clicks, 4): they become rigid bodies (each row gets a small falling-arrow badge; the panel
   gains a **Simulation** group: Mass (from size, as solid plastic), Bounce, Friction, Starts: Moving / Asleep until
   hit, Shape: Exact (convex) / Box / Sphere).
3. Select the bowl, **Simulate › Stays still** (the bowl and the plinth are colliders; the ground is one by default).
4. A **Simulate** row appears at the bottom of the timeline (mockup 10): "Not computed · **Simulate**". Click it (5).

**Simulate** runs as a job: the row fills left to right as frames are computed (Jolt is fast: a second or two for
twelve buds); scrub any time during it. Done: the row is a solid bar, "Stored · 120 frames · seen by Drop 03: 12 of 12
at rest in frame". Scrubbing and rendering read the stored result; nothing recomputes on its own.

**Out of date:** change a mass, move the bowl, a key under a body: the bar turns striped, "Out of date · Simulate". The
viewport keeps showing the old result. **Render with an out-of-date simulation** doesn't silently use it: the Render
sheet shows a line "Drop 03's simulation is out of date — it will be computed first" and the job does that first
(rule 6: never a broken file with success). **A failure** (bodies start inside each other, a body flies away, no
collider under them) stops the job with the reason and the frame: "bud_7 starts inside the bowl at frame 0: move it
up 4 mm or set Starts: Asleep".

**Stylize** (PLAN tool 16), the Simulation group in the scene (nothing selected): **Timing: Every frame · On 2s · On
3s** (stepped like hand animation), **Simplify** (keeps every nth sample, smooth between), and **Turn into keys**:
the result becomes ordinary keys on each body, editable like any animation, and the simulation is switched off (one
undo step). Nudge one bud's final position by hand after that.

**Cloth** (Simulate › Cloth on a plane or mesh): Weight, Stiffness, Pinned edge (pick points); colliders as above.
**Particles from this surface:** an emitter on the selected mesh: Rate, Life, Speed, Size, What (a small mesh or a
sphere), Gravity; computed and stored the same way. **Smoke & fire** (OpenVDB + Mantaflow) and **liquids**: later,
same flow.

*Why:* effective (real physics, stylizable, and editable after "Turn into keys"); efficient (5 clicks; computing is
one click, never on every scrub); easy (Falls / Stays still are what a person means; no "active / passive"). Follows
C4D's dynamics tags (set on the object), Houdini's good part (results stored as data you can cache and edit) and
Blender's cache bar (studied, not copied).

**Operations:** `sim.body(items, kind="falls"|"still"|"cloth")`, `sim.emitter.add`, `sim.set` **(new)**; `sim.run(shot)`
**(new, a job)**; `sim.to_keys` **(new)**. **Data change:** a `simulation` record per scene (inputs, frame range,
engine version) whose result lives in the content-keyed cache (`rostrum_core.cache`, kind "sim", key = inputs' content
+ Jolt + engine version), referenced by key from the document; out of date = the key doesn't match. Jolt (MIT).
**Agent:** `simulate` **(new, a job)**: shot, range → job id; `inspect_job` shows frames n of m; the reply on done:
key, frames, bodies at rest, seen-by-camera count, any body leaving the frame; `look_sheet` to see it.

---

## 11 · Job h: rendering

### 11.1 The viewport always shows a picture you can trust

- **Look: Quick** (Storm, about 60–90 pictures a second at 1298 × 652, measured H20): framing, motion, layout.
- **Look: Final** (F to switch): the viewport becomes **progressive Cycles in place**, same camera, same size, getting
  cleaner every pass, with a thin progress line under the header ("Final · 64 of 256 samples · 12 s"). Orbiting or
  editing restarts it from a coarse picture (as KeyShot does; KeyShot's whole viewport is this). The quick view never
  lies about lights: a light the Quick look can't show is named in a one-line note on switching ("Quick doesn't show:
  spread on rim").
- **Look: Stylized** (only when used, §6.4).

### 11.2 The Render button (F12): the sheet

Opens the kit's export sheet in the settings panel's place (mockup 8). Top to bottom:

| Row | Choices | Default |
|---|---|---|
| **Render** | This frame · Hero 01 (0–5 s) · A range · All shots (3) | This frame on Build, the shot on Animate / Render |
| **Quality** | Draft · Good · Final (segmented); **More** opens the numbers: samples (32 / 128 / 512), noise clean-up (on), light bounces (4 / 8 / 12), motion blur samples | Good |
| **Size** | The shot's 1920 × 1080 · ½ · × 2 (3840 × 2160) | The shot's |
| **Save as** | PNG (sRGB) · EXR layers for the Editor · MP4 preview | PNG for a frame, EXR for a shot |
| **Passes** (EXR only) | Beauty (always) · Light · Shadow · Reflections · Masks per item · Depth · Surface direction (row of names; ticked ones open) | Beauty + Masks |
| **Estimate** | "About 6 min · 120 frames · 3 s a frame on the RTX 3050" | measured, below |
| | **Render** (Enter) | |

**The time estimate, how it's measured:**
1. When the sheet opens (and again 0.4 s after any change that alters the picture, not just the numbers), the core
   renders **one probe frame**, the shot's middle frame, through the same path and settings as the real job, at a
   quarter of the pixels (so it takes about a quarter of the time), in the background job slot.
2. Time per frame = probe time × (real pixels ÷ probe pixels), plus the measured fixed cost (scene build, noise
   clean-up, which don't shrink with pixels; the probe times them separately), plus encoding for MP4 (0.15 s a frame,
   today's `ENCODE_S_PER_FRAME`). Changing only Quality samples or Size re-scales the number at once with no new probe
   (time follows samples and pixels: `apps\3d\python\rostrum3d\mcp\estimate.py`, which exists).
3. While the probe runs the row says "Measuring…"; it never shows a guess as if measured. If another job is using the
   graphics card, it says so: "another render is running on the card: about 2× slower now".
4. **During the render** the job chip and the queue row replace the estimate with the real numbers, re-estimated from
   the frames done so far: "frame 34 of 120 · 2 min left".
5. The probe's picture is kept and shown small in the sheet: the person sees what they're about to render.

*Why one small probe and not "1 tile" (disagreement with BRIEF, small):* Cycles on a GPU renders the whole picture in
passes rather than tile by tile, and a tile from the sky and a tile from the glass cost very different amounts. A
whole frame at a quarter of the pixels samples the real mix of the picture, and the existing `render_video` probe
(within about 10 % of the real time, `apps\3d\python\rostrum3d\guides\agents.md`) already works this way at full size.

**Budget:** the estimate row is a link: click it to type a budget ("10 min"); over it, the row lists the one-setting
changes that fit ("samples 96 · or size ½ · or Draft"), each a click (exists in `estimate.py` as `fitting_settings`).

### 11.3 The Render page

- **Header:** the Render button is absent on this page (the settings panel's Render is the same action; a control
  never shows twice).
- **Settings panel:** the selected shot's render settings (the sheet's rows, saved on the shot, so each shot keeps its
  quality and passes: **Data change**, `shot.render` fields) and its estimate. **Render** and **Add to queue**.
- **Bottom left:** the shots list (Hero 01, Close 02, Drop 03), each with a tick for "All shots", its length and its
  last render's time and date. Right-click a shot: **Send to 2D**, **Send to Editor**, Open its folder.
- **Bottom right:** the **queue**: one row per job (shot, quality, size, a progress bar with frames n of m, time left,
  ✕ cancel), then finished renders (time taken, the folder; click: the last frame over the viewport, as today's
  RenderView). One job runs at a time on this laptop (one heavy job per machine); the rest wait in order; drag to
  reorder. Cancel ends that job's engine by its handle, leaves a `.partial` folder that is never listed, and says
  "Render cancelled" (exists).
- **Viewport:** Final, progressive, through the shot camera.

**Operations:** render is a job, not a document change: `render.still` and `render.video` (exist as MCP tools
`render_still`, `render_video` and the screen's `render_job.py`); `render.queue.add / move / cancel` **(new, screen
state + project jobs queue from the shared project service)**; `render.estimate(shot, settings)` **(new, same probe
as `render_video estimate_only`)**; `shot.set render…` **(new fields)**; render passes as AOVs in the core
**(new: core `image_out.*` writes a layered EXR; Hydra AOVs)**.
**Agent:** `render_still`, `render_video` with `estimate_only` and `budget_min` (exist); `render_estimate` **(new:
for a still, a shot or all shots, without starting)**; `inspect_job` (exists).

---

## 12 · Job i: export to the Editor and 2D

**Send a shot to the Editor — 2 clicks:** Hero 01 ▾ (1) › **Send to Editor** (2). If the shot has no current render,
a small sheet says "Hero 01 has no render of its current state · Render now (about 6 min) · Use the last one (from 3
changes ago)", one click. The render is a **layered EXR sequence** (shared\HANDOFFS.md: scene-linear, one file per
frame, passes as layers, a manifest), and the Editor gets a **live linked clip**: when Hero 01 is rendered again, the
clip updates and says so.

**Send to 2D — 2 clicks:** the same, to a chosen 2D scene: it becomes a 2D "3D render" layer (exists in 2D:
`render3d` layers), transparent where the sky isn't seen by the camera (exists: `seenByCamera` off → alpha 0).

**Out of date is by content:** the render manifest carries a hash of the scene as rendered; 2D and the Editor compare
it to the 3D document's current hash, not history steps (Lull friction 16: an identical re-run said "out of date").

**Markers:** the timeline shows the project's shared markers; keys tied to "logo lands" follow it. A 3D shot adds no
markers of its own to the project unless the person makes one shared (M, then the Shared switch).

**2D into 3D (exists):** "Glow from 2D item" on a material plays a 2D render on a screen; From a 2D drawing (§4.4).

**Operations:** `shot.send(target="editor"|"2d", scene)` **(new: a render if needed + a link item in the target
document through the project service's live links, `rostrum_gui/live_link.py` already exists in the kit)**; the
render manifest's `scene_hash` **(new)**. **Agent:** `render_still / render_video formats=["exr"]` (exist);
`render_send_shot` **(new; the shared tool names allow only run / inspect / edit / render / look)**; the send reply reports the link and the render used (`inspect_project` is shared and has no per-app hook yet).

---

## 13 · Job j: agents' tools to see and act

### 13.1 Existing (`apps\3d\python\rostrum3d\mcp\`, plus the shared ones from `rostrum_core.mcp`)

| Tool | Input | Returns |
|---|---|---|
| `run_script`, `edit_document`, `edit_undo`, `edit_markers` (shared) | a script / operations | changes applied, removals listed, errors in words |
| `inspect_guide`, `inspect_operations`, `inspect_tools`, `inspect_item`, `inspect_project`, `inspect_history`, `inspect_markers`, `inspect_job`, `inspect_screen` (shared) | — | the API, the document, jobs, what the screen shows |
| `inspect_shot` | shot | frame rate, range, size, camera, every light |
| `inspect_usd_file` | a USD file | its parts, materials, sizes |
| `look_frame` | shot, frame, quality fast / final, renderer, `through` a light | a PNG through the shot camera, same path as export |
| `look_sheet` | shot, count, range | a contact sheet labelled with frame and time |
| `look_at` | x, y (or `points`) of a picture | item, part, material, world point, distance |
| `render_still` | shot, frame, formats png / exr, quality | a job → a project render version with manifest |
| `render_video` | shot, range, quality, `estimate_only`, `budget_min` | a job → mp4; the estimate from a probe frame; settings that fit a budget |

### 13.2 Needed (each **new**)

| Tool | Input | Returns | Why |
|---|---|---|---|
| `look_where` | item, a surface point (world or UV), shot, frame | where it lands on screen (x, y), whether it's seen or hidden behind something | PLAN "the reverse"; placing highlights, paint, labels |
| `look_at` (extended) | as now | + `uv`, surface direction, face set, painted layer there | paint and edit selectors |
| `look_coverage` | item (or all), shot, layer | a picture: painted / unpainted / seams / unseen by the camera, + numbers ("62 % of what Hero 01 sees is painted") and for copies / scatter "212 of 400 seen" | Paint what the camera sees first |
| `look_motion` | shot, items | per item: path drawn over a frame, speed curve, stops, sudden jumps, frames where it leaves the frame, overlaps / intersections (a bud through the case) | 2D's motion check, for 3D |
| `look_paint` | item, layer, region, grid | the unfolded canvas with a labelled grid, or the model from a view with the paint | Agents paint for real (PLAN) |
| `paint_strokes` | item, layer, strokes in `surface` pixels or `view` pixels of a given look, brush | one undo step; per stroke: what it landed on and how far off (`where.landed`) | The kit's strokes, with 3D landing |
| `look_material` | material | a ball or plane turntable under the scene's lights | Check a material alone |
| `look_shots` | shots | one contact sheet row per shot | Several shots at a glance |
| `render_estimate` | shot(s) or frame, settings | seconds per frame, total, how measured, what's slowing it, settings that fit a budget | Lull 12 / 20: no false starts |
| `simulate` | shot, range | a job; on done: frames, bodies at rest, seen count, failures with frame and item | Compute once, on request |
| `render_send_shot` | shot, target 2d / editor, scene | the link made, the render used | Hand-offs |
| `look_frame` (extended) | as now | + "clipped: n % of pixels", "applied in Final: …" / "not in Quick: …", text reading direction | Lull 5, 6, 7, 15 |

**Rule for every look tool:** it says what it measured and with which renderer; a tool that can't do what was asked
fails with the reason (no picture of the wrong thing).

---

## 14 · Keyboard map

| Key | Does |
|---|---|
| V | Select & move (combined handles) · W move only · E turn only · S scale only |
| R | Last-used shape (R again cycles) |
| T | 3D text (last-used of Type & logo) |
| Tab | Edit mesh on / off · 1 points · 2 edges · 3 faces (in Edit mesh) |
| B | Paint (mesh selected) · E eraser · I pick colour · [ ] brush size (in Paint) |
| L | Last-used light · Alt+click place highlight · Ctrl+Shift+drag turn the sky |
| C | Camera · Ctrl+Alt+0 shot camera to this view |
| D (hold) | Move the pivot with the gizmo |
| Middle-drag · Shift+middle · wheel | Orbit · pan · zoom (Alt + left / middle / right as well) |
| F · Home | Frame the selection · frame all |
| \` | View: Shot camera ↔ Free camera |
| Shift+F | Look: Quick ↔ Final |
| Ctrl+1 / 2 / 3 | Build / Animate / Render |
| K | Key what moved on the selection at the playhead |
| O · P | Onion skin · Poses (Animate) |
| Space · Ctrl+← / → · , / . | Play · frame step · previous / next key or marker |
| M | Add a marker |
| Ctrl+G · Ctrl+Shift+G | Group · Ungroup |
| Ctrl+D · Del | Duplicate · Delete |
| Ctrl+C / V | Copy / paste (items; animations when stretches are selected) |
| Ctrl+Z / Ctrl+Shift+Z | Undo / redo |
| F12 · Ctrl+Enter (in the sheet) | Render sheet · start |
| Ctrl+I | Import |
| Ctrl+K · Ctrl+F | Search / run anything · find a setting or item |
| Esc | Leave a mode (edit mesh, paint, look through) · back from an animation · deselect |
| F1 · Ctrl+/ | Guides · key list |

**Clash check with 2D:** V, R, T, B, C, M, Space, Ctrl+G, Ctrl+K, Ctrl+I mean the same in both apps; K, Tab, W, E, S, D
are 3D-only.
F means "fit selection" in both; in 3D Shift+F switches the look (KeyShot has no such key; C4D uses Ctrl+R for an
in-view render). The shared key map (INTERACTION.md Part 2) gains the 3D column.

---

## 15 · Conventions we follow, and where we differ

| From | We follow | Why |
|---|---|---|
| **Cinema 4D** | Attributes in one right panel; dynamics and constraints set *on* the object; cloners and effectors (as "copies" and "change near…"); the record key (K); axis mode for pivots (D); camera + rig as objects; the dimmed outside of the safe frame | The motion-design 3D standard; its object-centred model fits our operations |
| **KeyShot** | Progressive final render in the viewport; materials by drag-drop and from starting points; Ctrl-drag to turn the sky; a light mixer; one-click camera views | Product rendering is our first job |
| **Spline / Womp** | Combined move / turn / scale gizmo; live booleans; things land on the surface you click; a calm dark UI with a right panel | Simplicity for people who don't do 3D |
| **Plasticity** | Few precise modelling actions with numbers; 1 / 2 / 3 for points / edges / faces; live, editable results | Hard-surface product modelling without clutter |
| **Houdini (its good parts)** | Simulation computed once and stored as a cache you can inspect; procedural copies with seeds; everything is data an agent can read | Rule 7; agents |
| **HDR Light Studio** | Place a light by clicking where its highlight should be | Product lighting is judged by highlights |
| **Substance Painter** | Layers per channel (colour, roughness, height); automatic UVs on first paint | What texture painters know |
| **Blender** | Studied only: Tab for edit mode is a widely shared convention (also in other tools); the simulation cache bar idea | Never copied (GPL) |
| **Ours** | Rule of individuality everywhere (Edit mesh and Paint absent until they apply); open-if-changed groups; actions on the selection with hover preview; the measured time estimate; renderer badges ("Final"); shots as the header crumb; sending shots as live links | Each removes a step or a second place to look |

**What we don't take:** Blender's and Maya's mode menus, modifier stacks and tool shelves; C4D's floating managers and
separate material window; Houdini's node network as the main way to build (blocks only for materials); any panel of
finished looks, lighting presets passed off as tools, or demo scenes to copy.

---

## 16 · What exists today vs what the spec needs

Checked in `C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\apps\3d\` (paths below are relative to it) and the shared
kit `C:\Users\Sam\Documents\CODE\Rostrum\shared\` on 2026-10-24.

### The window and kit

| Piece | State | Where today |
|---|---|---|
| Header (shot name, Render, history, Ctrl K) | Partial | `app\qml\Main.qml`, kit `TopBar.qml`, `CommandBar.qml` |
| Page tabs Build / Animate / Render | Missing | — |
| Tool rail + flyouts | Missing in 3D; **exists in 2D only** | `C:\Users\Sam\Documents\CODE\Rostrum\apps\2d\screen\qml\ToolRail.qml`, `ToolFlyout.qml` (must move to the kit) |
| "+ Add" menu | Exists (to be replaced) | `app\qml\AddMenu.qml`, `app\screen3d\adding.py` |
| Settings panel from field data, key diamonds, pickers for references | Exists | kit `Inspector.qml`, `InspectorRow.qml`; `app\screen3d\bridge3d.py`, `route.py` |
| Open-if-changed groups + row of names | Missing | kit `Inspector.qml` / `rostrum_gui\sections.py` |
| Actions at the top for a multi-selection, hover preview | Exists in the kit for 2D | kit `ActionsSection.qml`, `ActionsPreview.qml`, `rostrum_gui\actions.py` |
| Colour swatch + hex, colour picker | Exists in the kit | kit `SwatchHex.qml`, `ColorPicker.qml` |
| Scene list in the bottom panel | Partial (outliner on the left) | `app\qml\Outliner.qml`, `app\screen3d\outline.py` |
| Viewport bar over the picture | Exists (to be moved into the Scene state) | `app\qml\Viewport.qml` |
| Job chip, export sheet | Exist in the kit | kit `JobChip.qml`, `ExportSheet.qml`, `rostrum_gui\export_sheet.py` |
| Layout check | Kit exists; 3D states missing | kit `rostrum_gui\layout_check.py` |

### a. Modelling

| Piece | State | Where |
|---|---|---|
| Box, sphere, cylinder, plane, disc, torus with bevel / segments | Exists | `core\src\primitives.*`, `python\rostrum3d\fields.py` |
| Cone, capsule | Missing | — |
| Place on a surface by click; pick with surface direction | Partial (pick gives item + point) | `core\src\hydra.*` (pick), `python\rostrum3d\mcp\look.py` (`look_at`) |
| Move / turn / scale gizmo | Missing | — |
| Booleans (Manifold) | Missing | — |
| Editable mesh, extrude, inset, bevel edges, loop cut, knife | Missing | — |
| Smooth subdivision | Missing | — |
| 3D text, SVG logo, 2D path with bevel and face materials | Exists | `python\rostrum3d\outline*.py`, `core\src\extrude.*`, `outline_offset.*` |
| Copies, scatter, effectors | Missing | — |
| Import USD with parts and overrides | Exists | `python\rostrum3d\fields.py` (`import`, `part`), `core\src\stage_items.*` |
| Import glTF, OBJ, FBX, Alembic; unit rescale | Missing (units "not rescaled" per README) | — |

### b. Painting

| Piece | State | Where |
|---|---|---|
| Brush engine, strokes as data, layers, masks, agent see / where | Exists (2D) | `shared\painting-kit\rostrum_paint\` (`brush.py`, `canvas.py`, `see.py`, `where.py`) |
| Canvas on a mesh, UV space | Missing | — |
| UV unfolding (xatlas) | Missing | — |
| Paint on the surface / from the view, coverage | Missing (proven by hand in `proofs\3d-painterly`) | — |
| Painted textures under real light in Cycles | Proven | `C:\Users\Sam\Documents\CODE\Rostrum\proofs\3d-painterly\README.md` |
| Tangent-space normal maps | Missing (Cycles' Hydra delegate builds no tangents) | proof notes |

### c. Materials

| Piece | State | Where |
|---|---|---|
| One principled material: colour, metal, roughness, glass, coat, sheen, brushed, bump, glow, thin film, images | Exists | `python\rostrum3d\material_fields.py`, `core\src\materials.*`, `material_nodes.*` |
| Face materials on text / logos | Exists | `core\src\extrude.*` |
| A 2D render playing on a screen | Exists (frame-by-frame playback not yet seen working) | `material_scene.py`, ENGINE_CONTRACT.md § 2 |
| Material picker with starting points | Missing (a drop-down of ids) | `bridge3d.py` `_rows` |
| Blocks (MaterialX graph) | Missing | — |
| Light-to-colour ramp | Proven in Cycles, not in the app | `proofs\3d-painterly` |
| Halftone, hatching, ink lines, brush strokes | Proven in our stylized renderer, not wired ("takes no look settings through the contract yet") | `proofs\3d-stylized`, `README.md` § Open |

### d. Lighting

| Piece | State | Where |
|---|---|---|
| Rect, disk, strip, bulb, sun, sky; colour, intensity, exposure, temperature | Exists | `python\rostrum3d\light_fields.py`, `core\src\lights_cameras.cpp` |
| Spread, visible card, light linking, sky turn, sky not seen | Exists (Final; patched Cycles) | `light_fields.py`, `core\src\light_extras.*`, `cycles_lights.*`, `libs\cycles-rostrum.patch` |
| Aim with roll | Exists | `python\rostrum3d\aim.py`, `fields.py` (`roll`) |
| Look through a light | Exists | `python\rostrum3d\through.py`, viewport, `look_frame through=` |
| Spot | Missing | — |
| Place highlight, starting brightness by distance | Missing | — |
| "Applied in Final" / clipped % in replies | Partial (`notInQuickView` in the view reply) | `core\src\hydra.*` view reply |

### e. Cameras and shots

| Piece | State | Where |
|---|---|---|
| Focal length, sensor, depth of field, f-stop, focus distance, clipping | Exists | `fields.py` (`camera`) |
| DoF in the Quick view | Exists | `core\src\view_post.*` |
| Orbit / crane / dolly rigs, handheld | Exists | `python\rostrum3d\rig_fields.py`, `rigs.py`, `guides\camera-rigs.md` |
| Several shots in the document | Exists | `fields.py` (`shot`) |
| Several shots on screen, crumb, camera from view | Missing (`--shot-id` picks one) | `app\main.py` |
| Click to focus, focus on item | Missing | — |
| Motion blur | Missing | — |

### f. Animation and rigs

| Piece | State | Where |
|---|---|---|
| Keys, easing table, evaluator, key ops | Exists | `rostrum_core\keys\` (shared), `python\rostrum3d\ops_keys.py` |
| Timeline with diamonds, drag, markers | Exists (H13 style) | `app\qml\Timeline.qml`, kit `Timeline.qml`, `KeyRows.qml` |
| Clickable stretches, animation panel, presets + curve, overlap lines | **Exists in 2D only** | `apps\2d\screen\qml\StretchBand.qml`, `AnimPanel.qml`, `EaseCurve.qml`, `LayerTimeline.qml`; `apps\2d\python\rostrum2d\anims.py`, `ops_anim.py` |
| Parenting | Exists (`item.arrange`) | `python\rostrum3d\ops_items.py` |
| Pivots, onion skin, poses, stepped timing, follow, stick | Missing | — |
| Bones and binding | Missing | — |
| Lip sync | Exists in 2D only | `apps\2d\screen\qml\LipSyncSheet.qml`, `rostrum2d\voice_words.py` |

### g. Simulation

| Piece | State | Where |
|---|---|---|
| Rigid bodies (Jolt), cloth, particles, cache, stylize | Missing | — |
| Content-keyed cache | Exists (shared) | `rostrum_core\cache.py` |

### h. Rendering

| Piece | State | Where |
|---|---|---|
| Live Quick view (Storm) with contact shadows, DoF, exposure | Exists | `core\src\view_*`, `app\screen3d\viewport.py`, `app\qml\Viewport.qml` |
| Progressive Cycles | Exists in the core for renders | `core\src\hydra.*` (progressive loop) |
| Look: Final in the viewport | Missing | — |
| Render a still from the screen, cancel | Exists | `app\screen3d\render_job.py`, `app\qml\RenderButton.qml`, `RenderView.qml` |
| Video render, probe estimate, budget | Exists for agents only | `python\rostrum3d\mcp\render.py`, `estimate.py` |
| Render sheet, quality presets, size, shot render settings | Missing | — |
| Queue, several jobs | Missing | — |
| EXR (beauty), PNG through OpenColorIO | Exists | `core\src\image_out.*` |
| Passes (AOVs) as EXR layers | Missing | — |

### i. Export

| Piece | State | Where |
|---|---|---|
| EXR sequence + manifest by HANDOFFS numbering | Exists | `python\rostrum3d\mcp\render.py` |
| 3D render layer in 2D | Exists (2D side) | `apps\2d` `render3d` layers |
| Send to 2D / Editor actions, scene hash | Missing | — |
| Live links in the kit | Exists | kit `rostrum_gui\live_link.py` |

### j. Agent tools

Existing: §13.1, all in `python\rostrum3d\mcp\` (`look.py`, `render.py`, `facts.py`, `estimate.py`, `shot.py`,
`server.py`). Missing: every row of §13.2.

---

## 17 · Build order (45-minute briefs, feel the difference soonest)

Each brief ends with the layout check (`main.py --check-layout <folder> --quick`), pictures for Sam, the guides it
changes (`python\rostrum3d\guides\` and the MCP tool descriptions) in the same commit, and the agent side of what it
adds (rule 4). **[Kit]** = needs Team Sam's shared-kit change merged first. **[C++]** = needs a heavy core build
(through the heavy-job lock; one at a time).

### First: the shared kit (Team Sam, alone, merges first)

| # | Brief | Files touched | Done when (a person can see) |
|---|---|---|---|
| K1 | **Rail and flyouts into the kit** | move `apps\2d\screen\qml\ToolRail.qml`, `ToolFlyout.qml` → `shared\gui-kit\...\qml\`; 2D uses the kit copy | 2D looks and works exactly as before; the kit has a rail any app fills from a list |
| K2 | **The key timeline into the kit** | `StretchBand.qml`, `AnimPanel.qml`, `EaseCurve.qml`, `LayerTimeline.qml` → kit; `anims.py`, `ops_anim.py` (`anim.list`, `anim.ease`, `key.scale`, `key.stagger`, `key.paste`) → `rostrum_core\keys\` | 2D unchanged; a 3D item's keys can be eased by `anim.ease` from a script |
| K3 | **Open-if-changed groups** (an option of the kit inspector: own group open, changed groups open, the rest as a row of names) | kit `Inspector.qml`, `rostrum_gui\sections.py` | A 3D light shows Light, Position open and "Spread · Card · Lights only · Shadow" as names; 2D keeps its own setting |

### Then Rostrum3D (Team Hem)

| # | Brief | Files touched | Done when (a person can see) | Needs |
|---|---|---|---|---|
| 1 | **The window shell**: header (crumb, pages, Look, View, Materials chip, Render), rail with Shapes / Lights / Camera filled from today's add operations, scene list in the bottom panel, settings panel on the kit grid | `app\qml\Main.qml` (new layout), `Outliner.qml` → `SceneList.qml`, `AddMenu.qml` removed, `bridge3d.py`, new `layout_states.py` | Screenshots of the Aurora scene at 1280, 1366, 1646, 1920 match mockup 01; layout check passes | K1, K3 |
| 2 | **Nothing floats over the viewport**: the dimmed outside of the shot frame, View: Shot / Free in the header, the Scene state (View, Sky, Shot groups) replaces the viewport bar; right-click ≤ 6 | `app\qml\Viewport.qml`, `viewport.py`, `viewcam.py`, new `app\screen3d\scene_state.py` | Nothing selected → the Scene state as mockup 02; the frame's outside is dimmed; orbiting says "Free camera" | 1 |
| 3 | **The gizmo**: combined move / turn / scale, W / E / S, D for the pivot; K keys what moved | new `app\qml\Gizmo.qml`, `app\screen3d\gizmo.py`, `route.py`; `fields.py` pivot fields | Drag the case's arrow: it moves, one undo step; the panel follows live | 1 |
| 4 | **Place on a surface**: pick returns the surface direction; Shapes land where clicked, with the size class; cone and capsule | `core\src\hydra.*` (pick), `primitives.*`, `fields.py`, `adding.py` | Click Box then the plinth: a 10 cm box sits on it; a cone and capsule exist | 3, **[C++]** |
| 5 | **Type & logo flyout**: type text in place, SVG and 2D drawing pickers, bevel "largest that fits" one click | `adding.py`, new `app\qml\TypeInPlace.qml` | Type AURORA on the plinth; it stands upright, reads from the camera | 1 |
| 6 | **Live booleans (Manifold)**: `combine` item, Combine actions with hover preview | `python\rostrum3d\fields.py`, new `ops_combine.py`, `compile.py`; core new `boolean.*`, Manifold added (licence row) | Case + capsule → Subtract: the port is cut, moving the capsule moves the hole (mockup 09) | **[C++]** |
| 7 | **Editable mesh, part 1**: `poly` shape, Tab, points / edges / faces selection in the viewport, Extrude, Inset | `fields.py`, new `ops_mesh.py`, `mesh_select.py`; core `stage_items.*` (poly meshes) | Push the lid's top up 2 mm with a drag | 3, **[C++]** |
| 8 | **Editable mesh, part 2**: Bevel edges, Loop cut, Knife, face materials, Smooth surface (OpenSubdiv) with sharp edges | `ops_mesh.py`; core subdivision attributes | The lid's top edge rounds with 4 segments; Smooth 2 on a box gives a pebble | 7, **[C++]** |
| 9 | **Material picker and Materials chip**: project materials, starting points, inline groups, "Used by 3", Make its own, drag onto items | new `app\qml\MaterialPicker.qml`, `app\screen3d\materials.py`, `python\rostrum3d\material_starts.py`; ops `material.from`, `material.split` | Two clicks give the case Matte plastic; mockup 04 | 1, K3 |
| 10 | **Lights flyout done right**: place by highlight (Alt+click), starting brightness from distance, strip standing, Spot, light linking by clicking; "Final" badges; `look_frame` clipped % and "applied in Final" | `adding.py`, new `python\rostrum3d\highlight.py`, `light_fields.py`, `mcp\look.py`; core spot shaping | A softbox clicked on the case lights it at a sensible level first time; mockup 05 | **[C++]** (spot) |
| 11 | **Cameras and shots**: crumb with shots list, New shot from this view, lens list, click-to-focus, focus on item, rigs from the flyout, motion blur | `app\qml\Main.qml` (crumb), `bridge3d.py` (several shots), `fields.py` (`focusItem`, `motionBlur`), `rigs.py`; core camera shutter | Switch Hero 01 → Close 02 in two clicks; focus on the logo in two clicks | **[C++]** (shutter) |
| 12 | **Look: Final in the viewport**: progressive Cycles in place, progress line, restart on change | core `hydra.*` view request with renderer cycles, `app\screen3d\viewport.py`, `frames.py` | Press Shift+F: the viewport cleans up into the Cycles picture in place | **[C++]** |
| 13 | **Render sheet and the estimate**: what / quality / size / save as, the quarter-size probe, re-scaling, budget, probe picture; shot render settings saved | `app\screen3d\render_job.py`, new `estimate_job.py`, kit `ExportSheet.qml` content; `mcp\estimate.py`, `render.py`; `fields.py` shot render fields; `render_estimate` tool | F12 shows "About 6 min · 120 frames" before anything runs; mockup 08 | 12 |
| 14 | **Render page and queue**: shots list, queue with progress, cancel, reorder, last render over the viewport | new `app\qml\RenderPage.qml`, `app\screen3d\queue.py` (project jobs queue) | Queue Hero 01 and Close 02; the second waits; cancel one cleanly | 13 |
| 15 | **Passes as EXR layers** (Light, Shadow, Reflections, Masks per item, Depth, Surface direction) | core `image_out.*`, `hydra.*` AOVs; `render.py` manifest | The EXR opens with named layers in another program | **[C++]** |
| 16 | **Animate page with the kit timeline**: stretches, the animation panel, overlap lines, markers snap | `app\qml\Timeline.qml` → kit timeline, `bridge3d.py`, `outline.py` | Click the lid's Turn stretch: the panel is that animation with presets (mockup 07) | K2 |
| 17 | **Onion skin, stepped timing, poses**: ghosts in the viewport, Timing field, Poses flyout | `fields.py` (`timing`), new `ops_poses.py`, `compile.py` (holds), core ghost drawing in the view request | Onion skin shows the lid's arc; a bud steps on 2s while the camera stays smooth | 16, **[C++]** (ghosts) |
| 18 | **Follow and stick constraints, pivot hinge** | new `python\rostrum3d\follow.py`, `compile.py`, `fields.py` | A bud follows the lid, then lets go at 1.4 s | 16 |
| 19 | **Simple bone chains and lip sync** | new `ops_bones.py`, core skinning (USD skel); lip sync reusing 2D's sheet via the kit | A strap bends along three bones; a mouth follows a voice line | 16, **[C++]**, K2 |
| 20 | **Painting, part 1**: canvas on a mesh, automatic unfold (xatlas), paint on the surface, layers per channel | `fields.py` (mesh canvas), register `rostrum_paint` with `canvas_types=("mesh",)`, new `python\rostrum3d\unfold.py`; core UVs + painted textures | Paint a roughness scuff on the lid in Paint mode (mockup 06) | **[C++]** (xatlas, MIT) |
| 21 | **Painting, part 2**: paint from the view, projection from a camera, coverage tint; `look_paint`, `paint_strokes`, `look_coverage`, `look_where`, `look_at` uv | `mcp\` new `paint.py`, `coverage.py`; core UV pick pass | The coverage tint shows what Hero 01 sees unpainted; an agent's stroke reports where it landed | 20, **[C++]** |
| 22 | **Stylized blocks, part 1**: Light to colour (Cycles), Lines and Halftone (stylized renderer through the contract), Look: Stylized | `material_fields.py`, `compile.py`, ENGINE_CONTRACT.md; core stylized look settings | A cel-shaded case with ink lines in the viewport and in a render | **[C++]** |
| 23 | **Blocks view (MaterialX graph)** in the bottom panel | new `app\qml\BlockView.qml`, `python\rostrum3d\graph.py`, core MaterialX reading | A noise block drives roughness and shows in Final | 22, **[C++]** |
| 24 | **Copies and scatter** with "only where the camera sees" and Change near… | new `ops_copies.py`, `compile.py` (point instancer), `look_coverage` seen counts | Twelve buds in a line; 400 pebbles scattered, 212 seen | **[C++]** |
| 25 | **Rigid bodies (Jolt)**: Falls / Stays still, Simulate row, stored result, out of date, loud failures; `simulate` tool | new `python\rostrum3d\sim\`, core or a Python Jolt binding (to decide in the brief, MIT), `rostrum_core.cache` kind "sim" | "Drop 03": click Simulate, the buds fall into the bowl, scrubbing reads it (mockup 10) | **[C++]** |
| 26 | **Simulation stylize and cloth**: On 2s, Simplify, Turn into keys; cloth on a plane | `sim\` | The fallen buds become keys; one is nudged by hand | 25 |
| 27 | **Send to 2D / Editor** with the scene hash; live link status | `mcp\render.py` (hash in manifest), new `send.py`, kit `live_link.py`; 2D's `render3d.status` reads the hash | Send Hero 01 to a 2D scene; re-render; the 2D layer updates and is not "out of date" after an identical re-run | 13 |
| 28 | **Agent look tools left**: `look_motion`, `look_shots`, `look_material`; `look_frame` text reading direction | `mcp\look.py`, new `motion.py` | An agent's motion check flags a bud passing through the case | 16 |
| 29 | **Imports**: glTF, OBJ, FBX (ufbx), Alembic, unit rescale, asset library sheet | `fields.py` (`import`), core `stage_items.*`, new `app\qml\AssetSheet.qml` | Drop a .glb on the plinth: it lands at the right size | **[C++]** |

**Order, why:** 1–3 change everything Sam sees at once (the house; no data risk). 4–8 make modelling real; 9–11
materials, lights and cameras give a lit product shot; 12–15 make rendering trustworthy and measured before anything
long is rendered; 16–19 animation; 20–23 painting and the stylized look; 24–26 copies and simulation; 27–29 hand-offs
and the rest. K1–K3 must merge before 1, 9 and 16. At most two heavy teams at once, one heavy build per team: the
[C++] briefs 4, 6, 7 are best batched by the lead into one build each round.

**Tests (only where something would break silently):** a re-run script never moves an item a person dragged with the
gizmo; a live boolean re-made from the same children gives the same mesh (cache key includes engine version); a
stored simulation is reported out of date when an input changes and is never used silently; the estimate says
"measuring" until measured; a paint stroke batch is one undo step; Send to 2D's hash matches after an identical re-run.

---

## Where this spec differs from BRIEF.md (the lead's rulings in italics; all others accepted)

1. **Rail:** Sculpt (later) and Smoke & fire are left out until they work (rule of individuality); Edit mesh, Paint and
   Bones show only when a mesh is there (§2).
2. **Groups:** the kind's own group is always open, or a new box would need a click before its size can be typed
   (§3.2). *Lead: accepted for the kind's own group only; Position and Turn follow the changed rule.*
3. **Estimate:** one probe frame at a quarter of the pixels, not "1 tile", because Cycles on the GPU doesn't render by
   tiles in a way that represents the whole picture (§11.2).
4. **Build page bottom panel:** 204 px with keys still shown on the rows (2D's minimum), rather than a "thin
   timeline", so the scene list shows six rows (§1.1).
5. **Look:** a third choice, **Stylized**, appears only when a material uses a stylized-only block (§6.4).
