# Sculpting with clay

Clay is a lump you push into shape with brushes, the way you would with real modelling clay: draw a shape and it
puffs up into clay, then build it up, carve into it, smooth it out. You never deal with points or faces. Every stroke is kept (not just the result), so each one can be
undone, and the clay comes back exactly the same when you open the scene again.

## On the screen

1. Click **Clay** on the tool rail (the second button, under Select) or press **Q**. The settings panel shows the Clay
   tool: **Make**, and once a clay is selected, **Brush** with its settings. The rest of the window stays as it is.
2. **Make a clay.** The panel's **Make** row has the ways to start or add to a clay:
   - **Draw** (chosen when the tool turns on): drag a closed outline in the viewport and let go (the outline stays,
     filled grey, until the clay is built a moment later). It **puffs** into a
     soft clay shape, as thick in the middle as the outline is wide there (a circle becomes a ball, a strip a sausage),
     facing you. On empty ground it stands on the ground under the outline as a new clay, selected; its middle is
     where you drew it and **Mirror** runs down that middle. An outline that isn't closed is closed with a straight
     line; a tiny one (a click, a scribble) makes a round lump the brush's size instead. While Draw is on, a left drag
     always draws (it never turns the view): turn the view with the right button or two fingers. **Esc** while
     drawing drops the line: nothing changes.
   - **Join by drawing:** start the outline **on a clay** (a thin, light outline shows on the clay while the pencil is
     over it; the selected thing keeps its thicker one).
     The new shape joins that clay smoothly, at the depth of the surface where you started, and is mirrored to the
     other side when Mirror is on. Starting just off the clay still joins it if the shape overlaps or nearly touches.
   - **Puff:** after a drawn shape, **Puff** sits at the top of the panel until your next stroke: drag it lower for a
     flatter shape (a leaf, an ear), higher for a fatter one. Each change is one undo step.
   - **Spin:** a vertical line follows the pointer; drag half a profile out from it (the side of a vase, a bottle, a
     mushroom) and let go: the profile is spun round the line into a round shape. On a clay it joins it.
   - **Lump:** click to drop a ball of clay the brush's size (a hand-sized one, 20 cm across, on empty ground); on a
     clay it joins it, blended in softly. The pointer is a cross while Lump is chosen.
   - **Turn into clay** shows only when an exact part (a Shapes box, sphere …) or an import is selected, and on its
     right-click menu: it makes a clay copy of it beside it, ready for the brushes, and hides the original (hidden,
     not deleted: show it again from the scene list). One undo step.

   Each Draw, Spin, Lump or Turn into clay is one undo step.
3. **Pick a brush** in the panel. Six shape the clay:
   - **Add** builds clay up under the brush; **Carve** takes clay away; **Smooth** evens bumps out (a freshly drawn
     shape is smooth already, so there it changes little: use it over joins, stroke edges and lumps).
   - **Pull** grabs the clay under the brush and drags it along the stroke: a nose, a chin, an ear tip.
   - **Flatten** planes the clay towards its average surface: the planes of a face, a cut rock.
   - **Crease** pinches a sharp line or valley: lips, eyelids, folds.

   The seventh, **Mask**, on its own row, shapes nothing: it paints a mask on the clay, and no brush changes masked
   clay until the mask is taken away (hold **Ctrl** with Mask to take it off where you drag). Mask a part you have
   finished, then work right next to it without spoiling it. Rest the pointer on a tile to see what it does.
4. **Drag on the clay** to sculpt. A ring lying on the surface shows the brush: where it touches and how big it is,
   tilted with the surface. The fainter circle inside it is where the brush still works at half strength: it moves
   out towards the ring as Falloff goes up (a hard edge) and in as it goes down (soft).
   While the Clay tool is on, the clay you sculpt has no selection outline: the ring is its only mark. The clay changes under the pointer while you drag; when you let go, **the whole stroke is one undo step** (Ctrl+Z
   takes back exactly that stroke).
   - Hold **Ctrl** for the opposite: Add carves, Carve adds, Flatten puffs the clay out, Crease pinches it up into a
     ridge, Mask takes the mask away. (Smooth and Pull have no opposite.) As soon as Ctrl goes down the middle of the
     ring shows what a stroke will do now: **−** takes clay (or the mask) away, **+** adds.
   - Hold **Shift** to smooth, whatever brush is chosen.
   - **With a pen** (a drawing tablet), pressing harder makes the brush bigger and stronger, lighter makes it smaller
     and gentler, within Size and Strength. A mouse always uses Size and Strength as they are.
   - **Drag on empty space** to turn the view around the clay, so you can work on its other side between strokes; no
     need for the middle button; the pointer shows four arrows while it turns. The wheel zooms. A click on another thing selects it.
