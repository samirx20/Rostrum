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
person moved by hand. Every step below has a script form (`clay(…)`, `.lump(…)`, `.pose(…)`; guide `script`).
The steps here use single operations and pixel tools, the way to fix one thing you see in a look.
In a script, things stand on the ground: a mesh's `y` is the height of its base above the ground (**changed**: it was its
middle; `y_world=` for that); place by relation with `place_on(other, beside="left")` and `row([...])`; frame with
`shot("shot_1", frame=c, at=(1/3, 0.5), fill=0.6)`; your own light adds to the start key and rim (guide `script`).
Check with `look_frame` (a quick frame in seconds) and judge it yourself; `notes: true` adds measurements if you want them. Renders always write what you asked.

### 1. The body: ONE clay, every part a piece of it

Build the whole figure as **one clay**: body, head, arms and feet are its pieces, joined into one surface, so nothing
can float off or drift apart, and its joints are found from that one shape. Separate meshes for the limbs are the
hard way (they have to be kept touching and moved together by hand).

- `clay(id, radius=r)` starts it as a ball **standing on the ground**: its middle at (0, r, 0), the clay's origin on
  the ground under it. So every piece position is (x, **height above the ground**, z), the same numbers as the scene:
  feet at height 0, a head above the body ball's top (2 r). A piece reaching below the ground lifts the whole figure
  (and what is attached) to stand on it. `at=(x, y, z)` places the ball's middle there instead, and pieces are then
  measured from that point.
- `.lump(at, radius, name=)` joins a ball; `.lump(at, radius, to=…)` a capsule from `at` to `to` (an arm, a leg).
  Positions are in the clay's own space; start each piece **inside** the one it joins, so they blend into one.
- Mirror is on (`symmetry="x"`): make one arm and one foot on the +x side, the other side comes with it.
- Shape it for posing: a **head on a narrower neck** (the head's ball overlapping the body's a little, not sunk into
  it), and **arms held a little out from the body** (a slight A), not pressed to its side. The joint finder reads a
  narrowing as a neck and a branch as a limb.
- Sizes that suit Shot 1: a figure about 0.2–0.3 m tall. A drawn outline works too (`clay(id, draw=[…],
  facing=(0, 0, 1))`, its lowest point at y = 0) when the body is not round (guide `sculpting`).

```python
c = clay("buddy", radius=0.07, material=material("body", start="clay", baseColor="#e07a3f"))   # middle at 0.07 high
c.lump((0, 0.195, 0), 0.055, name="head")                       # overlaps the body: a neck forms between
c.lump((0.055, 0.11, 0), 0.02, to=(0.13, 0.07, 0), name="arm")  # from inside the body, out and a little down
```

Then `look_frame` (`shot: "shot_1"`), and `look_frame` with `what: "shape"` (`target: "buddy"`) for its outline and size in numbers.

### 2. Detail: more pieces, carving, strokes

`.lump(…, mode="carve")` cuts (a mouth), a small `.lump` adds (a nose), `.draw(outline)` joins a flat drawn shape
(an ear, a foot sole), `.stroke(…)` sculpts (guide `sculpting`, "For agents"). Make the whole shape before posing it.

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
- Or in the script with numbers: `mesh("eye", …, x=…, y=…, z=…, attach_to=c)`, in the same space you built the clay in
  (it moves with the clay when the clay comes to rest on the ground, and bends with its pose).
- A shiny black: `material("eye_black", start="glossy plastic", baseColor="#101010")`. A material is shared by the
  eye and its copy.

### 4. The wave: bend the joints at several times

In the script, after the last piece: `c.bend(joint, {seconds: (x, y, z)})` turns a joint by those degrees about the
clay's own X, Y, Z (it faces +Z) from its rest, at each time; `c.pose(seconds, **{"picture-right hand": {"up": 0.22, "out": -0.15}})`
moves a part's end at that time instead (a world point, or up / out / forward metres from its rest; for a wave that
reads, the hand goes over the head and swings about half the figure's height, three times or more, to the shot's
end: guide `posing` › For agents; "picture-left hand" names the hand on the picture's left; the reply notes a target out of reach). The first one finds the joints from the shape (with the engine):
`body`, `chest`, `head`, `arm.L` / `forearm.L`, `foot.L` …; `.R` is the character's right, the −x side, on the
picture's left. A wrong joint name fails with the list of the ones it has.

- Turning about Z swings an arm up or down in the picture's plane: on `arm.R` (the −x side) a negative angle raises
  it, on `arm.L` a positive one. The arm turns at its shoulder joint, inside the body: about 60–90° from hanging
  reads as raised; much more lays it against the head.
- `holds=["foot.L", "foot.R", "body"]` on `pose`: the feet stay planted and the whole trunk upright (a held body
  holds the chest too); only the arm moves. About Y turns the head left/right, about X nods it.
- A wave: raise `arm.R`, then rock `forearm.R` back and forth a few times (small angles, about a third of a second
  apart), then lower it. Keys between are eased (`ease=` like `item.key`).
- Things attached to the clay (`attach_to=`, `place_on`) bend with the bone nearest them: the eyes stay on the head.

The same with single operations: `pose.find_joints`, then `pose.drag` (`part: "hand.R"`, `to`, `at`, `holds:
["foot.L", "foot.R"]`) through `edit_document`.

Guide `posing` has the rest (keys at several times, `pose.rest`).

### 5. The angle, then the light

- **Angle first.** `shot.take_view` (`target: ["shot_1"]`, `position` [x, y, z], `lookAt` [x, y, z], `focalLength`)
  moves Shot 1's camera; for a view from a little to the side and above, put it about 1.3 m away, 0.3–0.5 m up,
  looking at the character's middle. `shot.frame` (`items: ["buddy"]`) then moves it nearer or farther so the
  character fills the picture with a margin, keeping its direction (in a script: `shot("shot_1", frame=c, fill=0.6)`). Look again.
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
