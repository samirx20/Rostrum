# Camera rigs: orbit, crane, dolly, handheld

A **rig** is an item that carries what is inside it, usually the shot camera. You move the rig with a few numbers
(an angle, an arm's lift, a distance along a track) and key those numbers like any other field. The rig is worked out
for every frame and sent to the renderers as an ordinary moving group, so Storm, Cycles and a saved `.usda` all play
it the same way.

## Make one

```python
r = rig("spin", rig="orbit", radius=0.6, height=0.15, y=0.05)   # the rig's x y z = the centre it circles
with r:
    camera("cam", focalLength=85)                                # sits at the rig's head, faces where the rig faces
r.key("angle", {0: 0, 3: 360}, ease="linear")                    # one full turn in 3 s
shot("turn", camera="cam", fps=24, start=0, end=3)
```

Operations: `rig.add` (then `camera.add into=<rig id>`, or `item.arrange` an existing camera into it), `rig.set`,
`key.add` on `angle`, `lift`, `swing`, `travel`, `pan`, `tilt`, `radius`, `height`, `armLength`.

Leave the camera inside the rig at its own default place (x y z and turns 0): it then sits on the rig's head and looks
the way the head looks. Move or turn the camera inside the rig only for an offset (a camera a little above the arm).

## The three rigs

| Rig | Its base (the rig's own x y z, turns) | Moves |
|---|---|---|
| `orbit` | the centre it circles | `radius` (distance), `height` (above the centre), `angle` (0 = on +Z, the side the default camera is on). The head always faces the centre. |
| `crane` | the foot of the arm | `armLength`, `lift` (up from level), `swing` (around the foot; 0 = forward, −Z). The head stays level, like a real remote head. |
| `dolly` | the start of the track | `travel` (metres forward along −Z, the way the rig faces). Turn the rig (`ry`) to lay the track another way, e.g. `ry=90` for a sideways truck. |

Every rig has a head: `pan` (left/right) and `tilt` (up/down), added on top of where the rig points it. Key them for
a pan or a tilt-up during a crane move.

## Handheld

`handheld=True` adds a gentle drift to the head: smooth noise, never a jolt.

- `shake` (degrees): how far the head wanders. Around 0.2–0.5 reads as someone holding still; several degrees reads
  as running.
- `shakeFrequency` (Hz): how often. Under 1 reads as breathing, above 3 as nervous.
- `shakeMove` (metres): how much the camera body sways.
- `seed`: another number gives another drift of the same size. The same seed gives the same drift on every render,
  so two renders of one shot always match.

The drift is part of the rig, so a turntable or a crane move can be handheld too.

## Checking a move

Look before you render: `look_sheet` on the shot shows frames spread through it, so you can see the whole move at once,
and `look_frame` at the first and last frame shows where the move starts and ends.

Things to know:
- A key on `angle` from 0 to 360 with `ease="linear"` is a steady turn; the default ease starts and stops gently.
- An orbit's head faces the centre at its own height (the rig's y). Raise the rig's `y` to look at a higher point,
  and use `height` to lift the camera above that point.
- `aim` on the camera inside a rig still works (it overrides the head's facing), e.g. a crane that rises while the
  camera stays aimed at the product.
