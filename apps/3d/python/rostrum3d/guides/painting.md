# Painting on a model

You paint straight onto a mesh: colour, and also how rough, how raised, how metal or how glowing each spot is. It
uses the same brushes as Draw in Rostrum2D. The paint is kept as strokes on the mesh, so every stroke can be undone and
nothing is lost when you save and open the scene again.

## On the screen

1. Select the mesh (one mesh: a lid, a case, a plinth).
2. Click **Paint** on the tool rail (the brush, at the bottom) or press **B**. The first time, the mesh is laid flat
   for painting by itself (the message line says "Unfolding Lid…" for a moment). Nothing is asked. Unfolding is one
   undo step of its own.
3. The settings panel now shows the brush and the paint layers:
   - **Brush**: the tip (round, bristle, chalk, flat, block, line), **Size** (in pixels of the paint picture, which is
     2048 px across unless you change it), **Colour** and **Opacity**.
   - **Paints**: what the active layer paints. **Colour**; **Roughness** (white = rough and dull, black = mirror);
     **Height** (white = raised, as fine relief); **Metal** (white = metal); **Glow** (its colours give off light).
   - **Paint layers**, top first. **+** adds a layer painting the same as the active one. Click a layer's name to
     paint on it; its dot shows or hides it. With no layer yet, your first stroke makes a Colour layer. A layer is
     named after what it paints ("Roughness 1") and its name follows when you change Paints, until you rename it.
4. Drag on the mesh in the viewport. A thin line follows the pointer while you drag; when you let go the paint lands.
   **Each stroke is one undo step** (Ctrl+Z takes back exactly that stroke). The disc at the pointer is the brush's
   size as it lands on the surface. Middle-drag turns the view, Shift-drag pans, so you can turn the model between
   strokes. The move handles are hidden while you paint.
5. **B** or **Esc** leaves Paint. Selecting something else leaves it too.

Paint sits over the material's own value: where you haven't painted, the surface is exactly its material (its colour,
its roughness, its own pictures). A layer painting Roughness changes only roughness: the colour stays.

Look at paint with **Look: Final** (Shift+F): Cycles shows roughness, height and metal the way the render will. Quick
shows colour, roughness, metal and glow; Height only shows in Final.

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
- `paint.add` with `target: [mesh id]`, `args: {name, channel}` adds a paint layer; `channel` is `colour`,
  `roughness`, `height`, `metal` or `glow` (`paint.set` changes it).
- `stroke.add` with `target: [paint layer id]`, `args: {points: [[x, y, pressure], …], color, size, brush, opacity}`
  paints one stroke, in pixels of the paint picture (0..paintSize, y down). Several `stroke.add` calls in one
  `edit_document` call list are one undo step.
- `look_at` on the viewport gives `uv` (with the engine's pick): the canvas pixel there is x = u × paintSize,
  y = (1 − v) × paintSize. Check the result with `look_frame` (Final) from the shot camera.
- `paintSize` on the mesh (256..8192, default 2048) is the picture's side. Paint strokes are kept in its pixels, so set
  it before painting.

## What it doesn't do yet

- Painting from the camera (strokes projected through the view), projecting a picture onto shapes, and the coverage
  tint come next.
- Seams: the unfold cuts where it must. A stroke that crosses a cut continues as a second stroke on the other side,
  in the same undo step; its two halves may not meet exactly.
- Faces with their own material (an editable mesh's face materials, a logo's sides) show their own material, not the
  paint.
