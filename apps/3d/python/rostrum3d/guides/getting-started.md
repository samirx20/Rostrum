# Getting started: a small clay character in five minutes

From an empty project to a rendered picture of a small clay character standing on the ground, waving. The steps
are the same for a person on the screen and an agent through MCP; each half below teaches them in its own way.
The character is only an example of the steps. Make your own: a different body, more arms, a tail, no arms at all.

Deeper on each step: guides `sculpting` (clay), `posing` (bending it), `materials`, `lighting`, `rendering`,
`window` (every control and key) and, for agents, `agents` and `script`.

## What a new project already has

A wide grey **ground** that catches shadows, a soft photographed **sky** ("Studio"), and the shot **Shot 1**, whose
camera looks at the middle of the ground. Shot 1 is framed for things a hand to an arm tall: a character about
30 cm tall standing in the middle fills about half the picture. Each of these is an ordinary item you can change or
delete.

## On the screen

**Moving around** works the same in every tool: **right-drag** (or two fingers on a touchpad) turns the view, the
**wheel** (or a pinch) comes closer or goes back. **F** brings the selection to the middle. Turning the view never
moves Shot 1's camera. **↶** in the header (Ctrl+Z) undoes any step: a shape, a stroke, a colour, a pose, a light.

1. **A body.** Click **Clay** in the rail (or press **Q**). **Draw** is already chosen in the panel. Drag a closed
   outline over the ground, about half as tall as the picture, and let go. It puffs into a soft clay body standing
   on the ground, its front towards you. A faint line down its middle shows that **Mirror** is on. On a touchpad,
   keep the click held for the whole outline.
2. **Arms.** With Draw still on, start an outline **on the side of the body** (the body gets a thin outline while
   the pencil is over it) and drag an arm out. It joins the body, and the same arm appears on the other side.
3. **Feet.** A small oval at the bottom of the body. Mirror makes the second one.
4. **Shape it.** Pick a brush in the panel and drag over the clay: **Smooth** evens out lumps, **Add** builds clay
   up (a brow), **Carve** takes it away (a mouth). Hold **Shift** to smooth with any brush, **Ctrl** for the opposite.
   **Size** is the brush's radius. Each stroke is one undo step.
