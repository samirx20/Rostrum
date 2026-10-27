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

Each one's settings (`sim.set`, or the item's own `.set`):

| field | what it does |
|---|---|
| `massFromSize` (on) / `mass` (kg) | how heavy: from its size as solid plastic, or a number. Heavier things push lighter ones aside |
| `bounce` 0–1 | 0 lands dead, 1 bounces back as high as it fell |
| `friction` 0–2 | 0 slides like ice, 1 grips like rubber |
| `starts` | `moving`, or `asleep`: stays put until something hits it (a stack waiting to be knocked over) |
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
| `pinned` | `none`, or the side held in place like a curtain on its rail: `top`, `bottom`, `left`, `right`, `front`, `back` (as the scene sees it at the first frame: `top` is its highest edge, `back` the edge furthest back) |
| `friction` 0–2 | how much it grips what it lies on |

A plane is made fine enough to fold on its own (a 40 × 40 grid of points); another shape has its faces split until they are
small enough. Pin a side the cloth has an edge on: a sheet lying flat has no top edge (pinning `top` holds all of it, which
fails); pin its `back` instead. Start it just above what it should land on, not touching it.

Cloth plays back from the stored result like a falling thing (Timing and Simplify apply too), but it never becomes keys: its
folds stay a simulation (`sim.to_keys` leaves it as it is). While it is cloth, keys on its place are not used: it stays where it
was at the first frame and the cloth moves inside it. Cloths don't touch each other (two sheets pass through each other).

## Compute it

The `run_simulation` tool computes the whole shot as a job (`inspect_job` shows frame n of m; a dozen things take a second or two)
and stores it. It reports how many fell, how many came to rest and how many end inside the camera's picture. Then
`look_sheet` shows the motion. `sim.run` does the same as an operation (in a script's batch of operations).

Nothing is computed again on its own. Change something it depends on (move the bowl, change a mass, a key on a falling thing)
and `inspect_simulation` says **out of date**: the viewport keeps showing the old result, and any render (`render_still`,
`render_video`, the Render button, the queue) computes it again first. A render never uses an out-of-date result. Put the
change back and the earlier result is used again without computing.

Changing only colours or materials never makes it out of date. A cloth's `clothWeight`, `stiffness`, `pinned` and `friction`
do.

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

`sim.to_keys` on the shot turns the result into ordinary keys on each falling thing (x y z rx ry rz: every frame; with
Timing on 2s / 3s a held key every 2 or 3 frames; with Simplify every nth frame) and switches its simulation off, in one undo
step. From then on it is plain animation: nudge one key by hand to place a bud just so. Running `sim.to_keys` again never
changes a key it already wrote for the same result, so a nudge stays, and it never touches keys you made yourself.

A falling copies item becomes **keyed copies**: every copy gets its own keys on x y z rx ry rz (in the copies item's own space,
the same frames as above) and the copies item stops simulating, in the same undo step. Nudge one copy with `copies.key`
{copy, prop, t, v}: it changes the key at that time (or adds one), and running `sim.to_keys` again keeps it, as for any item.
`copies.release` {copy} lets a copy go back to its place in the layout, its keys with it.

While a copies item still simulates, clicking a copy picks it where it fell, the "seen by" count tests where the copies fell,
and Change near no longer changes them (it changes them again once they are keys).
