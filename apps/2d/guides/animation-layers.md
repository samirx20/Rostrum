# Animation layers

A layer lays a move over the animation you already have, with a weight: a wobble over a slide, a breath over a pose,
a shake over a frame move. The animation you keyed first is the **Base**; layers sit on top of it, and the stack is
read from the bottom up.

## In the window
1. Click **⧉** in the timeline's header (just left of **Keys** / **Curves**), then **+ New layer**. The new layer is
   chosen: the ⧉ button is lit, and the timeline's rows show only this layer's keys.
2. Animate as usual: drag on the canvas, type a value in the settings panel, press K. While a layer is chosen, what
   you set goes on the layer as a key at the playhead, and the picture shows exactly the value you set. The settings
   panel always shows the value with every layer laid over.
3. To move keys of a layer in time, choose the layer first: only its keys show and move. A layer's key may sit at the
   same time as a Base key.
4. Back in the popover: drag a layer's **weight** (0 % = none of it, 100 % = all of it), switch it **off** to compare,
   pick **Add** or **Replace**, double-click its name to rename it. Click **Base** to key the Base again.
5. To fade a layer in: put the playhead where the fade starts, ⋯ › **Key the weight here**, drag the weight to 0 %;
   move the playhead, drag the weight to 100 %. Once the weight has a key, the slider keys it at the playhead.
6. ⋯ › **Delete layer and its keys** removes it; the Base is untouched. Every change is one undo step.

What the canvas shows is what the export writes: layers are laid in once, for both.

## Add or Replace
- **Add**: the layer's keys are amounts added on top (0 = no change). Numbers only: a colour on an Add layer is left
  as the Base has it.
- **Replace**: the value moves toward the layer's keys by the weight (100 % = the layer's value). Numbers and colours.
- A path's shape and width profile, and on / off settings, always read the Base.
- A field driven by an expression: the layer is laid over the expression's value. A field an auto layout sets
  (inside a row, column or grid) is the layout's: layers don't move it.

## For agents
A script's `.key()` keys the Base. Layers are operations (`edit_document`, or `inspect_operations name: animlayer.add`):
- `animlayer.add {id, name, mode: "add" | "replace", weight}` makes a layer on top of the stack.
- `key.add {prop, t, v, layer: "<layer id>"}` puts a key on it (on an Add layer `v` is the amount added; 0 = no change).
- `animlayer.set {weight, at}` keys the weight (a fade); without `at` it sets the weight (refused once the weight has
  keys: give `at`). `animlayer.set {name | mode | on}`; `animlayer.move {to}` (0 = bottom); `animlayer.remove`
  deletes the layer and every key on it.
- `look_frame` shows the stack laid over, as the export will. A layer and its keys made by a person stay when your
  script runs again.
