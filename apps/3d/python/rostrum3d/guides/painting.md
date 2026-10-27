# Painting on a model

You paint straight onto a mesh or a clay: colour, and also how rough, how raised, how metal or how glowing each spot
is. It uses the same brushes as Draw in Rostrum2D. The paint is kept as strokes on the model, so every stroke can be
undone and nothing is lost when you save and open the scene again. On a clay the paint stays where you put it when you
sculpt the clay again afterwards (see "Painting on clay").

## On the screen

1. Select the mesh or the clay (one: a lid, a case, a head).
2. Click **Paint** on the tool rail (the brush, at the bottom) or press **B**. The first time, a mesh is laid flat
   for painting by itself (the message line says "Unfolding Lid…" for a moment). Nothing is asked. Unfolding is one
   undo step of its own. A clay needs nothing: it is laid flat by itself each time its shape changes.
3. The settings panel now shows the brush and the paint layers:
   - **On the surface | From the view**: where a stroke lands. *On the surface* paints the selected item where you
     drag. *From the view* keeps the drag exactly as you drew it on the picture and paints every item under it (a stroke
     across a case and its lid lands on both, one undo step); its **Size** is in pixels of the screen. A view stroke
     stays editable: it is laid on the surfaces each time the paint is made, from the view it was drawn in.
   - **Brush**: the tip (round, bristle, chalk, flat, block, line), **Size** (in pixels of the paint picture, which is
     2048 px across unless you change it), **Colour** and **Opacity**.
   - **Paints**: what the active layer paints. **Colour**; **Roughness** (white = rough and dull, black = mirror);
     **Relief** (middle grey = flat, white = raised, black = sunk: fine detail such as wrinkles, pores and scratches); **Metal** (white =
     metal); **Glow** (its colours give off light).
   - **▨** beside the layers' **+**: the coverage tint. Every surface the shot's camera sees and nothing paints yet
     gets a faint orange hatch (on the screen only, never in Final or a render), and the line under it says how much
     is done: "Seen by Hero 01: 62 % painted". The first tint from a new view takes a few seconds ("tinting…").
   - **Paint layers**, top first. **+** adds a layer painting the same as the active one. Click a layer's name to
     paint on it; its dot shows or hides it. With no layer yet, your first stroke makes a Colour layer. A layer is
     named after what it paints ("Roughness 1") and its name follows when you change Paints, until you rename it.
4. Drag on the model in the viewport. A thin line follows the pointer while you drag; when you let go the paint lands.
   **Each stroke is one undo step** (Ctrl+Z takes back exactly that stroke). The disc at the pointer is the brush's
   size as it lands on the surface. Right-drag (or middle-drag) turns the view, Shift-drag pans, so you can turn the model between
   strokes. The move handles are hidden while you paint.
5. **B** or **Esc** leaves Paint (Bones is **Shift+B**). Selecting something else leaves it too.
6. **Project a picture**: select the shapes (Ctrl+click their names in the scene list), right-click one ›
   **Project a picture from Hero 01…** › a rendered 2D item of the project, or **A picture file…**. Each shape gets a
   layer with the picture laid on it from the shot's camera, like a slide projector: what the camera can't see (behind
   the case, facing away) stays unpainted, so turning the view shows the depth. A 2D item stays linked: render it again
   in Rostrum2D and the 3D view follows by itself. Paint over it on the same layer or on layers above.

Paint sits over the material's own value: where you haven't painted, the surface is exactly its material (its colour,
its roughness, its own pictures). A layer painting Roughness changes only roughness: the colour stays.