5. Under the brushes, **Size** and **Strength**; then the **Steps** list (below); then **More**, a fold that is closed
   at first and holds Falloff, Spacing, Front faces only and Mirror (it stays open or closed as you left it until the
   app closes):
   - **Size**: the brush's radius, in metres (0.03 m = 3 cm). Faster: rest the pointer on the clay, **hold F** and move
     the pointer right (bigger) or left (smaller); the ring shows the new size as you move, with the size in millimetres
     beside it, and letting go of F keeps it (one undo step).
   - **Strength**: how much one stroke changes the clay.
   - **Falloff**: how the brush fades towards its edge: low is soft (it blends in), high is a hard edge (a crisp step).
   - **Spacing**: how far apart the brush's touches are along a stroke, as a share of its size. Low gives an even,
     smooth stroke; high leaves a row of separate dents or bumps.
   - **Front faces only** (on at the start): a stroke only touches the side of the clay facing you, so it never
     reaches through a thin part (an ear, a fin) to the far side. Turn it off to work both sides of a thin part at once.
   - **Mirror**: **Left–right** (the start) makes every stroke on one side happen on the other side too, mirrored
     across the clay's own middle, so a face or a body stays even. **Off** sculpts one side only.
   These are the clay's settings for its next stroke: changing them never changes strokes already made (each stroke
   keeps the settings it was made with). Each change is one undo step.
6. **Esc** during a stroke cancels it: the clay goes back as it was and nothing is recorded. **Q** again, **V** or
   **Esc** (with no stroke under way) goes back to Select, and so does picking a shape from the rail (Box, Sphere …):
   the next click places the shape. The move handles are hidden while the Clay tool is on, so they
   never sit on the clay you are sculpting; with Select they are back.

## The Steps list

A clay's shape is its list of steps, in order: what you drew, spun or dropped, then every stroke. The **Steps** group
in the panel (under Size and Strength, above More) lists them, newest at the bottom, each by its name or what it is ("Drawn shape", "Spun shape", "From
Box", "Lump", "Stroke · Add").

- **The eye** hides a step: the clay is rebuilt without it, and showing it again brings it back. Use it to compare
  with and without an arm, or to set a step aside.
- **Double-click** a step to name it ("body", "arm", "nose"). Agents use the same names.
- **Click** a step to see its own settings under the list and change them: a drawn shape's Puff, Blend and Mode
  (Add or Carve), a lump's Radius, a stroke's Size and Strength. Changing an old step rebuilds the clay from there on,
  with every later step on top. Each change is one undo step.

## Fine detail: Relief

The clay's grain sets how small a sculpted detail can be. For what is finer (wrinkles, pores, scratches, the weave of
cloth) don't make the clay finer: paint it as **Relief**. It shows in Final and in the render as real light and shadow
on the surface, and it stays put when you sculpt the clay again (guide `painting`, "Painting on clay").

How to: a wrinkle across a forehead.

