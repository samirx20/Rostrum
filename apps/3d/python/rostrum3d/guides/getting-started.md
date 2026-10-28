# Getting started: a small clay character, step by step

From an empty project to a rendered picture of a small clay character standing on the ground, waving, through the
MCP tools. Read `start-here` first (the loop). The character is only an example of the steps. Make your own: a
different body, more arms, a tail, no arms at all. The same steps by clicking on the screen: guide `window`, "Your
first character on the screen".

Deeper on each step: guides `sculpting` (clay), `posing` (bending it), `materials`, `lighting`, `rendering`,
`agents` and `script`.

## What a new project already has

A wide grey **ground** that catches shadows, a soft photographed **sky** ("Studio"), two lights (a **Key light** softbox
high on the left that casts the shadow, a **Rim light** strip behind on the right for a bright edge), and the shot **Shot 1**, whose
camera looks at the middle of the ground. Shot 1 is framed for things a hand to an arm tall: a character about
30 cm tall standing in the middle fills about half the picture. Each of these is an ordinary item you can change or
delete.

## As an agent

You work through the MCP tools on one document. Every call below is one change in the history, the same a person
makes. Look after each step: `look_frame` with `quality: "fast"` takes about a second.

**The usual way: the whole scene as one Python script, look, edit, re-run.** Keep the script in a .py file and run it with
`run_script` `path`; after each look, edit that file and run it again (same name): it replaces what it made and keeps what a
person moved by hand. Every step below has a script form (`clay(…, draw=[…])`, `.draw(…)`, `item.key(…)`; guide `script`).
The steps here use single operations and pixel tools, the way to fix one thing you see in a look.
Replies open `NOT DONE:` with each fault (id, when, fix) or `DONE:`; render_still / render_video refuse open faults unless `keep: {id: why}` explains them.

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

Check the form in numbers with `look_frame what "shape"` (`target: "buddy"`): its outline from the front, side and top, its
height, widths and how even its two sides are. Sculpt with `clay.stroke` (guide `sculpting`, "For agents").

### 3. Eyes: place on a pixel

Make the eye at its size in the script (`mesh("eye", shape="sphere", radius=0.012, material=…)`; 2–3 cm across suits a
26 cm body), then `edit_place_on` with `mesh: "eye"` and `x`, `y` a pixel of the face in the picture `look_frame` gave
(and its `width`). It stands the eye on the surface there, and because the body's Mirror is on, makes its mirrored
copy `eye_mirrored`, which follows it. Change the original only. Both also follow the body's pose (each rides the
bone nearest it), so they stay on the face when the body bends. If the eye's size is far from what a click there
would make, the reply says so (`spotSize`, about a sixth of the body's width at that spot).

- Not sure a pixel is on the face? `look_at` with `points` answers what is at each pixel; pick one a few pixels inside
  the surface, away from edges (`edit_place_on` checks two neighbours too).
- In a script instead: `mesh(...).place_on("buddy", at=(x, y, z))` with a world point on the surface, for example
  `look_at`'s `point`.
- A shiny black: `material("eye_black", start="glossy plastic", baseColor="#101010")`. A material is shared by the
  eye and its copy.

### 4. The wave: find the joints, hold, drag

All through `edit_document`:

1. `pose.find_joints` (`target: ["buddy"]`). The reply lists the joints it found by name. The names follow the
   shape, so use the ones it gives: an arm usually gets `arm.R` (shoulder) and `forearm.R` (elbow, at its middle
   when it is straight), but a long or bent arm may get a third (`arm2.R`), and a body gets `chest` only when it is
   tall enough to bend in two (else its one joint is `body`). `.R` is the character's right, the −x side, on the
   picture's left. To see where a joint is, `inspect_item` its id (its head and tail, in the clay's space). An arm
   drawn hanging down must not touch the body's side (leave a gap of about a centimetre), or it is read as part of
   the body.
2. `pose.drag` with `part: "hand.R"` (the end of the arm, whatever its last joint is), `to` a world point and
   `holds`. Keep `to` **within the arm's reach**: no farther from the shoulder joint's head than the arm's joints
   are long together (about 10–13 cm for the arm above). Up and a little out from the shoulder reads as a wave. A
   point out of reach stretches the arm straight and leans the body a little after it (a few degrees at most, the
   eyes with it: parts placed on a clay follow its pose); drag again nearer.
3. **Hold the feet**: `holds: ["foot.L", "foot.R"]`. Within reach only the arm and the shoulder round it move: the
   body stays upright and its side stays where it is. Holding the body's upper joint too (`"chest"`, or `"body"`
   when that is its only one) is optional: it keeps the body still even for a point out of reach.

```json
{"op": "pose.drag", "target": ["buddy"], "args": {"part": "hand.R", "to": [-0.14, 0.27, 0.04], "at": 0,
 "holds": ["foot.L", "foot.R"]}}
```

Then `look_frame`: the arm bent at the shoulder and elbow, the hand up, the body upright.

Guide `posing` has the rest (keys at several times, `pose.rest`).

### 5. The angle, then the light

- **Angle first.** `shot.take_view` (`target: ["shot_1"]`, `position` [x, y, z], `lookAt` [x, y, z], `focalLength`)
  moves Shot 1's camera; for a view from a little to the side and above, put it about 1.3 m away, 0.3–0.5 m up,
  looking at the character's middle. `shot.frame` (`items: ["buddy"]`) then moves it nearer or farther so the
  character fills the picture with a margin, keeping its direction. Look again.
- **Then the light.** `edit_document` `light.add` (`id`, `kind: "rect"`: the Soft light), then `edit_place_on what "highlight"`
  with `light`, a pixel `x`, `y` of the cheek in the picture you were shown (and its `width`) and `fresh: true` (a
  light just added: it also gets a distance and a starting brightness). The light moves so its shine lands there.
  Placing the light before moving the camera can leave it in the new view.
- Check with one `look_frame` `quality: "final"`: real soft shadows, the light under the surface, the clay's look.
  `look_at` with `step` or `joint` and `look_frame what "shape"` help you check a part before you render.

### 6. Render

`render_still` (`shot: "shot_1"`) is a job: it answers with a `job_id` at once. Ask `inspect_job` with that `job_id`
and `wait_s` (at most 25) until it says "Rendered"; the reply names the picture's file (open that file to see it). Before a big render, ask
`render_estimate` (guide `agents`, "Render settings and the time estimate").

### When something looks wrong

- **The clay is not where you drew it.** Its origin is the drawing's middle at its lowest point; `inspect_item`
  shows its `x y z`. Later `clay.draw` outlines are in the clay's own space, so subtract that origin.
- **An arm did not join.** The outline must overlap or nearly touch the body: start it further inside.
- **A pixel call fails with "not inside one item's surface".** The pixel or a neighbour 3 px right or down is on an
  edge or on another part (an eye). Move a few pixels inwards.
- **The light makes a hard wedge on the floor or is in the picture.** The camera moved after the light was placed:
  place the highlight again (`edit_place_on what "highlight"` without `fresh` keeps its distance and brightness).
