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
3. **Pick a brush** in the panel. Six shape the clay:
   - **Add** builds clay up under the brush; **Carve** takes clay away; **Smooth** evens bumps out.
   - **Pull** grabs the clay under the brush and drags it along the stroke: a nose, a chin, an ear tip.
   - **Flatten** planes the clay towards its average surface: the planes of a face, a cut rock.
   - **Crease** pinches a sharp line or valley: lips, eyelids, folds.

   The seventh, **Mask**, on its own row, shapes nothing: it paints a mask on the clay, and no brush changes masked
   clay until the mask is taken away (hold **Ctrl** with Mask to take it off where you drag). Mask a part you have
   finished, then work right next to it without spoiling it. Rest the pointer on a tile to see what it does.
4. **Drag on the clay** to sculpt. A ring lying on the surface shows the brush: where it touches and how big it is.
   While the Clay tool is on, the clay you sculpt has no selection outline: the ring is its only mark. The clay changes under the pointer while you drag; when you let go, **the whole stroke is one undo step** (Ctrl+Z
   takes back exactly that stroke).
   - Hold **Ctrl** for the opposite: Add carves, Carve adds, Flatten puffs the clay out, Crease pinches it up into a
     ridge, Mask takes the mask away. (Smooth and Pull have no opposite.)
   - Hold **Shift** to smooth, whatever brush is chosen.
   - **With a pen** (a drawing tablet), pressing harder makes the brush bigger and stronger, lighter makes it smaller
     and gentler, within Size and Strength. A mouse always uses Size and Strength as they are.
   - **Drag on empty space** to turn the view around the clay, so you can work on its other side between strokes; no
     need for the middle button. The wheel zooms. A click on another thing selects it.
5. Under the brushes:
   - **Size**: the brush's radius, in metres (0.03 m = 3 cm). Faster: rest the pointer on the clay, **hold F** and move
     the pointer right (bigger) or left (smaller); the ring shows the new size as you move, and letting go of F keeps
     it (one undo step).
   - **Strength**: how much one stroke changes the clay.
   - **Mirror**: **Left–right** (the start) makes every stroke on one side happen on the other side too, mirrored
     across the clay's own middle, so a face or a body stays even. **Off** sculpts one side only.
   - **Falloff**: how the brush fades towards its edge: low is soft (it blends in), high is a hard edge (a crisp step).
   - **Spacing**: how far apart the brush's touches are along a stroke, as a share of its size. Low gives an even,
     smooth stroke; high leaves a row of separate dents or bumps.
   - **Front faces only** (on at the start): a stroke only touches the side of the clay facing you, so it never
     reaches through a thin part (an ear, a fin) to the far side. Turn it off to work both sides of a thin part at once.
   These are the clay's settings for its next stroke: changing them never changes strokes already made (each stroke
   keeps the settings it was made with). Each change is one undo step.
6. **Q** again, **V** or **Esc** goes back to Select. The move handles are hidden while the Clay tool is on, so they
   never sit on the clay you are sculpting; with Select they are back.

## How it is kept

A clay's shape is its list of steps, in order: the balls and joins Lump made, then every stroke. A stroke is stored
as the exact path of brush touches it made, in a small file in the project's `clay` folder, so it replays to exactly
the same shape. The clay's **Detail** (how fine its grain is, set from the first ball's size) is under **+ Detail** in
its settings when Select is on. The brush settings (Brush, Size, Strength, Mirror, Falloff, Spacing, Front faces only)
show only while the Clay tool is on; with Select they are not in the settings. An agent can still read and set them
any time (`clay.set`). Each stroke keeps its own copy of them, and whether it was Ctrl's opposite (`invert`).

## For agents

The Clay tool makes the same operations an agent calls (guides `agents` and `script`):

```
clay.add(at=[0, 0.15, 0], radius=0.15)                 -> a new clay with one ball (at: in the scene)
clay.lump(target="clay_1", at=[0.1, 0.05, 0], radius=0.06)   -> a ball joined on (at: in the clay's own space)
clay.shape(target="clay_1", shape="capsule", at=[..], to=[..], radius=0.03, mode="carve")
clay.stroke(target="clay_1", brush="add", path=[[x, y, z], …], dir=[0, 0, -1])   -> a stroke along a path
clay.set(target="clay_1", brush="smooth", brushSize=0.02, brushStrength=0.4, symmetry="off",
         brushFalloff=0.5, brushSpacing=0.3, frontOnly=True)    # brush: add carve smooth pull flatten crease mask
claystep.remove(target="clay_1.step_3") · claystep.set(target="clay_1.step_3", name="nose")
```

A person's strokes are `clay.stroke` with `dabs="clay/<hash>.dabs"` (the file the stroke wrote), and `invert=True`
when Ctrl was held with Flatten, Crease or Mask (Add and Carve swap the brush instead). A script run again
keeps the steps a person added to its clay.
