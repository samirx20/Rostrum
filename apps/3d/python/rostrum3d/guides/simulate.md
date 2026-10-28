# Simulate: things that fall, bump and land, and cloth that drapes

Some things move best by real physics: buds dropped into a bowl, dice thrown on a table, blocks knocked over. Mark what falls
and what it lands on, compute once, and the result is stored and played back like any animation.

## Set it up

| what | how |
|---|---|
| it drops and bumps | `sim.body` on it with `kind: "falls"` (script: `bud.simulate("falls")`) |
| things land on it, it never moves | `kind: "still"` (a bowl, a table, a plinth) |
| not part of it | `kind: "off"` |
| the floor | the shot's `simGround` (on by default): a floor at height 0, even with nothing modelled there |

Only things directly in the scene can fall or stay still, not something inside a group or copies (move it out first with
`item.arrange`). A **copies** item that falls makes every copy fall on its own: twelve buds in one item are twelve falling things.

A spill or a pour, written as one script you re-run and look at (the fields are in the guide *copies*):

```python
mesh("table", shape="box", width=1.0, height=0.04, depth=0.6, y=0.38).simulate("still")
red = material("red", start="glossy plastic", baseColor="#c8321e")
cream = material("cream", start="glossy plastic", baseColor="#efe6d2")
# a few sources, same shape, different materials: each copy picks one by the seed (colour variety)
a = mesh("die_a", shape="box", width=0.03, height=0.03, depth=0.03, bevel=0.003, y=0.9, material=red)
b = mesh("die_b", shape="box", width=0.03, height=0.03, depth=0.03, bevel=0.003, y=0.9, material=cream)
copies("dice", [a, b], layout="pour", count=40, radius=0.03, pourTime=3, pourSpeed=0.6, pourSpread=15,
       varyTurn=180).simulate("falls", fallStart=0.5, bounce=0.3)
```

Then `run_simulation`, a contact sheet, change, run the script again. In a stream (a pour, or `varyStart` on any layout) a copy
is **not there until it starts to fall**: it appears at its start point and drops, and until then it neither shows nor
collides (renders, looks and framing all agree), so nothing hangs in the air waiting. Without a stream (all copies start
together) every copy holds still where it is until `fallStart`.

Each one's settings (`sim.set`, or the item's own `.set`):

| field | what it does |
|---|---|
| `massFromSize` (on) / `mass` (kg) | how heavy: from its size as solid plastic, or a number. Heavier things push lighter ones aside |
| `bounce` 0–1 | 0 lands dead, 1 bounces back as high as it fell |
| `friction` 0–2 | 0 slides like ice, 1 grips like rubber |
| `starts` | `moving`, or `asleep`: stays put until something hits it (a stack waiting to be knocked over) |
| `fallStart` (seconds into the shot) | holds still where it is until then (others land on it and bounce off it), then falls; 0 = from the start. Stagger drops with it: `a.simulate("falls", fallStart=1)`, `b.simulate("falls", fallStart=2.5)`. On a copies item every copy waits, and its `varyStart` (Vary › **Start**, the guide *copies*) spreads each copy's start over that many seconds after it, from the seed (each copy then appears only when it starts); a pour leaves them one after another over `pourTime` after it; in the window it is the Simulation group's **Falls from** row, shown while it falls. To see the drop: *Stage a fall people see* below |
| `simShape` | `exact` (its own outline; for one that falls, with the dents filled in), `box` or `sphere` (faster, rougher) |

A thing that has keys at the start keeps its speed: key it moving and it is thrown. Keys after the first frame are not used
while it falls (the simulation moves it).

## Cloth

A shape set to `kind: "cloth"` (script: `sheet.simulate("cloth")`; in the window: right-click › Simulate › Cloth) drapes and
folds over whatever is under it: things that stay still, things that fall (it pushes them), and the floor. Only a shape can be
cloth (a plane is the usual one), and only one directly in the scene.

