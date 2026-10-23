# Modelling: shapes, and cutting or joining them (live booleans)

Every shape is an item made from numbers you can change later: `mesh.add` (or `mesh(...)` in a script) with a `shape` and
its sizes in metres. Shapes join, cut and overlap through a **combine**: a live boolean, worked out by the engine
(Manifold) every time the scene is drawn, so the quick view, Final and the Render button all show the same cut.

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

## Errors (loud, never a silent wrong shape)

- **"is not a closed solid"**: a plane, a disc or an imported part with holes can't be combined, because it has no inside.
  Use a box or a cylinder with a small depth instead.
- **"Subtract gave an empty shape"**: the cutters cover the base entirely. Make them smaller or move them.
- **"Intersect gave an empty shape"**: the solids don't overlap.
- **"can't be animated yet"**: an input of a combine can't have keys (the cut is made once per shot). Key the combine
  itself to move the whole result.
- **"needs two or more"**: a combine holds at least two solids.

## Technique

- **Build the base first, at its real size and bevel, then cut.** A cut keeps the base's bevel everywhere except the new
  edge, which is sharp. Real ports and slots are often small and sharp, which reads correctly at product scale.
- **Cutters longer than the wall.** A port cutter 2–3 mm longer than the wall on each side cuts cleanly at any angle.
- **Several cutters, one combine.** Twelve grille holes are twelve cutters in one Subtract (made with a loop in a script),
  not twelve combines inside each other.
- **Nesting.** A combine can be an input of another: a union of a body and a handle, then a subtract of a slot from it.
