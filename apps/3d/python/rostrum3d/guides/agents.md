# Building, looking and fixing a 3D shot

You work on a document, never on the USD file: every change is an operation (`run_script`, `edit_document`), and the engine builds the
scene from the document each time you look. Imported USD files stay untouched; your changes to them are overrides.

## The loop

1. **Know the shot.** `inspect_shot` gives the frame rate, the frame range, the picture size, the shot camera and every light.
   `inspect_usd_file` shows what a file you want to import holds (its parts, their materials and sizes) before you import it.
2. **Build with a script**, small steps: the room and the subject first, then the camera, then light, then materials, then motion.
   Each step ends with a look.
3. **Look through the shot's camera, not around the scene.** Everything you see is what the final picture will hold.
   - `look_frame` — one frame. Quality `fast` (Storm) tells you composition, scale, framing and motion in about a second;
     `final` (Cycles) tells you light, glass, shadows, reflections. Use `renderer: "stylized"` to see the stylized look.
   - `look_sheet` — the whole shot in six frames. Ask for it after every change to motion: does the thing arrive, hold, leave?
   - `look_at` — "what is at this pixel?" Give x, y of the picture you were just shown (same width). It answers with the item id,
     the part, its material, the point in the world and the distance. Use it to find the id behind something that looks wrong,
     and to check a thing is where you meant (several points at once with `points`).
4. **Fix the cause, not the picture.** If a shadow is wrong, look at the light's position and size, not at the surface it falls on.
   If something is too small in frame, check the camera's focal length and the distance before scaling the object.
5. **Render last.** `render_still` (png for people, exr for the Editor) and `render_video` are jobs: they return a job id at once;
   `inspect_job` with `wait_s` shows `frames n of m`. Draft a video with `quality: "fast"` first.

## Techniques

- **Frame first, light second, detail third.** A box-and-sphere blockout with the right camera and light already shows if the shot
  works. Add detail only where the camera sees it (a part that never reaches the frame costs render time and gives nothing).
- **A look at fast quality is not a look at final.** Storm has no true glass, soft shadows or global light. Judge shape and timing in
  Storm, then confirm light and materials with one `final` look at the frame that matters most.
- **Depth of field is a choice of three numbers.** The focus distance is the distance from the camera to what must be sharp. Get
  it from `look_at` (its `distance`) instead of measuring by eye.
- **Time.** `at` is seconds from the start of the shot; `frame` is the shot's own frame number. Both are valid in every tool; the
  replies carry both `time` and `frame`.
- **Check the ends of a move.** First and last frame of a move, and the middle: `look_sheet` with `start` / `end` zoomed to that range.
- **Memory.** `look_frame` replies carry the video memory the render used; a 4 GB card holds a modest scene at 1080p. If a
  render fails with a memory message, lower `width` or the number of lights before anything else.

## Errors

A failed look or render says what failed (the frame, the camera, the item) and, when the engine had stopped, that it was started
again. Read the line; it names what is accepted. A scene the engine refuses is refused whole, and the engine keeps the previous
scene, so a look after a refused change shows the last good state, not the new one.
