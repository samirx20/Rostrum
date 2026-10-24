# 3D renders in a 2D piece

A **3D render** layer shows a Rostrum3D item's finished render inside a 2D composition: a product turning behind
your type, a still of a device under a UI animation. It is a placed picture, read-only. You move, scale, mask, blend
and time it like any layer; you change the product itself in Rostrum3D.

## Placing one

- In the tool rail, open **Media**: every Rostrum3D item of this project that has a finished render (with EXR frames)
  is listed by its name. A click places that item's render, centred, as one step. An item not rendered yet is not
  listed (render it in Rostrum3D first); with none, nothing 3D is offered. Ctrl+K lists the same ("Add 3D render: …").
- In the settings panel, **3D item** and **3D shot** are lists of what the project has, never ids to type.

## How it stays live

- The layer names a 3D item of the project (`item`). With **Version** at 0 ("Newest") it always shows that item's
  newest finished render. When Rostrum3D finishes a new render, the 2D screen picks it up within two seconds; an
  export or an agent's look always uses the newest one.
- Set **Version** to a number to keep one render (v002) while the 3D goes on changing.
- **3D shot** names one shot of the item (`hero`): the layer then shows only that shot's renders, so a later render of
  another shot doesn't replace it. Empty: the newest render of any shot. Rostrum3D's **Send to 2D** (agents:
  `render_send_shot`) makes the layer with the shot set; sending the same shot again updates this layer and leaves where you
  put it, its size and timing alone.
- It reads the render's **EXR frames**, the hand-off with transparency, so whatever has nothing behind it in 3D is
  see-through in 2D. Colours match the 3D app's own PNG (same colour settings). Render with EXR: `render_still`
  makes PNG + EXR by default; `render_video` needs `exr: true`.
- A sequence plays at the composition's speed; **Speed**, **Render starts at** and **Loop** (Off, Loop or Ping-pong) work as on a video layer.

## Timing it to the story

Give it a **Timed from marker**: a shared marker's name ("product lands"). The render's first frame lands on that
marker, and moves when someone moves the marker in any app. *Starts at* and *Ends at* then count from the marker
(Starts at 0.5 = half a second after it). Every layer has this field; see `start-here` › Timing to the story.

## When something is wrong, it says so

- A version that isn't there, a render without EXR frames, a 3D item that doesn't exist, a marker that isn't in the
  project: the picture is not drawn, and the message says what to do. An export stops. No render yet: see below.
- **Out of date**: the 3D document changed after the render (its content: the render's `scene_hash` no longer matches).
  The layer keeps showing the render it has (it is still a true render) and the Problems list (agents:
  `inspect_diagnose`) says "3D render out of date" until 3D renders or sends the shot again.

## Techniques

- **Render at the size you show it.** The layer's width and height are what the render is fitted into; a render
  smaller than that is stretched. Use Fit *contain* to keep the whole render, *cover* to fill the box.
- **Let 3D own the light, 2D own the layout.** Type, UI and graphic shapes stay in 2D where they are sharp and quick
  to change; the product's look stays in 3D where light and materials are right.
- **Depth without a second render.** Put 2D layers both behind (a soft shape, a gradient) and in front (type, a UI
  card) of the 3D layer. For real depth-of-field, shadows on 2D shapes or passes, finish the shot in the Editor.
- **Agents:** add it with `run_script` (`render3d("hero", item="product", w=1600, h=900, marker="product lands")`),
  then `look_frame`; `inspect_diagnose` tells you if the render is missing or out of date.

- **3D not rendered yet?** In looks (`look_frame`, `look_sheet`), a part of a video and the screen, the layer is a grey
  card at its own box labelled "3D: <item> — not rendered yet", and the reply warns; you can judge the rest of the film
  now. A whole-film `render_export` / `render_video` refuses until the render is there. "Out of date" means the 3D
  scene's content changed after the render; a re-run that changed nothing is not out of date.

What this layer is not: it never mixes the 3D app's passes or combines frames from several apps. That is the
Editor's job (AGENTS.md rule 8).