| field | what it does |
|---|---|
| `clothWeight` (kg per m²) | how heavy it is: silk 0.05, cotton 0.2, denim 0.4, felt or leather 1 |
| `stiffness` 0–1 | 0 folds like silk, 0.3 like cotton, 1 bends like thin card |
| `clothAir` 0–4 | how much the air holds it up as it falls. 1 (the default) is room air: a sheet settles over about a second instead of dropping like a stone, its edges lift and lag behind its middle, and a light one (silk, 0.05) floats down slower than a heavy one (denim, 0.4). 0: no air (it drops as fast as a falling thing); 2–4: slower and softer still, like a large light sheet or a parachute. In the window: the Simulation group's **Air** row |
| `pinned` | `none`, or the side held in place like a curtain on its rail: `top`, `bottom`, `left`, `right`, `front`, `back` (as the scene sees it at the first frame: `top` is its highest edge, `back` the edge furthest back) |
| `friction` 0–2 | how much it grips what it lies on |
| `fallStart` (seconds into the shot) | Falls from, as for a falling thing: the cloth keeps its first shape where it is until then (things that fall land on it as on something still), then drops. In the window: the Simulation group's **Falls from** row |
| `clothWind` 0–5 (m/s) | Breeze: moving air in slow travelling gusts, so the cloth keeps breathing after it lands (free edges lift and fall, hanging sides sway) instead of freezing. 0 (the default) is still air: it settles and stays. 0.3–0.8 a room's draught, 1–2 an open window, 3–5 outdoors (a light cloth may blow off). A lighter `clothWeight` or more `clothAir` moves more in the same breeze. In the window: **Breeze** |
| `clothWindTurn` (degrees) | which way the breeze blows, turned about the up axis: 0 towards +x (left to right seen from the front), 90 away from the front (−z), −90 towards the front. In the window: **Breeze from** |

A plane is made fine enough to fold on its own (a 96 × 96 grid of points, so wrinkles a couple of centimetres wide on a
1.5 m sheet); another shape has its faces split until they are small enough. At the default `stiffness` 0.3 a sheet hangs in soft folds and gathers where it meets the floor; go towards 0
for silk that clings to every shape, towards 0.6–1 for canvas or card that stands off in broad bends. A still thing whose
shape is closed and has no dents (a box, a ball, a plinth) is solid to cloth; one with dents or holes (a chair, a bowl)
is draped by its own faces. The sheet rests about 0.6 of a grid square (under 1 cm on a 1 m sheet) off what it lies on, so
sharp corners don't poke through it. A cloth touches itself: where it folds over or gathers on the floor its layers stay
about 0.9 of a grid square apart (1.4 cm on a 1.5 m sheet) instead of passing through each other, so corners fold into soft
rolls, not crumpled spikes. Pin a side the cloth has an edge on: a sheet lying flat has no top edge (pinning `top` holds all of it, which
fails); pin its `back` instead. Start it just above what it should land on, not touching it.

**Timing the drape in a long shot:** a sheet takes about 1.5–2.5 s from letting go to lying still. In a 10 s shot with
`fallStart` 1 it is still from about 3.5 s on, and `run_simulation` says so: "Everything settles at 3.5 s … start it 5.5 s
later (its fallStart + 5.5)". Choose what the shot is about, then write it in the script and run it again: a later
`fallStart` (the drop as the climax), a `clothWind` of 0.3–0.8 so the settled cloth keeps stirring for the rest of the
shot, a shorter shot, or all of them. Look with `look_motion` (its **On screen** and moving lines) after each run.

**Make it read as fabric (Final):** the simulation gives the folds; the material gives the cloth. Start its material from
**Fabric** (`material.from` with `start: "fabric"`, `to: ["sheet"]`): high roughness and `sheen` (the soft glow fibres
catch at grazing angles; `sheenRoughness`, `sheenTint`). Set its colour; for a woven or printed cloth wire a **Pattern**
block (checks, stripes or a weave) into its base colour, two operations: `graph.add` `{"type": "pattern", "values":
{"shape": "checks", "a": …, "b": …, "repeats": 12}}` then `graph.connect` `pattern_1.colour` → `surface.baseColor` (guide
`materials`, "Fabric, velvet and soft fuzz"). A light low from one side (raking) shows the folds. Sheen shows only in
Final (Cycles): check a Cycles still.