5. **Eyes.** **Shapes › Sphere**, then click on the face where one eye goes, a little off the middle. A small ball
   sits on the face, sized for it (about a ninth of the face's width there), and its mirrored copy appears on the
   other side and follows it. Drag it with the arrows, or type its size in the panel. Both stay on the face when
   you pose the body later.
6. **Colour.** Select the body and click the small coloured square beside **Base colour** (under its **Material ▾**):
   pick an orange. New clays share the project's grey "Clay"; the first colour change gives this clay its own copy, so
   other clays stay grey. Select an
   eye, click its material ball, choose **Glossy plastic** under **Start from**, then set its Base colour to black.
   Both eyes change, because the copy follows the original.
7. **A wave.** Select the body and click **Pose** in the rail (Shift+P). Click each foot once (an orange ring: it
   stays put) and click the chest so the body stays upright. Then drag the end of one arm up. The arm bends at the
   shoulder and the elbow. Bent in the wrong place: ↶, add a hold nearer to where it should bend, drag again.
8. **A good angle.** Right-drag to look from a little to the side and above. Rest the pointer on **Make this the
   shot** in the header: the frame Shot 1 would take shows. Click it. Choose the angle **before** the light: the
   light is placed for what the camera sees.
9. **A good light.** **Lights › Soft light**, then click the cheek where you want it brightest. The light is placed
   so its shine lands there, at a sensible brightness. **Shift+F** shows the view in Final quality, with real soft
   shadows (Shift+F again goes back to Quick).
10. **The picture.** Click **Render** at the right of the top bar. It starts at once at final quality and says how long
    it will take; the picture shows when done, saved in the project's Renders folder (**Show in folder**).
    When it is done: **Show in folder**.

## As an agent

You work through the MCP tools on one document. Every call below is one change in the history, the same a person
makes. Look after each step: `look_frame` with `quality: "fast"` takes about a second.

### 1. The body: an outline in metres

`run_script` with `clay(id, draw=[…])`. The points are in the scene, in metres. To stand the character in Shot 1's
middle, facing the camera:

- Draw on the plane **z = 0** with `facing=(0, 0, 1)` (its front towards the camera, which stands on +z).
- Centre the outline on **x = 0** and put its **lowest point at y = 0**. The clay then stands on the ground, and its
  own space is the scene's own space: its origin is the drawing's middle at its lowest point, here (0, 0, 0). So
  later outlines can use the same numbers.
- Sizes that suit Shot 1: a body about 0.26 m tall and 0.18 m wide. 24 to 40 points around the outline is plenty.
- Give it its material in the same call; the starting point `clay` with your colour gives matte clay.

```python
orange = material("body_orange", start="clay", baseColor="#e07a3f")
c = clay("buddy", draw=[(x, y, 0.0) for x, y in body_outline], facing=(0, 0, 1), material=orange)
```

Then `look_frame` (`shot: "shot_1"`). Mirror (`symmetry="x"`) is on by default: it mirrors across the clay's x = 0.

### 2. Arms and feet: join by drawing

`c.draw(outline)` in the same script joins a shape on, in the clay's own space (here the same as the scene). Start
the outline **inside the body's edge** so it overlaps; draw only one side, Mirror makes the other.

- An arm: a thin oval from about 3 cm inside the body's side out to 10–12 cm past it (about 4–5 cm tall).
- A foot: a small oval (about 7 × 3.5 cm) at the bottom of the body, its lowest point at y = 0, off the middle.
- `name="arm"` on each `draw` names the step, so you can find it again (`claystep.set`).

To add a shape later without re-running the script: `edit_document` with `clay.draw` (`target: ["buddy"]`,
`outline`, clay's own space). Re-run the same script under the same `name` to change what it made; what a person
moved since is kept.

Check the form in numbers with `look_shape` (`target: "buddy"`): its outline from the front, side and top, its
height, widths and how even its two sides are. Sculpt with `clay.stroke` (guide `sculpting`, "For agents").

### 3. Eyes: place on a pixel

Make the eye at its size in the script (`mesh("eye", shape="sphere", radius=0.012, material=…)`; 2–3 cm across suits a
26 cm body), then `edit_place_on` with `mesh: "eye"` and `x`, `y` a pixel of the face in the picture `look_frame` gave
(and its `width`). It stands the eye on the surface there, and because the body's Mirror is on, makes its mirrored
copy `eye_mirrored`, which follows it. Change the original only. Both also follow the body's pose (each rides the
bone nearest it), so they stay on the face when the body bends. If the eye's size is far from what a click there
would make, the reply says so (`spotSize`, about a ninth of the body's width at that spot).

- Not sure a pixel is on the face? `look_at` with `points` answers what is at each pixel; pick one a few pixels inside
  the surface, away from edges (`edit_place_on` checks two neighbours too).
- In a script instead: `mesh(...).place_on("buddy", at=(x, y, z))` with a world point on the surface, for example
  `look_at`'s `point`.
- A shiny black: `material("eye_black", start="glossy plastic", baseColor="#101010")`. A material is shared by the
  eye and its copy.

### 4. The wave: find the joints, hold, drag

All through `edit_document`:

1. `pose.find_joints` (`target: ["buddy"]`). The reply lists the joints it found, each with where it is (and
   `dropped`: old joints the new shape no longer has). An arm gets `arm.R` (shoulder) and `forearm.R` (elbow, at
   its middle when it is straight). `.R` is the character's right, the −x side, on the picture's left. An arm
   drawn hanging down must not touch the body's side (leave a gap of about a centimetre), or it is read as part of
   the body.
2. `pose.drag` with `part: "hand.R"` (the end of the arm, whatever its last joint is), `to` a world point (up and a
   little out: about 15 cm above the shoulder) and `holds`.
3. **Hold the feet**: `holds: ["foot.L", "foot.R"]`. The chest then leans a little with the arm, and the eyes lean
   with it (parts placed on a clay follow its pose). Add `"chest"` to keep the body upright and bend only the arm.
   Only the arm and the shoulder round it move: the body's side stays where it is.

```json
{"op": "pose.drag", "target": ["buddy"], "args": {"part": "hand.R", "to": [-0.16, 0.30, 0.04], "at": 0,
 "holds": ["foot.L", "foot.R"]}}
```

The reply names the joints that moved. `miss` above 0 means the hand could not reach `to`: bring it closer.
Guide `posing` has the rest (keys at several times, `pose.rest`).

### 5. The angle, then the light

- **Angle first.** `shot.take_view` (`target: ["shot_1"]`, `position` [x, y, z], `lookAt` [x, y, z], `focalLength`)
  moves Shot 1's camera; for a view from a little to the side and above, put it about 1.3 m away, 0.3–0.5 m up,
  looking at the character's middle. `shot.frame` (`items: ["buddy"]`) then moves it nearer or farther so the
  character fills the picture with a margin, keeping its direction. Look again.
- **Then the light.** `edit_document` `light.add` (`id`, `kind: "rect"`: the Soft light), then `edit_place_highlight`
  with `light`, a pixel `x`, `y` of the cheek in the picture you were shown (and its `width`) and `fresh: true` (a
  light just added: it also gets a distance and a starting brightness). The light moves so its shine lands there.
  Placing the light before moving the camera can leave it in the new view.
- Check with one `look_frame` `quality: "final"`: real soft shadows, the light under the surface, the clay's look.
  `look_at` with `step` or `joint` and `look_shape` help you check a part before you render.

### 6. Render

`render_still` (`shot: "shot_1"`) is a job: it answers with a `job_id` at once. Ask `inspect_job` with that `job_id`
and `wait_s` (at most 25) until it says "Rendered"; the reply carries the picture. Before a big render, ask
`render_estimate` (guide `agents`, "Render settings and the time estimate").

### When something looks wrong

- **The clay is not where you drew it.** Its origin is the drawing's middle at its lowest point; `inspect_item`
  shows its `x y z`. Later `clay.draw` outlines are in the clay's own space, so subtract that origin.
- **An arm did not join.** The outline must overlap or nearly touch the body: start it further inside.
- **A pixel call fails with "not inside one item's surface".** The pixel or a neighbour 3 px right or down is on an
  edge or on another part (an eye). Move a few pixels inwards.
- **The light makes a hard wedge on the floor or is in the picture.** The camera moved after the light was placed:
  place the highlight again (`edit_place_highlight` without `fresh` keeps its distance and brightness).
