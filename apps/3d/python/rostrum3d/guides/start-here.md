# Start here: making a 3D shot

Rostrum3D makes shots: meshes, sculpted clay, imported models, lights and a camera, animated by keys and rendered by
Storm (quick looks) or Cycles (the final picture). You work on a document, never on a USD file: everything you make
is an operation, and every look draws the scene again from the document.

## The loop

1. **Write ONE script** for the whole scene (Python, the helpers in guide `script`). Keep it in a .py file.
2. **Run it with a look**: `run_script` with `path` (or `source`), a stable `name` and `look: true`. The reply carries
   the picture through the shot's camera and the faults.
3. **Read the faults.** A checked reply opens `NOT DONE:` with each fault (its id, when, and the fix) or `DONE:`:
   too dark or blown out, a subject cut by the frame's edge, something floating above or sinking into the ground.
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

- **Ground.** Things stand on the ground (y = 0). A mesh's `y` is its middle, so write its height from its own size,
  never a guessed number: a ball `y=r` with `radius=r`, a box `y=h / 2` with `height=h`. A clay with no `at` / `y` stands on
  the ground by itself, and its pieces' positions are heights above it. A character is ONE clay (`c.lump(...)` pieces),
  posed by its joints: `c.bend("arm.R", {0: (0, 0, 0), 1: (0, 0, -80)})` or `c.pose("hand.L", {2: point})` (guide `script`). A thing on another made earlier in the same group: `.place_on(other)`; on a clay's
  surface at a world point: `.place_on(clay, at=(x, y, z))`. The faults name anything floating or sunk.
- **Frame.** Frame the camera by its subject, not by numbers you guess: `edit_document` with `shot.frame`
  (`items`: the subject's ids) moves the camera so they fill the picture with a margin, keeping its direction;
  `shot.take_view` (`position`, `lookAt`, `focalLength`) sets the angle first. Then look.
- **Place.** To put one thing on another where you see it: `edit_place_on` with a pixel `x`, `y` of the picture you
  were just shown (and its `width`): a mesh stands on the surface there (an eye on a face). `what: "highlight"` aims a
  light so its shine lands there instead. `look_at` tells what is at a pixel.
- **Time.** Keys are in seconds from the shot's start: `item.key("ry", {0: 0, 2: (90, "linear")})`.

## A tiny example

The technique only: a box on the ground, a ball standing on it, turning.

```python
m = material("red", start="glossy plastic", baseColor="#c23b22")
h = 0.1
crate = mesh("crate", shape="box", width=0.2, height=h, depth=0.2, y=h / 2)
ball = mesh("ball", shape="sphere", radius=0.06, material=m).place_on(crate)
ball.key("ry", {0: 0, 2: (180, "linear")})
```

Run it (`run_script`, `name: "scene.py"`, `look: true`), then `edit_document` `shot.frame` with `items: ["crate", "ball"]`,
then look again.

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

**Never** guess a height or a camera position: write heights from sizes, frame by the subject, place by `place_on`
or a pixel; never edit a .trd or USD file directly.

## Where next

- `getting-started`: a small clay character, step by step through the tools.
- `script`: every script helper, field and rule for ids and re-runs.
- `agents`: the look tools in depth, render settings and the time estimate, techniques, errors.
- `modelling`, `sculpting`, `posing`: shapes, clay, bending it.
- `materials`, `lighting`, `camera-rigs`, `copies`, `simulate`, `painting`: one topic each.
- `rendering`: stills, videos, passes, handing a shot to 2D.
- `window`: the screen, every control and key, for helping a person who clicks.
- `tool-details`: each tool's long description and every argument.
