# Animation layers

A layer lays a move over the animation you already have, with a weight: a breath over a walk, a shake over a
camera move, a head turn over a pose. The animation you keyed first is the **Base**; layers sit on top of it, and
the stack is read from the bottom up.

## In the window
1. On the Animate page, click **⧉** at the left of the timeline's header, then **+ New layer**. The new layer is
   chosen: the ⧉ button is lit, and the timeline's rows show only this layer's keys.
2. Key as usual (move with the gizmo, type a value in the settings panel, K). While a layer is chosen, what you set
   goes on the layer, and the picture shows exactly the value you set.
3. Back in the popover: drag a layer's **weight** (0 % = none of it, 100 % = all of it), switch it **off** to compare,
   pick **Add** or **Replace**, double-click its name to rename it. Click **Base** to key the Base again.
4. To fade a layer in: put the playhead where the fade starts, ⋯ › **Key the weight here**, drag the weight to 0 %;
   move the playhead, drag the weight to 100 %. Once the weight has a key, the slider keys it at the playhead.
5. ⋯ › **Delete layer and its keys** removes it; the Base is untouched. Every change is one undo step.

## Add or Replace
- **Add**: the layer's keys are amounts added on top (0 = no change). Numbers only: a colour on an Add layer is left
  as the Base has it.
- **Replace**: the value moves toward the layer's keys by the weight (100 % = the layer's value). Numbers and colours.
- On / off settings (Visible) and shapes always read the Base.

## For agents
- `animlayer.add {id, name, mode: "add" | "replace", weight}` makes a layer on top of the stack.
- `key.add {prop, t, v, layer: "<layer id>"}` puts a key on it (on an Add layer `v` is the amount added).
- `animlayer.set {weight, at}` keys the weight (a fade); without `at` it sets the weight (refused once the weight has
  keys: give `at`). `animlayer.set {name | mode | on}`; `animlayer.move {to}` (0 = bottom); `animlayer.remove`
  deletes the layer and every key on it.
- A layer and its keys made by a person stay when your script runs again.
