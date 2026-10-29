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
   - **Brush | Stamp** (only while the active layer paints Relief): Stamp lays a whole picture with one click (see
     "Stamping a picture" below). The rows become **Picture**, **Size**, **Depth** and **Turn**.
   - **Paints**: what the active layer paints. **Colour**; **Roughness** (white = rough and dull, black = mirror);
     **Relief** (middle grey = flat, white = raised, black = sunk: fine detail such as wrinkles, pores and scratches); **Metal** (white =
     metal); **Glow** (its colours give off light).
   - Under Paints, the chosen layer's **Fill** and **Mask** (see "Wear and dust: automatic masks" below). **Fill**
     covers the whole model with the layer's **Fill colour**; **Mask** shows the layer only on Edges, Cavities,
     Facing up or Thin parts; **Spread** and **Invert** appear once a mask is chosen.
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

## Stamping a picture

A stamp (an "alpha") lays one whole picture as relief in one click: a logo pressed into leather, a row of rivets, a
scale pattern, a stitched seam, a coin's face.

1. Select the model, press **B**. Click **+** next to Paint layers and set **Paints** to **Relief** (or click an
   existing Relief layer).
2. Click **Stamp** (next to Brush, above the rows). The rows are now the stamp's:
   - **Picture**: the built-in pictures (sponge, speckle, streaks, ragged, charcoal) and the pictures you loaded.
     **Load picture…** at the end of its list brings in your own picture file: it is kept in the project and picked.
     A loaded picture raises where it is **bright** and stays flat where it is black (a picture with see-through parts
     raises where it is opaque). Grey raises part of the way.
   - **Size**: how wide the whole picture lands (its longest side), in pixels of the screen where you click: the
     disc at the pointer shows it. On a clay it keeps that size in metres afterwards, whatever you do to the view.
     The picture's corners are always kept: nothing of it is cut off.
   - **Depth**: how far it raises the surface; below 0 % it sinks it instead (pressed in).
   - **Turn**: the picture's turn in degrees, clockwise. At 0 the picture stands upright: on a mesh (and From the
     view) the way it stands on your screen; on a clay with the clay's own up (towards its top, or towards its back
     where the surface faces straight up or down). It stays upright when you sculpt the clay again.
3. Click on the model: the whole picture lands there once. **Each stamp is one undo step**; clicking again stamps
   again (drag does nothing more while stamping). On a clay the stamp stays on its spot when you sculpt the clay again.
4. Shift+F (Final): Relief shows in Final and in the render. Too strong: undo, lower Depth, click again.

## Wear and dust: automatic masks

A layer can show only where the model's own shape says: on its **Edges** (the sharp outside edges and corners, where
paint wears off first), in its **Cavities** (creases, hollows and inside corners, where dirt gathers), where it is
**Facing up** (where dust settles), or on its **Thin parts** (ears, fins, leaves: where light shines through). Rostrum
works these out from the shape by itself; nothing is painted by hand. They follow a clay when you sculpt it again.

1. Select the model, press **B**, click **+** next to Paint layers and set **Paints**.
2. Switch **Fill** on: the layer covers the whole model with its **Fill colour** (the brush colour when you switched
   it on; change it in its row). For Roughness, Relief and Metal the colour's grey is the value (white = rough,
   raised, metal).
3. Pick a **Mask**. The first time on a model it takes a moment ("Finding edges…" on the message line); after that it
   is instant. The layer now shows only there.
4. **Spread**: how far the mask reaches (low = only the sharpest edges, the very top; high = wider). **Invert**:
   everywhere except there (paint that survives only in the recesses).
5. Brush strokes on the same layer are masked too: paint more wear by hand where you want it, only on edges.

Examples (each one layer; stack them):
- **Worn paint on a metal case**: a **Metal** layer, Fill white, Mask **Edges**, Spread about 40 %. Under the paint
  colour the bare metal shows along the edges.
- **Dust**: a **Colour** layer, Fill a light warm grey, Mask **Facing up**, Opacity about 50 %. Add a **Roughness**
  layer the same way (Fill light grey) so the dust is dull too.
- **Grime in the cracks**: a **Colour** layer, Fill a dark brown, Mask **Cavities**.

A mesh laid flat for painting before masks existed has no shape kept for them. With nothing painted on it yet,
picking a Mask lays it flat again by itself (an undo step of its own) and the mask just works. With strokes on it
the message line says so instead: laying it flat again (`mesh.unfold`) would move them.

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
  undo step). Paint mode and `paint.add` do it by themselves for a mesh with no `uvs` (a shape's own surface
  coordinates are not a paint picture: a box's top shares its walls' part of it, so paint there shows in both places).
  Call it yourself again after changing the shape: a mesh whose shape changed since it was unfolded is refused by the
  engine with a message saying so.