1. Sculpt the forehead's shape first (Add, Smooth). Turn the view so you look at it straight on.
2. Select the clay and press **B** (Paint). Click **+** next to Paint layers and set **Paints** to **Relief**.
3. Brush: tip **round**, **Colour** a dark grey (#404040: black sinks, white raises, middle grey leaves it flat),
   **Opacity** about 50 %, **Size** small (8–16 px).
4. Drag one slow line where the fold sinks. For the soft ridge above it, set Colour to a light grey (#b0b0b0) and a
   larger Size, and drag along just above the line.
5. Shift+F (Final): the wrinkle catches the light. Too deep: undo, lower Opacity, paint again.

## Posing

Any clay can bend: select it, click **Pose** on the tool rail and drag a hand (holds keep the feet still). The joints
are found from the shape, and found again when you sculpt it further (joints you placed and bends you keyed stay).
Sculpting a posed clay sculpts it as it stands. Guide `posing` has all of it, for people and agents.

## Eyes, buttons and other parts

Parts that should look exact (an eye, a button) are shapes, not clay: **Shapes › Sphere**, then click on the clay where
it goes: it comes out sized for that spot. With Mirror on, it gets a mirrored copy on the other side that follows it
(move, resize or recolour one and both change). Posed later, both move with the clay. Guide `modelling` › On a
mirrored clay.

## How it is kept

A drawn shape is kept as its outline on a flat plane; a spun one as its profile and axis; a clay turned from an item
as a link to that item (change the item and the clay follows). A stroke is stored as the exact path of brush touches
it made, in a small file in the project's `clay` folder, so it replays to exactly the same shape. The clay's
**Detail** (how fine its grain is; it follows the shot cameras) is under **+ Detail** in its settings when Select is
on. The brush settings (Brush, Size, Strength; under More: Falloff, Spacing, Front faces only, Mirror) show only while the Clay
tool is on; with Select they are not in the settings. An agent can still read and set them any time (`clay.set`).
Each stroke keeps its own copy of them, and whether it was Ctrl's opposite (`invert`).

**While a stroke is drawn on fine clay** (a brush 16 grains or more across its radius: a 25 mm brush on clay at
1 mm) the clay under the brush is shown a little coarser, so the brush keeps up with the pointer; a moment after you
let go it sharpens to full detail. What is kept is always the full-detail stroke: an agent's `look_frame` after the
stroke, and every render, show the full detail.

## For agents

**A character is one clay.** Start it as a ball and join its head, arms and feet as pieces of it, in a script:
`c = clay("buddy", radius=0.07)` (no `at` / `y`: the ball stands on the ground, the clay's origin on the ground
under it, so positions are heights above the ground), then `c.lump((0, 0.175, 0), 0.055, name="head", blend=0.012)`,
`c.lump(at, 0.02, to=…, name="arm")` from inside the body outwards (its shoulder clear of the head), and short `leg` and
`foot` capsules reaching below the ball (the figure is lifted to stand on them; guide `script` has the whole figure).
Every piece blends into one surface, so nothing floats or drifts apart, and the joints (`body`, `chest`, `head`,
`arm.R` …) are found from that one shape for `c.bend` / `c.pose` (guides `posing`, `script`). Separate clays or
meshes for limbs only touch, with a hard line, and don't bend together.

The Clay tool makes the same operations an agent calls (guides `agents` and `script`):

```
clay.add(draw=[[x, y, z], …], facing=[0, 0, 1])        -> a new clay from a drawn outline (points in the scene)
clay.add(spin=[[x, y, z], …], axis=[[x, y, z], [x, y, z]])   -> a new clay from a spun profile
clay.add(at=[0, 0.15, 0], radius=0.15)                 -> a new clay with one ball (at: in the scene)
script: clay("c", radius=0.15) / clay("c", at=(0, 0.15, 0), radius=0.15) / clay("c", at=.., to=.., radius=..)  (capsule)
clay.draw(target="clay_1", outline=[[x, y, z], …], puff=1, name="arm")   -> a drawn shape joined on (clay's own space)
clay.spin(target="clay_1", profile=[[x, y, z], …], axis=[[0, 0, 0], [0, 1, 0]])
clay.from_item(target=["box_1"])                       -> Turn into clay: a clay copy, the box hidden
clay.lump(target="clay_1", at=[0.1, 0.05, 0], radius=0.06)   -> a ball joined on (at: in the clay's own space)
clay.shape(target="clay_1", shape="capsule", at=[..], to=[..], radius=0.03, mode="carve")
clay.stroke(target="clay_1", brush="add", path=[[x, y, z], …], dir=[0, 0, -1], size=0.02)   -> a stroke along a path
                                                       # (size: this stroke's radius in m; left out, clay.set's brushSize)
clay.set(target="clay_1", brush="smooth", brushSize=0.02, brushStrength=0.4, symmetry="off",
         brushFalloff=0.5, brushSpacing=0.3, frontOnly=True)    # brush: add carve smooth pull flatten crease mask
claystep.set(target="clay_1.step_3", name="nose") · claystep.set(target="clay_1.step_2", hidden=True)
claystep.set(target="clay_1.step_2", puff=0.6) · claystep.remove(target="clay_1.step_3")
```

A new clay without `material=` gets the project's **Clay** material (grey, matte; made from the Clay start the
first time and shared by every clay made so: change it once to recolour them all, or give one clay its own with
`material.from(start="skin", to=["clay_1"])`; guide `materials`). A clay turned from an item keeps that item's material.

How the points work:

- **Which space.** `clay.add`'s `draw` / `spin` points are in the scene (or inside `into`); `clay.draw` and
  `clay.spin` points are in the clay's own space (its origin, turned with it), as `clay.lump`'s `at`.
- **The plane.** A drawn outline is laid flat on a plane through its points: `facing` is that plane's normal,
  pointing at the viewer (the side you drew on becomes the front, the clay's +Z); left out, the outline's own plane.
  The plane's sideways direction is its most horizontal one, so a new drawn clay's X runs along the drawing and
  Mirror's X = 0 runs down its middle. The new clay stands at the drawing's middle, at its lowest point.
- **Puff.** 1 is round (as thick in the middle as the outline is wide there); 0.1–3; `claystep.set puff` changes it.
- **Joining.** A drawn, spun or lumped shape joins the clay when it overlaps or touches its surface: put the
  outline's points at the depth of the surface where it should join. `blend` is how softly it joins (left out: half
  how fat the shape is × Puff, at most 5 cm, as a ball's half radius: an arm's root swells into the body as one piece;
  0 = a hard crease, which a bent limb opens into a seam); `mode="carve"` cuts the shape out instead.
- **A head on a body.** Two separate things (two clays, or a ball mesh on a body) only touch: a hard line where they meet,
  however close they are. Make the head a piece **of the body's clay** and it grows out of it: `body.lump((0, 0.28, 0),
  0.07, name="head", blend=…)`. `blend` is the width of the fillet in metres: about a fifth of the head's radius reads as
  a chin over a short neck, half (the default) as a soft neck, the whole radius as one blob. For a longer neck, a capsule
  piece between them (`to=`) with its own blend. To keep a hard line on purpose (a helmet), use a separate clay.
- **Tiny.** An outline under 4 points, or thinner than 1.5 of the clay's grains, makes a lump the brush's size.
- **A stroke's path.** `clay.stroke` `path` points are in the clay's own space; each dab lands where a ray from the
  point along `dir` meets the clay, so the points can float in front of it (e.g. z 0.3 with `dir` [0, 0, -1] in front of
  a face at z 0.08): the ray goes on until it reaches the clay. A point inside the clay, or whose ray misses it, makes
  no dab. Default strength (0.5) at the brush's size makes a clean, gentle ridge or groove; pass over it again, or turn
  `accumulate` on, for more.
- **Spin axis.** Two points; left out, straight up (+Y) through the profile's first point. Each profile point counts
  by its distance from the axis and its height along it; the ends close to the axis.
- **Hidden and names.** `claystep.set hidden=True` leaves a step out of the shape (kept); `name` names it.
- **Looking at it.** `look_frame what "shape" target="clay_1"` gives its outlines from the front, side and top with its measures
  (height, width and depth, the width at each tenth of its height, the left–right difference, thin spots);
  `look_at` on a pixel names the step that made the surface there ("arm, drawn"); `look_frame
  highlight="steps:arm"` outlines all of what that step made. Name your steps (`name="arm"`) so these replies read.
- **Turn into clay.** `clay.from_item` takes exact parts (meshes, combines, an import's parts) and imports; each gets
  a clay beside it named "<name> clay", Mirror off, and the original is hidden (`visible=false`), one undo step for all.

A person's strokes are `clay.stroke` with `dabs="clay/<hash>.dabs"` (the file the stroke wrote), and `invert=True`
when Ctrl was held with Flatten, Crease or Mask (Add and Carve swap the brush instead). A script run again
keeps the steps a person added to its clay.
