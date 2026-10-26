# Modelling: shapes, and cutting or joining them (live booleans)

Every shape is an item made from numbers you can change later: `mesh.add` (or `mesh(...)` in a script) with a `shape` and
its sizes in metres. Shapes join, cut and overlap through a **combine**: a live boolean, worked out by the engine
(Manifold) every time the scene is drawn, so the quick view, Final and the Render button all show the same cut.

## Shapes, and placing them on a surface

`box` (width height depth, bevel), `sphere` (radius), `cylinder` (radius height, bevel), `cone` (radius of the base,
height to the point), `capsule` (radius, height end to end: at least twice the radius), `torus` (radius, tube),
`plane` and `disc` (flat, facing up). Each is centred on its origin with up along +Y.

On screen: **Shapes** in the rail, pick one, click where it goes. It lands with its base on the surface you clicked,
standing along it, a fifth the size of the thing you clicked (10 cm on the floor or in an empty scene). Then type exact
sizes in the settings panel.

In a script, stand one mesh on another with `place_on`: its base on the other's top, over its middle; move it along
the top afterwards.

      mesh("plinth", shape="box", width=0.5, height=0.3, depth=0.5, y=0.15)
      mesh("cap", shape="cone", radius=0.04, height=0.09).place_on("plinth").set(x=0.12)

Agents placing by numbers use `mesh.add`'s `x y z rx ry rz`; the engine's `pick` gives the point **and the surface's
direction** (`normal`) under any pixel, so an agent can do what the screen does.

## Text and logos

`text` (the words, `font`, `size` = the em in metres, `weight`, `tracking`, `lineHeight`, `align`), `svg` (`svgFile` or
`pathData`, `svgWidth`) and `path2d` (`doc2d` + `layer`: a path layer of a 2D item in this project, linked) are flat
outlines pushed out `depth` along their own +Z (the front), with a rounded edge `bevel`. Text is centred on its origin.

On screen: **Type & logo** (T) in the rail, pick one, click where it goes. It stands upright facing the shot camera
(never flat on the floor), base on the top you clicked, or in front of the side you clicked; then type the words in
place (window guide). Agents do the same with `mesh.add shape=text … x y z ry`: `ry` turns its front (+Z) toward the
camera (`ry` = atan2(camera x − x, camera z − z) in degrees).

**Largest bevel.** A bevel too big for the outline (a thin stroke, a sharp corner) fails loudly: the engine says
"… Accepted: at most 0.001602 m for this outline". The Bevel row then says so in a line under it and offers **Use 1.60 mm** (the
largest that fits) beside it: one click sets it (one undo step, `mesh.set bevel`). A modest bevel is about a hundredth of the
size; thin fonts and fine logos take less.

## Combine: union, subtract, intersect

A **combine** item holds two or more solids (meshes, or other combines) as its children, in order. The engine draws only
the result; the children are its inputs and are never drawn themselves.

- **`union`** joins them into one shape (a handle welded to a body, a word sunk into a base).
- **`subtract`** cuts every later child out of the **first** one. The first is the base; the others are cutters. A charging
  port, a speaker grille, a slot, a recess for a button.
- **`intersect`** keeps only the space all of them share (a rounded tablet from a box and a sphere).

It stays live. The inputs remain items with their own settings: move, turn or resize a cutter and the hole moves with it;
change the base's bevel and the cut edge follows. Nothing is baked.

### On the screen

1. Select the base (click it in the scene list), then Shift+click or Ctrl+click the cutter(s).
2. The top of the settings panel shows **Combine: Union · Subtract · Intersect**. Rest the pointer on one: the viewport shows
   the result before you press. Press it.
3. The scene list now shows one row with the base's name and a Combine icon, its inputs indented under it; in a Subtract
   the cutters carry a minus sign. Select a cutter's row to move it (its settings, or the gizmo); the hole follows.
