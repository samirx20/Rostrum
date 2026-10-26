# Sculpting with clay

Clay is a lump you push into shape with brushes, the way you would with real modelling clay: build it up, carve into
it, smooth it out. You never deal with points or faces. Every stroke is kept (not just the result), so each one can be
undone, and the clay comes back exactly the same when you open the scene again.

## On the screen

1. Click **Clay** on the tool rail (the second button, under Select) or press **Q**. The settings panel shows the Clay
   tool: **Make**, and once a clay is selected, **Brush** with its settings. The rest of the window stays as it is.
2. **Make a clay.** With **Lump** chosen (it is chosen when nothing to sculpt is selected), click in the viewport: a
   hand-sized ball of clay (20 cm across) lands there, sitting on the ground or on the surface you clicked, and
   is selected; its brush starts at a quarter of its size. Click on a clay with Lump and a ball the size of the brush
   **joins** it, blended in softly. Each Lump is one undo step. The pointer is a cross while Lump is
   chosen; dragging turns the view.
3. **Pick a brush** in the panel: **Add** builds clay up under the brush, **Carve** takes clay away, **Smooth** evens
   bumps out. Rest the pointer on a tile to see what it does.
4. **Drag on the clay** to sculpt. A ring lying on the surface shows the brush: where it touches and how big it is.
   While the Clay tool is on, the clay you sculpt has no selection outline: the ring is its only mark. The clay changes under the pointer while you drag; when you let go, **the whole stroke is one undo step** (Ctrl+Z
   takes back exactly that stroke).
   - Hold **Ctrl** for the opposite brush: Add carves, Carve adds.
   - Hold **Shift** to smooth, whatever brush is chosen.
   - **Drag on empty space** to turn the view around the clay, so you can work on its other side between strokes; no
     need for the middle button. The wheel zooms. A click on another thing selects it.
5. Under the brushes:
   - **Size**: the brush's radius, in metres (0.03 m = 3 cm).
   - **Strength**: how much one stroke changes the clay.
   - **Mirror**: **Left–right** (the start) makes every stroke on one side happen on the other side too, mirrored
     across the clay's own middle, so a face or a body stays even. **Off** sculpts one side only.
   These are the clay's settings for its next stroke: changing them never changes strokes already made (each stroke
   keeps the settings it was made with). Each change is one undo step.
6. **Q** again, **V** or **Esc** goes back to Select. The move handles are hidden while the Clay tool is on, so they
   never sit on the clay you are sculpting; with Select they are back.

## How it is kept

A clay's shape is its list of steps, in order: the balls and joins Lump made, then every stroke. A stroke is stored
as the exact path of brush touches it made, in a small file in the project's `clay` folder, so it replays to exactly
the same shape. The clay's **Detail** (how fine its grain is, set from the first ball's size) is under **+ Detail** in
its settings when Select is on. The brush settings (Brush, Size, Strength, Mirror, Build up) show only while the Clay
tool is on; with Select they are not in the settings. An agent can still read and set them any time (`clay.set`).

## For agents

The Clay tool makes the same operations an agent calls (guides `agents` and `script`):

```
clay.add(at=[0, 0.15, 0], radius=0.15)                 -> a new clay with one ball (at: in the scene)
clay.lump(target="clay_1", at=[0.1, 0.05, 0], radius=0.06)   -> a ball joined on (at: in the clay's own space)
clay.shape(target="clay_1", shape="capsule", at=[..], to=[..], radius=0.03, mode="carve")
clay.stroke(target="clay_1", brush="add", path=[[x, y, z], …], dir=[0, 0, -1])   -> a stroke along a path
clay.set(target="clay_1", brush="smooth", brushSize=0.02, brushStrength=0.4, symmetry="off")
claystep.remove(target="clay_1.step_3") · claystep.set(target="clay_1.step_3", name="nose")
```

A person's strokes are `clay.stroke` with `dabs="clay/<hash>.dabs"` (the file the stroke wrote). A script run again
keeps the steps a person added to its clay.