- `paint.add` with `target: [mesh or clay id]`, `args: {name, channel}` adds a paint layer (unfolding a mesh never
  unfolded, in the same change); `channel` is `colour`, `roughness`, `height` (shown as Relief), `metal` or `glow`
  (`paint.set` changes it).
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
- **Stamp a picture** (`paint.stamp`, one call, one undo step): `target: [mesh or clay]`, `args: {picture, size,
  depth, turn}` plus where: `at: [x, y, z, nx, ny, nz]` on a clay (look_at's `local` + `localNormal`; `size` in
  metres), `point: [x, y]` in paint picture px (`size` in px), or `viewPoint: [x, y]` in px of a view with `shot` (or
  `eye`, `target`, `fov`, `width`, `height`; `size` in screen px). `size` is the whole picture's longest side; its
  corners are never cut off (a padded copy of the picture is kept in the project for stamping). `picture` is a picture
  file (kept in the project: bright = raised) or a tip picture's name. `depth` -1..1 (below 0 sinks). `turn` is
  clockwise degrees from upright: with `viewPoint` the view's up, with `at` the clay's own +Y on the surface (−Z where
  it faces straight up or down), worked out again each time the clay is reshaped; with `point` the paint picture's
  up. It goes on the item's top Relief layer (`layer` to choose one), made when there is none. It is one stroke of one dab, so `inspect_paint_strokes` and
  `look_frame what "paint"` see it like any stroke.
- **Automatic masks and fills** are paint layer settings (`paint.add` or `paint.set` on the layer, one undo step
  each): `fill: true` with `fillColor` covers the whole surface (a whole material on one layer); `shapeMask`:
  `edges`, `cavities`, `up` (facing the item's own +Y), `thin` (or `none`), with `maskSpread` (0..1, how far it
  reaches, default 0.5) and `maskInvert`. Strokes on a masked layer are masked too. The masks are worked out from the
  shape once per shape (a clay's surface, a mesh's built mesh kept when it was unfolded: a mesh unfolded before this
  must be unfolded again) and kept; the first one on a big clay takes a few seconds. They are tools: what is worn or
  dusty is your layer's colour and value. Check with `look_frame` (Final) from the shot.
- `paintSize` on the mesh (256..8192, default 2048) is the picture's side. Paint strokes are kept in its pixels, so set
  it before painting.

## For agents: seeing and checking paint

Five tools look at paint. Canvas coordinates are always pixels of the item's paint picture (0..paintSize, x right,
y down) or a `uv` (x = u × paintSize, y = (1 − v) × paintSize).

- `look_frame what "paint" target=<mesh or clay>`: the paint picture itself, flat. All layers together, one `layer`, or one
  `channel` (`roughness`, …); `zoom` [x0, y0, x1, y1] and `grid` label canvas pixels, the same numbers `stroke.add`'s
  `points` use. Unpainted shows as a checkerboard. A clay's anchored strokes, strokes from the view and projected
  pictures are shown laid, as the render gets them. The reply gives each layer and the box that holds paint.
