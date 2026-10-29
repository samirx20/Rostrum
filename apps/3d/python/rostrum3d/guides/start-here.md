# Start here: making a 3D shot

Rostrum3D makes shots: meshes, sculpted clay, imported models, lights and a camera, animated by keys and rendered by
Storm (quick looks) or Cycles (the final picture). You work on a document, never on a USD file: everything you make
is an operation, and every look draws the scene again from the document.

## The loop

1. **Write ONE script** for the whole scene (Python, the helpers in guide `script`). Keep it in a .py file.
2. **Run it with a look**: `run_script` with `path` (or `source`), a stable `name` and `look: true`. The reply carries
   the picture through the shot's camera and the faults.
3. **Read the faults.** A checked reply opens `NOT DONE:` with each fault (its id, when, and the fix) or `DONE:`:
   too dark or blown out, a subject cut by the frame's edge, something floating above or sinking into the ground,
   a sky photo seen past the floor.
4. **Fix the script**, not the picture: if a shadow is wrong, move the light; if a thing is too small, check the camera
   before scaling the thing.
5. **Re-run under the same name.** The re-run replaces what the script made (changed values, removed items) and keeps
   what a person moved by hand. A different name is a different script.
6. **Deliver**: `render_still` or `render_video` (jobs: `wait: true`, or ask `inspect_job`). They refuse a file while a
   fault is open, unless `keep: {fault_id: "why"}` explains it.

## Ground, frame, place

A new scene is not empty: a wide `ground` (a plane at y = 0), the `sky` (the Studio dome), a `key_light` and a
`rim_light`, and the shot `shot_1`, whose camera looks 15° down at the middle of the ground, framed for things a hand
to an arm tall. Units are metres, degrees and seconds; y is up; the camera stands on +z looking towards −z.

- **Ground.** Things a script makes stand on the ground by themselves: `y` is how high a thing's base sits above the
  ground (left out: on it), never its middle; `y_world=` puts its middle at a world height (the rare floating thing).
  A clay with no `at` / `y` stands on the ground too, its pieces' positions heights above it. The faults name anything
  floating or sunk.
- **Place by relation.** `.place_on(other)` stands a thing on top of another; `.place_on(other, beside="left", gap=0.02)`
  (or `in_front_of=other`) puts it next to it by their real sizes, turned or not; `row([a, b, c], gap=0.05)` lays
  things side by side, centred. On a clay's surface at a world point: `.place_on(clay, at=(x, y, z))`.
- **Frame by the subject.** `shot("shot_1", frame=subject, at=(1/3, 0.5), fill=0.6)` moves the shot's camera so the
  subject's middle lands at that point of the picture (fractions from the left and the top) and fills that share of
  its height; `shot.key("frame", {0: {"fill": 0.4}, 3: {"fill": 0.8}})` is a push-in; `cam.take_view(pos, look_at)`
  sets an angle first. Making `shot_1` again keeps its camera.
- **Light.** Your lights add to the start key and rim (`replace_start_lights=True` takes them out, and the reply
  says so). `brightness=` is in stops against the start key on its subject: 0 the same, +1 twice, −1 half.
- **Pose.** A character is ONE clay (`c.lump(...)` pieces), posed by its joints:
  `c.pose(t, **{"picture-right hand": {"up": 0.17, "out": -0.11, "forward": 0.06}})`, one call per time (a world point
  or up / out / forward metres from rest; "left hand", "hand.R" and "picture-left hand" all work; the reply notes a
  target out of reach; the arm is kept clear of the head, `clear=0` lets it touch). A wave reads only when big and
  repeated: the hand beside the head and a little forward, swinging a good share of the figure's height, three times
  or more, to the shot's end, turning points every 0.35 s, not 0.5 or 1 s (stills one second apart catch the same
  pose; guide `posing` › For agents); or
  `c.bend("arm.R", {0: (0, 0, 0), 1: (0, 0, -80)})` (guide `posing`).
- **At a pixel.** `edit_place_on` with a pixel `x`, `y` of the picture you were just shown (and its `width`): a mesh
  stands on the surface there (an eye on a face); `what: "highlight"` aims a light so its shine lands there.
  `look_at` tells what is at a pixel.
- **Time.** Keys are in seconds from the shot's start: `item.key("ry", {0: 0, 2: (90, "linear")})`.

## A tiny example

The technique only: a box on the ground, a ball standing on it, turning.

```python
m = material("red", start="glossy plastic", baseColor="#c23b22")
crate = mesh("crate", shape="box", width=0.2, height=0.1, depth=0.2)       # on the ground: no y
ball = mesh("ball", shape="sphere", radius=0.06, material=m).place_on(crate)
ball.key("ry", {0: 0, 2: (180, "linear")})
shot("shot_1", frame=[crate, ball], fill=0.5)
```

Run it (`run_script`, `name: "scene.py"`, `look: true`), read the faults, change the script, run it again.

## The core tools

- `run_script`: run the whole scene script (`look: true` to see it and get its faults).
- `look_frame`: see the shot: one frame (default), or `what` "sheet", "shots", "material", "shape", "paint",
  "coverage", "where", "exposure".
- `edit_place_on`: put a mesh, or a light's highlight, on what is at a pixel of the last look.
- `inspect_guide`: these guides (`topic`).
- `render_still`: the final picture (`render_video` for an mp4).

How every reply works: it has `ok`, `summary` (read it first), `data` and `files`; a failure's `error` lists
`accepted`, what would have worked. `inspect_*` reads, `edit_*` and `run_*` change the document, `look_*` sees,
`render_*` makes files. Long work is a job: pass `wait: true`, or ask `inspect_job` (`wait_s` up to 25); `run_stop`
stops it. Every tool, by verb, with its arguments: `inspect_tools`. Every tool in full: guide `tool-details`.

**Never** guess a height or a camera position: things stand on the ground, frame by the subject, place by `place_on`,
`row` or a pixel; never edit a .trd or USD file directly.

## Where next

- `getting-started`: a small clay character, step by step through the tools.
- `script`: every script helper, field and rule for ids and re-runs.
- `agents`: the look tools in depth, render settings and the time estimate, techniques, errors.
- `modelling`, `sculpting`, `posing`: shapes, clay, bending it.
- `materials`, `lighting`, `camera-rigs`, `copies`, `simulate`, `painting`: one topic each.
- `rendering`: stills, videos, passes, handing a shot to 2D.
- `window`: the screen, every control and key, for helping a person who clicks.
- `tool-details`: each tool's long description and every argument.
