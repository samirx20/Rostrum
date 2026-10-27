# Simulate: things that fall, bump and land

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

## Compute it

The `run_simulation` tool computes the whole shot as a job (`inspect_job` shows frame n of m; a dozen things take a second or two)
and stores it. It reports how many fell, how many came to rest and how many end inside the camera's picture. Then
`look_sheet` shows the motion. `sim.run` does the same as an operation (in a script's batch of operations).

Nothing is computed again on its own. Change something it depends on (move the bowl, change a mass, a key on a falling thing)
and `inspect_simulation` says **out of date**: the viewport keeps showing the old result, and any render (`render_still`,
`render_video`, the Render button, the queue) computes it again first. A render never uses an out-of-date result. Put the
change back and the earlier result is used again without computing.

Changing only colours or materials never makes it out of date.

## When it fails

A failure stops with the thing, the frame and what to do, for example:

- *bud_copies copy 7 starts inside bowl at frame 0*: move it up a little, or set `starts: "asleep"`.
- *flies away*: it starts inside another thing or `bounce` is too high: lower it, or check where it starts.
- *falls past everything*: nothing is under it: turn on `simGround`, or set something under it to `still`.

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

A falling copies item is left as it is (still simulating): its copies have no keys to write.