- `inspect_paint_strokes target=<mesh, clay or paint layer>`: one line per stroke, where it landed and how far off:
  `stroke s3 (From the view, layer paint_1): landed on case and lid, at most 1.2 screen px outside the line (canvas x
  410–980, y 220–260)`. A stroke on the surface is measured on the canvas (canvas px between its paint's centre and its
  path). A stroke from the view is measured by where its paint **shows** through its own camera, every pixel of the
  item whose spot it painted: `offPx` / `offMedianPx` how far outside the line you drew (screen px, 0 = inside the
  brush), `pieces` how many separate patches (`wantPieces`: the line's own on that item), `covered` how much of the line
  it covers. It says "landed" only when nothing shows more than 3 px (or a quarter of the brush) outside the line, in at
  most 2 more pieces than the line, covering at least 80 % of it; otherwise it says what went wrong, e.g. `painted in
  30 pieces, up to 49 screen px outside the line on lid`: look at it with `look_frame`, undo, and draw it again. Each
  row also has `uvBox`, and for a view stroke `share` (how much of the drawn path is on this item).
- `look_frame what "coverage" shot=<id> frame=<n>`: through the shot camera, how much of each mesh and clay it sees is painted
  ("lid: 62 % painted (41 000 of 66 000 px seen)"), and the frame with what is seen but unpainted hatched orange. A
  spot counts as painted where any shown layer is at least half opaque, as the screen counts. A mesh seen but never
  unfolded is named: `mesh.unfold` it first.
- `look_frame what "where" target=<item> px=[x, y]` (or `uv=[u, v]`): the reverse of `look_at`. Where that canvas spot shows on
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
   layer of that item (`paint.add` first if it has none: it unfolds a mesh never unfolded), each with the same view
   fields and the same `viewPoints`. A few points are enough for a straight or gently bending line: the path between
   them is followed pixel by pixel on the picture before it is laid on the surfaces.

   ```json
   [{"op": "stroke.add", "target": ["case_colour"], "args": {"viewPoints": [[300, 410, 1], [520, 380, 1], [700, 300, 0.6]],
     "viewEye": [1.2, 0.9, 2.4], "viewTarget": [1.0, 0.75, 1.5], "viewFov": 28.2, "viewSize": [960, 540], "viewFrame": 0,
     "size": 14, "color": "#c23b22", "brush": "round"}},
    {"op": "stroke.add", "target": ["lid_colour"], "args": {"viewPoints": [[300, 410, 1], [520, 380, 1], [700, 300, 0.6]],
     "viewEye": [1.2, 0.9, 2.4], "viewTarget": [1.0, 0.75, 1.5], "viewFov": 28.2, "viewSize": [960, 540], "viewFrame": 0,
     "size": 14, "color": "#c23b22", "brush": "round"}}]
   ```

   `size` is in pixels of that picture (screen px), not of the paint picture: the painted line is that wide on the
   screen, also on a surface seen at a slant. Leave out `points`.
4. Check: `inspect_paint_strokes` on each item says it landed there and how far outside the line, or what went wrong;
   `look_frame` shows it; `look_frame what "coverage"` shows what the shot still sees unpainted.

A stroke on the surface (`points` in canvas px) is the other way: work out the canvas pixels from `look_at`'s `uv`,
or read them off `look_frame what "paint"` with a `grid`.

## How view strokes, projected pictures and coverage are kept

- **A stroke from the view** keeps its path as drawn: `viewPoints` in pixels of a `viewSize` [width, height] picture
  from the camera `viewEye` → `viewTarget` with `viewFov` (vertical, degrees) at `viewFrame`, and `viewShot` when it
  was drawn through a shot. `stroke.add` also takes them as one `view` {eye, target, fov, frame, width, height,
  points, shot}; they are stored as the flat fields. Each time the paint is made it is laid from the camera's texel
  picture (which spot of which item every pixel sees): every screen pixel of the path takes the canvas pixel under it,
  the brush `size` goes from screen px to canvas px by how much the surface stretches across the path there (so the
  line is as wide on the screen as drawn), pressure is kept, and the path
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

## Export painted pictures

**Export painted pictures** (`paint.export`, on a painted mesh or clay) writes each channel the paint covers to a folder,
as the renderers draw it (the paint over the material's own value), for another tool: Mari, Substance Painter, a game
engine. Each channel is one file named as a **UDIM set** with its one tile, `<item>_<channel>.1001.png`
(`lid_colour.1001.png`, `lid_roughness.1001.png`; Relief is `height`, Metal `metal`), plus `<item>_paint.json`, a short
list of channel → file, its set name (`lid_colour.<UDIM>.png`) and whether it is colour (sRGB) or raw numbers. A mesh
whose faces have their own materials also gets `<item>__<material>_<channel>.1001.png` for each painted face
material. The pictures sit on the item's paint unfold (the UVs painting uses: a mesh's `uvs`, a clay's own unfold). A clay's
unfold leaves Rostrum with nothing else yet (Make clean mesh doesn't carry paint), so its exported pictures are for
looking at and keeping; a mesh's fit the mesh wherever its UVs go.
An item with no paint layer is refused. Nothing in the document changes.

- For agents: `paint.export` with `target: [mesh or clay]`, `args: {folder}` (absolute, or inside the project).
  The reply lists each item's manifest.
- Paint over a UDIM set in the material (pictures in tiles, guide `materials`) is refused: paint is one picture.
  Empty that picture field on the item's material to paint the channel.

## What it doesn't do yet

- A projected 2D render shows its first frame (a still), not the animation.
- Only plain over-painting is kept across a projected layer: a layer above it that multiplies, screens or smudges the
  layers below mixes with them as if the projected layer weren't there.
- Seams: the unfold cuts where it must. A stroke that crosses a cut continues as a second stroke on the other side,
  in the same undo step (on a clay, each time it is laid); its two halves may not meet exactly.
- A logo's or an outline's front and sides show their own material, not the paint.
