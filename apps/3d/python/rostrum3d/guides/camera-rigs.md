# Camera rigs: orbit, crane, dolly, handheld

A **rig** is an item that carries what is inside it, usually the shot camera. You move the rig with a few numbers
(an angle, an arm's lift, a distance along a track) and key those numbers like any other field. The rig is worked out
for every frame and sent to the renderers as an ordinary moving group, so Storm, Cycles and a saved `.usda` all play
it the same way.

## Put a camera on a rig (one step)

In the window: **Camera** flyout (C) › **Orbit**, **Turntable**, **Crane**, **Dolly** or **Handheld**. The camera
(the selected one, else the shot camera) goes onto a new rig and starts exactly where it was, so the shot does not
jump. Orbit and Turntable then wait for a click on what to circle (an item: its middle; the ground: that point; Esc
cancels). Turntable also keys one full turn over the shot. Crane, Dolly and Handheld start at once: the track or arm
runs the way the camera looks. The rows are absent while the camera already rides a rig: change that rig's **Rig**
setting instead.

Agents do the same with one operation:

```json
{"op": "rig.wrap", "target": ["cam"], "args": {"kind": "orbit", "around": "case", "turn": "hero"}}
```

- `kind`: `orbit`, `crane` or `dolly`; `handheld: true` adds the drift (the window's Handheld is a still dolly with it).
- An orbit circles `around` (an item's origin) or `point` [x, y, z], else what the camera aims at, else the point at its
  focus distance straight ahead.
- `turn: <shot id>` keys one turn (a turntable); later, `rig.turn_once` with `shot` does the same on an orbit rig.
  The key at the shot's end is a full turn, so the last frame stops just short of it and the shot loops.
- The camera's own position and turn keys are cleared (the rig moves it now); its aim stays and still works.

## Make one by hand

```python
r = rig("spin", rig="orbit", radius=0.6, height=0.15, y=0.05)   # the rig's x y z = the centre it circles
with r:
    camera("cam", focalLength=85)                                # sits at the rig's head, faces where the rig faces
r.key("angle", {0: 0, 3: 360}, ease="linear")                    # one full turn in 3 s
shot("turn", camera="cam", fps=24, start=0, end=3)
```

Operations: `rig.wrap` (above), or `rig.add` (then `camera.add into=<rig id>`, or `item.arrange` an existing camera into it), `rig.set`, `rig.turn_once`,
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

## Motion blur

A camera on the move smears what it passes, the way a real film camera does, and that smear is what makes a fast
orbit or a whip-pan read as motion instead of a string of sharp stills.

Select the shot, then **Motion blur** in its row of names: switch it on, and **Shutter** appears. The shutter is how
long each frame is exposed: **180°** (the default) is half a frame, the usual film look; smaller is crisper and
choppier, **360°** is a whole frame, the most smear. It is off on a new shot.

```python
shot("turn", camera="cam", fps=24, start=0, end=3, motionBlur=True, shutter=180)
```

Agents: `shot.set` with `motionBlur` and `shutter` (degrees, 1–360).

Things to know:
- **Quick shows no motion blur** (the setting's tip says so). Switch the viewport to **Final** to see it, and every render
  (Render button, `render_still`, `render_video`) draws the same blur: it is part of the shot, not of the render.
- **The camera's own move blurs** (an orbit, a crane, a dolly, a handheld drift). A keyed object moving in front of a
  still camera stays sharp for now.
- Each frame's smear is centred on that frame: the sharp picture of a frame sits in the middle of its blur.
- A faster move or a longer shutter smears more. If a turntable looks smeary, slow the turn or lower the shutter.