**Place it over its target:** `sim.body` with `kind: "cloth", over: "box"` (script: `sheet.simulate("cloth", over=box)`) puts
the sheet centred above that item, a little over its top, level; a plane too small to drape it (less than half the item's
height would hang down each side) is made square and big enough to reach the floor and gather there.
Set the target to `still` too. `run_simulation` then says what each cloth ends on (`cloth sheet: … ends on box`) and **warns**
when a cloth starts over nothing it can land on, or slides off what it started over. Read the warning and look with
`look_frame what "sheet"` before rendering.

Cloth plays back from the stored result like a falling thing (Timing and Simplify apply too), but it never becomes keys: its
folds stay a simulation (`sim.to_keys` leaves it as it is; on a shot whose only simulated thing is cloth it fails saying
so, and the window offers no Turn into keys). While it is cloth, keys on its place are not used: it stays where it
was at the first frame and the cloth moves inside it. Two cloths don't touch each other (two sheets pass through each other); one cloth does touch itself.

## Compute it

The `run_simulation` tool computes the whole shot as a job (`inspect_job` shows frame n of m; a dozen things take a second or two)
and stores it. It reports how many fell, how many came to rest and how many end inside the camera's picture. Then
`look_frame what "sheet"` shows the motion. `sim.run` does the same as an operation (in a script's batch of operations).

**What a video shows of the fall.** `render_video` (a re-export, `estimate_only` and `render_send_shot` too), `look_frame what "sheet"`, `look_motion` and
`run_simulation` judge the frames they cover, not only the whole shot, and say in plain words, with the fix: *the cut opens mid-drop* or
*after the thing landed* (a `start` later than the fall's start: start the cut at or before it), *a thing is already moving at the first
frame* (the shot opens mid-fall: give it a moment with `fallStart`, or start it higher), and *everything settles at 0.4 s, the last 7 s
don't move* (shorten the cut, slow the fall, or key the camera or other things). Nothing is said when the fall is on screen and the cut
holds it; judge a refine cut again after changing its range.

Nothing is computed again on its own. Change something it depends on (move the bowl, change a mass, a key on a falling thing)
and `run_simulation what "status"` says **out of date**: the viewport keeps showing the old result, and any render (`render_still`,
`render_video`, the Render button, the queue) computes it again first. A render never uses an out-of-date result. In the
window, the result a render computed becomes the shot's stored one (the row says Stored, the viewport shows that fall; one
undo step, "Simulate … (for the render)"). Put the change back and the earlier result is used again without computing.

`look_motion` measures a falling thing where the stored result has it, and checks it for passing through like any shape;
its **On screen** lines (and `run_simulation`'s warnings) say whether each fall and cloth is seen (*Stage a fall people see*).
While the simulation is out of date (it measures the older result) or not computed (the things stay at their keyed
places) its reply says so first and gives no all-clear: run the simulation, wait for it, look again.

Changing only colours or materials never makes it out of date. A cloth's `clothWeight`, `stiffness`, `clothAir`, `pinned` and
`friction` do.

## Stage a fall people see

A fall only reads when the shot camera sees it move. A thing placed far above the picture drops through the top edge and
lands a couple of frames later; a sheet placed right on what it covers barely moves. Two controls and one check:

| what | how |
|---|---|
| start it inside the picture | `sim.start_in_view` on things set to Falls or Cloth (script: `sheet.simulate("cloth", over=box, fallStart=1).start_in_view(0.1)`, after the shot and its camera), `fromTop` 0–0.9 (default 0.1): moves each one up or down so its top sits that share of the picture's height below the picture's top edge, as the shot camera sees it at the frame it starts falling. Only its height changes, so it still lands where it did. A copies item moves as a whole (its highest copy goes there). In the window: right-click its row › Simulate › **Start in view**, or select it › settings panel › **Start in view** (0.1 from the top; scripts and agents set `fromTop`) |
| give the shot a moment first | `fallStart` (Falls from, seconds; a falling thing or a cloth): the thing hangs in the picture until then, so the viewer sees it before it drops; a copies item's `varyStart` (or a pour's `pourTime`) spreads the copies' starts after that, each copy appearing as it starts |
| check it | `run_simulation` warns, and `look_motion` has an **On screen** line per falling thing and cloth: how far and over which frames it drops (until it first lands), how many of those frames the picture shows it in and how many it drops outside (above, below, beside), the frame it comes into the picture and the frame it lands, or "starts already at rest". Its data: `fallsOnScreen` (`run_simulation`: `onScreen` {item: [drop frames on screen, drop frames]}) |

`sim.start_in_view` fails with the reason when no height can show the thing: it is beside the picture (move it sideways
first), behind the camera, the camera looks straight down, the picture's top is below the floor there, that low it would
start inside or under what it falls onto (a smaller `fromTop`), or its height has keys. How far it falls decides how long
the fall takes (gravity does the rest: about 0.45 s for 1 m, 0.3 s for 0.5 m); a cloth is held up by the air (`clothAir`), so a
lighter one (`clothWeight`) or more air drifts down slower: a 0.2 kg/m² sheet falls at most about 1.4 m/s flat on, a
0.05 one about 0.7 m/s. The check counts the **drop**: from its first move until it stops going down (its first landing); bounces,
rolls and a cloth's settling after that are "moves until frame n". A drop that is mostly above the picture, wholly
outside it, or on screen for fewer than 4 frames is named, with the fix. A falling **copies** item is judged copy by copy
(a pour is many short falls one after another): the line says how many copies fall, over which frames they start, the median
drop and how long each is seen dropping, and names the item only when more than a quarter of its copies drop unseen or for
under 4 frames (`run_simulation`'s `onScreen` for it counts the frames in which some copy is seen dropping).

## When it fails

A failure stops with the thing, the frame and what to do, for example:

- *bud_copies copy 7 starts inside bowl at frame 0*: move it up a little, or set `starts: "asleep"`.
- *flies away*: it starts inside another thing or `bounce` is too high: lower it, or check where it starts.
- *falls past everything*: nothing is under it: turn on `simGround`, or set something under it to `still`.
- *sheet tore apart* (cloth): an edge stretched to many times its length, usually because it starts inside something: lift it
  clear, lower `stiffness`, or pin fewer points.
- *sheet is flat along its top side, so pinning it holds all of it*: pin a side it has an edge on (`back`, `front` …).

## Make it look hand-made (shot settings)

| field | what it does |
|---|---|
| `simTiming` | `every` frame, or `2s` / `3s`: the falling things move in steps, held 2 or 3 frames each, like hand animation, while the camera stays smooth |
| `simSimplify` 1–12 | keeps every nth frame of the result and moves smoothly between them: fewer, cleaner moves |

Neither needs computing again: they change how the stored result is played back.

## Turn it into keys

`sim.to_keys` on the shot turns the result into ordinary keys on each falling thing (x y z rx ry rz) and switches its
simulation off, in one undo step. It keeps only the keys that matter: a key the straight line between its neighbours
already gives, within 1 mm (x y z) or 0.1° (rx ry rz), is left out, so a thing at rest keeps two keys and a bouncing one a
key at each bounce and a few along each arc; played back, the keys give every frame of the fall within that. With Timing
on 2s / 3s the keys are held, every 2 or 3 frames where the value changes; with Simplify they come from every nth frame. From then on it is plain animation: nudge one key by hand to place a bud just so. Running `sim.to_keys` again never
changes a key it already wrote for the same result, so a nudge stays, and it never touches keys you made yourself.

A falling copies item becomes **keyed copies**: every copy gets its own keys on x y z rx ry rz (in the copies item's own space,
thinned the same way) and the copies item stops simulating, in the same undo step. Nudge one copy with `copies.key`
{copy, prop, t, v}: it changes the key at that time (or adds one), and running `sim.to_keys` again keeps it, as for any item.
`copies.release` {copy} lets a copy go back to its place in the layout, its keys with it.

While a copies item still simulates, clicking a copy picks it where it fell, the "seen by" count tests where the copies fell,
and Change near no longer changes them (it changes them again once they are keys).