4. Select the combine row to change **Operation**, its **Material** (the whole result wears one material; it starts as the
   base's) or to move the whole thing. Undo takes back the combine in one step.

### For agents

- Operation: `combine.make` with `target: [base, cutter, …]` (order matters: the first is the base) and `op`
  (`union`, `subtract`, `intersect`). All targets must sit in the same list (the top level or the same group): move them
  together first with `item.arrange` if not. The new combine takes the base's place and name; its id is counted
  (`combine_1`) unless you give `id`.
- Change it with `combine.set` (`op`, `material`, transform). Move an input with `mesh.set` on that input. Add another
  cutter with `mesh.add into=<combine id>`.
- In a script:

  ```python
  with combine("case", op="subtract"):
      mesh("body", shape="box", width=0.064, height=0.03, depth=0.048, bevel=0.004)
      mesh("port", shape="cylinder", radius=0.0035, height=0.02, rz=90, x=0.032)
  ```

  An input's position is relative to the combine, like any child.
- Always look after a cut (`look_frame`, then `look_at` on the cut to check it hit what you meant). A cutter that only
  touches the surface (shares a face with it) leaves a paper-thin skin or nothing: make cutters a little longer than the
  wall they go through.

## Editable mesh: extrude, inset, bevel, cut, smooth

Any shape (box, sphere, text …) or combine can become an **editable mesh**: its points and faces exactly as they were
drawn, joined where they meet. Then you push faces out (**Extrude**), make a smaller face inside a face (**Inset**), or
move, turn and scale points, edges and faces. Each action is one undo step, and the mesh is saved with the project.
Making a combine editable is its **Bake**: the result becomes one plain mesh and the inputs are gone (undo brings them
back).

### On the screen

1. Select the item and press **Enter** (or **Edit mesh** in the settings panel, or right-click it › Edit mesh). The first time, the panel says "Turns the
   box into an editable mesh · Edit": click **Edit**. The box's Width / Height fields go; the mesh is now points and
   faces.
2. Pick what to select at the top of the settings panel, or press **1** points, **2** edges, **3** faces.
3. Click a face (or point, or edge) in the viewport; **Shift+click** adds or removes; drag on empty space to box-select.
   The selection is drawn in blue, faces tinted. Only the edges you edit are drawn in full: the little edges inside a
   rounded corner (faces meeting at under about 35 degrees) are drawn faint. Box select and click pick only what you can
   see; **X-ray** (button, or **Alt+Z**) lets them reach points, edges and faces hidden behind the mesh.
4. With faces selected, the panel shows "1 face" and **Extrude** and **Inset**. Press one: it runs at once with its last
   numbers (Extrude: Distance; Inset: Width, Depth), and those numbers then show below it until your next action: type
   2 mm and that action is redone at 2 mm, still one undo step. After Extrude, an arrow stands on the faces: drag it and
   the distance follows the pointer in 0.5 mm steps (hold Ctrl for free), one step when you let go. While the arrow
   shows, the gizmo steps aside. With faces picked, **Material** gives them a material from the project (or "The shape's
   own" takes it back).
   With edges selected, the panel shows **Bevel** (Width, Segments), **Loop cut** (Cuts, Slide) and **Sharp** / **Not
   sharp**. Bevel and Loop cut work as above: numbers below, typed again as the same one step. After Bevel an arrow
   stands on the edges: drag it and the width follows live. **Knife** (button, or **Shift+K**): click points across the faces,
   a line is drawn as you go, **Enter** cuts along it (one undo step), **Esc** drops it. **Smooth surface** (0 to 3) is in
   the Shape group of the settings once the mesh is editable.
5. Otherwise the gizmo sits on the selection: drag it to move, turn (E) or scale (S) the selected points, edges or faces;
   each drag is one undo step.
6. Middle-drag turns the view while you edit. **Esc** (with no Knife line) or **Shift+Enter** leaves editing, and so does picking another item.

### For agents

- `mesh.edit` with `target: [id]` (a mesh or a combine): makes it editable, in one step. It reads the shape from the
  engine, so it runs in the app and the 3D MCP server.
- Name what to change with a **selector**, never by guessing numbers: `"top"`, `"bottom"`, `"front"` (towards the default
  camera, +z), `"back"`, `"left"`, `"right"` (the outermost faces facing that way), `"faces facing +y"` (every face within
  30° of up; `"faces facing -x within 10"`), `"all"`, or by number: `"faces 3 4"`, `"points 0 1"`, `"edges 0-1 1-5"` (an
  edge by its two points), `"edges around top"` (the loop round what a faces selector picks).
- `faces.extrude` `{faces, distance}` (metres; negative pushes in). `faces.inset` `{faces, width, depth}`. Both answer
  with the faces that are now selected (`{"faces": "faces 3"}`), so the next action can use them.
- `mesh.transform` `{select, move: [x, y, z], turn: [x, y, z] degrees, scale: [x, y, z]}`, in the item's own space,
  around the selection's middle. Push the lid's top up 2 mm: `{"op": "mesh.transform", "target": ["lid"], "args":
  {"select": "top", "move": [0, 0.002, 0]}}`.
- `edges.bevel` `{edges, width, segments}`: rounds the edges `width` metres wide with `segments` rows (1 is a flat
  chamfer; 4 is a smooth round). Round the lid's top edge:
  `{"edges": "edges around top", "width": 0.001, "segments": 4}` (`"edges around …"` takes any faces selector and names
  the loop of edges round it). Too wide fails, saying the largest that fits. Answers
  with the new faces.
- `edges.loopcut` `{edges, count, slide}`: name one edge; the ring of four-sided faces across it is cut `count` times
  (one cut: `slide` -1..1 moves it towards either side). `mesh.knife` `{points: [[x, y, z], …], view: [x, y, z]}`: a
  line through the points (the item's own space, on the surface), seen along `view`; each face it passes over is cut
  right across. Fails if it cuts nothing.
- `faces.material` `{faces, material}`: those faces take that material (`""` gives them the item's own again). It
  follows the faces through later cuts, bevels and smoothing.
- **Smooth surface:** `mesh.set` `{subdivide: 0..3}` rounds the whole mesh (Catmull-Clark, OpenSubdiv): 2 on a box gives
  a pebble. Edges marked sharp stay sharp: `edges.sharp` `{edges, sharp: true}` (false unmarks). Mark the edges first,
  then smooth; the cage (the points you edit) stays the same, only the drawn surface rounds.
- Every one of these is one undo step. Look after each edit (`look_frame`). An edited mesh's `points`, `faceCounts`,
  `faceIndices`, `creases` (sharp edges) and `faceMaterials` are in the document like USD's mesh, but change them through
  these operations, not by hand.

## Errors (loud, never a silent wrong shape)

- **"is not a closed solid"**: a plane, a disc or an imported part with holes can't be combined, because it has no inside.
  Use a box or a cylinder with a small depth instead.
- **"Subtract gave an empty shape"**: the cutters cover the base entirely. Make them smaller or move them.
- **"Intersect gave an empty shape"**: the solids don't overlap.
- **"can't be animated yet"**: an input of a combine can't have keys (the cut is made once per shot). Key the combine
  itself to move the whole result.
- **"needs two or more"**: a combine holds at least two solids.
- **"picks nothing on this mesh"**: the selector matched no face (a sphere has no flat "top"; use `"faces facing +y"`).
- **"is too wide for face n"**: an inset wider than the face has room for; the message gives the most that fits.

## Technique

- **Build the base first, at its real size and bevel, then cut.** A cut keeps the base's bevel everywhere except the new
  edge, which is sharp. Real ports and slots are often small and sharp, which reads correctly at product scale.
- **Cutters longer than the wall.** A port cutter 2–3 mm longer than the wall on each side cuts cleanly at any angle.
- **Several cutters, one combine.** Twelve grille holes are twelve cutters in one Subtract (made with a loop in a script),
  not twelve combines inside each other.
- **Inset, then extrude** for a raised or sunken panel: a button's rim is an inset of 1 mm and an extrude of −0.5 mm.
- **Make it editable late.** A box keeps its typed sizes and bevel until you edit it; do the sizes first.
- **Nesting.** A combine can be an input of another: a union of a body and a handle, then a subtract of a slot from it.