Look at paint with **Final** (Shift+F, or Final in the top bar's **Shot camera · Quick ▾**): Cycles shows roughness,
relief and metal the way the render will. Quick shows colour, roughness, metal and glow; Relief only shows in Final.

## Painting on clay

A clay is painted the same way: select it, press **B**, drag on it. Each stroke is kept as a path on the clay's
surface, not as pixels, so you can go back to the Clay tool, pull a nose further out or add a lump under a stripe, and
the stripe stays on the same spot of the clay, stretched with it. After a change of shape the clay is laid flat again
and every stroke laid back on it; for a moment after a sculpting stroke the changed part shows the clay's own
material, then its paint comes back.

The brush Size is in pixels of the paint picture, as on a mesh; the stroke keeps the size it had on the clay (in
metres), so sculpting the clay bigger or smaller under it doesn't make the stroke thicker or thinner. A stroke that
runs over a cut of the laid-flat surface carries on across it by itself.

**Relief** is the way to add the finest detail to a clay (wrinkles, pores, scratches, fabric weave): it shows in
Final and in the render without making the clay finer (and heavier). Sculpt the big and middle shapes with the Clay
tool, then paint Relief for what is smaller than its grain (guide `sculpting`).

## How to: a roughness scuff on a glossy lid

1. Select the lid, press **B**.
2. Click **+** next to Paint layers, then set **Paints** to **Roughness**.
3. Set the brush: tip **chalk** or **bristle** (a broken edge), **Colour** a light grey (#b0b0b0: quite rough),
   **Opacity** about 60 %, **Size** 30–60 px.
4. Drag a few short strokes where a hand or a table would rub it: near the edge, along the rim.
5. Shift+F (Final): the scuffs read as dull patches in the gloss, catching the light differently. Too strong: undo the
   last stroke, lower Opacity, paint again. Darker grey = less rough.

## For agents

- `mesh.unfold` with `target: [mesh id]` lays the mesh flat into its paint picture (stored as `uvs` on the mesh, one
  undo step). Paint mode does it by itself; an agent calls it once before painting a mesh with no `uvs`. Again after
  changing the shape: a mesh whose shape changed since it was unfolded is refused by the engine with a message saying so.
- `paint.add` with `target: [mesh or clay id]`, `args: {name, channel}` adds a paint layer; `channel` is `colour`,
  `roughness`, `height` (shown as Relief), `metal` or `glow` (`paint.set` changes it).
- `stroke.add` with `target: [paint layer id]`, `args: {points: [[x, y, pressure], …], color, size, brush, opacity}`
  paints one stroke, in pixels of the paint picture (0..paintSize, y down). Several `stroke.add` calls in one
  `edit_document` call list are one undo step.
- `look_at` on the viewport gives `uv` (with the engine's pick): the canvas pixel there is x = u × paintSize,
  y = (1 − v) × paintSize. Check the result with `look_frame` (Final) from the shot camera.
- **On a clay, paint by `anchors`, not pixels.** `stroke.add` with `args: {anchors: [[x, y, z, nx, ny, nz,
  pressure], …], reach, color, brush, opacity}`: the path on the clay's surface in the clay's own space (metres) and
  `reach`, the brush's radius in metres (0.003 = 3 mm); no `points`. `look_at` on a clay gives `local` and
  `localNormal` at a pixel: one anchor is `[*local, *localNormal, 1]`. Give a point every few millimetres along the
  path (several `look_at` points in one call), or space them evenly along a line you work out on the clay's shape;
  between anchors the path is a straight line taken to the nearest surface. Strokes by anchors stay on the same spots
  through reshapes; pixel `points` on a clay (from its `uv`) would slide when its shape changes. A clay with no paint
  layer yet gives no `uv`, only `local`. On a **posed** clay `look_at` also gives `rest`, the same spot on the clay's
  rest shape: anchor there (`[*rest, *normal, 1]`, the normal from the rest shape; `localNormal` is close enough on
  parts the pose hardly turns). Paint is kept on the rest shape, so it rides with every pose, as the screen does.
- `paintSize` on the mesh (256..8192, default 2048) is the picture's side. Paint strokes are kept in its pixels, so set
  it before painting.

## For agents: seeing and checking paint

Five tools look at paint. Canvas coordinates are always pixels of the item's paint picture (0..paintSize, x right,
y down) or a `uv` (x = u × paintSize, y = (1 − v) × paintSize).

- `look_paint target=<mesh or clay>`: the paint picture itself, flat. All layers together, one `layer`, or one
  `channel` (`roughness`, …); `zoom` [x0, y0, x1, y1] and `grid` label canvas pixels, the same numbers `stroke.add`'s
  `points` use. Unpainted shows as a checkerboard. A clay's anchored strokes, strokes from the view and projected
  pictures are shown laid, as the render gets them. The reply gives each layer and the box that holds paint.
- `inspect_paint_strokes target=<mesh, clay or paint layer>`: one line per stroke, where it landed and how far off:
  `stroke s3 (From the view, layer paint_1): landed on case and lid, 1.2 screen px off (canvas x 410–980, y 220–260)`.
  A stroke on the surface is measured on the canvas (canvas px between its paint's centre and its path); a stroke from
  the view through its own camera (screen px between where the paint shows and where you drew it). Each row also has
  `uvBox`, and for a view stroke `share` (how much of the drawn path is on this item).
- `look_coverage shot=<id> frame=<n>`: through the shot camera, how much of each mesh and clay it sees is painted
  ("lid: 62 % painted (41 000 of 66 000 px seen)"), and the frame with what is seen but unpainted hatched orange. A
  spot counts as painted where any shown layer is at least half opaque, as the screen counts. A mesh seen but never
  unfolded is named: `mesh.unfold` it first.
- `look_where target=<item> px=[x, y]` (or `uv=[u, v]`): the reverse of `look_at`. Where that canvas spot shows on
  the shot's picture (its pixel), the world point and which way the surface faces there; or that it isn't seen (behind
  something, facing away, out of frame), with the nearest pixel where the item is seen.
- `look_at` gives on every hit `normal` (the surface direction, "facing [0, 1, 0]" is a top), `faceSet` on a mesh
  with face materials (that face's own material), `uv`, and where something is painted `painted`: the topmost shown
  layer with paint there, its channel, colour and how opaque. Its reply's `view` is the picture's camera as
  `stroke.add`'s From the view fields.

## For agents: painting from the view

A stroke from the view is drawn on a picture of the shot, the way a person drags across the viewport: the path is
kept in that picture's pixels with the camera it was seen through, and laid on whatever the camera sees there each
time the paint is made. One stroke can cross several items.

1. `look_frame` (the width you want, e.g. 960) shows the picture. Choose the path's pixels on it.
2. `look_at` with those pixels as `points` (same width): each hit names the item under it. Its reply's `view` holds
   `viewEye`, `viewTarget`, `viewFov`, `viewSize`, `viewFrame`: the camera as stroke.add takes it.
3. One `stroke.add` per item the path crosses, all in one `edit_document` call list (one undo step), each on a paint
   layer of that item (`paint.add` first if it has none), each with the same view fields and the same `viewPoints`:

   ```json
   [{"op": "stroke.add", "target": ["case_colour"], "args": {"viewPoints": [[300, 410, 1], [520, 380, 1], [700, 300, 0.6]],
     "viewEye": [1.2, 0.9, 2.4], "viewTarget": [1.0, 0.75, 1.5], "viewFov": 28.2, "viewSize": [960, 540], "viewFrame": 0,
     "size": 14, "color": "#c23b22", "brush": "round"}},
    {"op": "stroke.add", "target": ["lid_colour"], "args": {"viewPoints": [[300, 410, 1], [520, 380, 1], [700, 300, 0.6]],
     "viewEye": [1.2, 0.9, 2.4], "viewTarget": [1.0, 0.75, 1.5], "viewFov": 28.2, "viewSize": [960, 540], "viewFrame": 0,
     "size": 14, "color": "#c23b22", "brush": "round"}}]
   ```

   `size` is in pixels of that picture (screen px), not of the paint picture. Leave out `points`.
4. Check: `inspect_paint_strokes` on each item says it landed there and how far off; `look_frame` shows it;
   `look_coverage` shows what the shot still sees unpainted.

A stroke on the surface (`points` in canvas px) is the other way: work out the canvas pixels from `look_at`'s `uv`,
or read them off `look_paint` with a `grid`.

## How view strokes, projected pictures and coverage are kept

- **A stroke from the view** keeps its path as drawn: `viewPoints` in pixels of a `viewSize` [width, height] picture
  from the camera `viewEye` → `viewTarget` with `viewFov` (vertical, degrees) at `viewFrame`, and `viewShot` when it
  was drawn through a shot. `stroke.add` also takes them as one `view` {eye, target, fov, frame, width, height,
  points, shot}; they are stored as the flat fields. Each time the paint is made it is laid from the camera's texel
  picture (which spot of which item every pixel sees): every screen pixel of the path takes the canvas pixel under it,
  the brush `size` goes from screen px to canvas px by how big the surface looks there, pressure is kept, and the path
  is cut where it leaves the item or crosses a seam (a jump on the canvas). Move or reshape the item and the stroke
  lands where the camera now sees it. A path that the camera sees on none of the item paints nothing there.
- **A projected picture** is a paint layer with `projectSource` (a picture file, or `2d:<2D item id>`: that item's
  newest pictures render, its first frame) and the projector's camera (`projectEye`, `projectTarget`, `projectFov`,
  `projectSize`, `projectFrame`). `paint.project` makes one on each target, on top, in one change: `{"op":
  "paint.project", "target": ["wall_a", "wall_b", "wall_c"], "args": {"shot": "hero", "picture": "2d:poster"}}` (the
  shot's camera at its start, or `frame`; or a free camera: `eye`, `target`, `fov`, `width`, `height`; optional `name`,
  `channel`). Each texel the camera sees gets the picture's colour there; what is hidden or faces away stays
  unpainted, so another camera sees the picture lying on the surfaces, with their depth. The layer's own strokes
  paint over the picture. Render the 2D item again and the projection follows at the next look.
- **Coverage** counts, through a shot camera's picture, the pixels showing each painted item (`seen`) and those on
  paint that is at least half opaque in any shown layer (`painted`), and their share. The orange hatch is laid only in
  the screen's view, never in a render or export.
- The first stroke from a new camera (or a projection) waits for its texel picture: the scene is loaded once without
  that paint, the picture is drawn, then the paint is laid and the scene loaded again. Later strokes from the same
  camera on the same shapes go in at once (the picture is kept until the shapes or the camera change).
- Paint pictures bleed a few texels past each piece's edge of the unfolded surface, so no line shows at a seam, and an
  editable mesh's faces with their own material show the paint too (over that material's own colour or value).

## What it doesn't do yet

- A projected 2D render shows its first frame (a still), not the animation.
- Only plain over-painting is kept across a projected layer: a layer above it that multiplies, screens or smudges the
  layers below mixes with them as if the projected layer weren't there.
- Seams: the unfold cuts where it must. A stroke that crosses a cut continues as a second stroke on the other side,
  in the same undo step (on a clay, each time it is laid); its two halves may not meet exactly.
- A logo's or an outline's front and sides show their own material, not the paint.
