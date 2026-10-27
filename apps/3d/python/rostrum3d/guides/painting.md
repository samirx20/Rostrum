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
   - **Brush**: the tip (round, bristle, chalk, flat, block, line), **Size** (in pixels of the paint picture, which is
     2048 px across unless you change it), **Colour** and **Opacity**.
   - **Paints**: what the active layer paints. **Colour**; **Roughness** (white = rough and dull, black = mirror);
     **Relief** (white = raised, black = sunk: fine detail such as wrinkles, pores and scratches); **Metal** (white =
     metal); **Glow** (its colours give off light).
   - **Paint layers**, top first. **+** adds a layer painting the same as the active one. Click a layer's name to
     paint on it; its dot shows or hides it. With no layer yet, your first stroke makes a Colour layer. A layer is
     named after what it paints ("Roughness 1") and its name follows when you change Paints, until you rename it.
4. Drag on the model in the viewport. A thin line follows the pointer while you drag; when you let go the paint lands.
   **Each stroke is one undo step** (Ctrl+Z takes back exactly that stroke). The disc at the pointer is the brush's
   size as it lands on the surface. Middle-drag turns the view, Shift-drag pans, so you can turn the model between
   strokes. The move handles are hidden while you paint.
5. **B** or **Esc** leaves Paint. Selecting something else leaves it too.

Paint sits over the material's own value: where you haven't painted, the surface is exactly its material (its colour,
its roughness, its own pictures). A layer painting Roughness changes only roughness: the colour stays.

Look at paint with **Look: Final** (Shift+F): Cycles shows roughness, relief and metal the way the render will. Quick
shows colour, roughness, metal and glow; Relief only shows in Final.

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
  layer yet gives no `uv`, only `local`.
- `paintSize` on the mesh (256..8192, default 2048) is the picture's side. Paint strokes are kept in its pixels, so set
  it before painting.

## What it doesn't do yet

- Painting from the camera (strokes projected through the view), projecting a picture onto shapes, and the coverage
  tint come next.
- Seams: the unfold cuts where it must. A stroke that crosses a cut continues as a second stroke on the other side,
  in the same undo step (on a clay, each time it is laid); its two halves may not meet exactly.
- Faces with their own material (an editable mesh's face materials, a logo's sides) show their own material, not the
  paint.
