# Rostrum2D characters: rigs, bones, IK (Team Hem, H10)

A **rig** is a layer that holds other layers (like a group) plus **bones**, **IK chains** and **binds**. People and
agents edit them with operations; the engine poses the bones and moves the bound layers **every frame** (Rust,
`engine/render/src/rig/`), so the canvas, the look tools and the export see the same pose (preview ≡ export).

## The document

```
rig (a layer: w, h, clip + transform)
 ├ layers  ─ any layers (shape, image, drawing, path, group …), drawn in list order, positioned in the rig's px
 ├ bones   ─ bone ─ keys
 ├ iks     ─ ik ─ keys
 └ binds   ─ bind
```

All positions are **rig px** (from the rig box's top-left, the same space its layers are placed in). Angles are
degrees, clockwise on screen (as a layer's rotation); 0 = pointing right, 90 = pointing down.

| Item | Field | Kind | Animatable | Meaning |
|---|---|---|---|---|
| **bone** | `parent` | text | no | Id of the parent bone; "" = a root bone. |
| | `x`, `y` | number | no | Rest pivot (the joint it turns about), rig px. |
| | `angle` | number | no | Rest direction. |
| | `length` | number | no | Rest length, px (≥ 0). The tip is `length` along `angle` from the pivot. |
| | `rotation` | number | yes | Turn from rest (adds to the parent's turn: FK). |
| | `scale` | number | yes | Uniform scale about the pivot (children and bound layers follow). Default 1. |
| | `moveX`, `moveY` | number | yes | Shift of the pivot, px, in the parent's (posed) frame; a root's moves the whole character. |
| **ik** | `bone` | text | no | The chain's **lower** bone (shin, forearm). Its parent is the upper bone (thigh, upper arm). |
| | `mode` | choice `ik` / `fk` | no | FK / IK switch for this chain. Every field below is valid only when `mode` = `ik`. |
| | `mix` | number 0..1 | yes | 1 = the IK pose, 0 = the FK pose (key it to blend FK → IK over time). Default 1. |
| | `targetX`, `targetY` | number | yes | Where the lower bone's tip reaches to, rig px. |
| | `bend` | choice `clockwise` / `counterclockwise` | no | Which way the middle joint (knee, elbow) bends. |
| | `pin` | number 0..1 | yes | While ≥ 0.5 the target is **held** where it was when the pin turned on (a planted foot), whatever the target keys or the body do. Key it with `hold`: 1 at the contact, 0 at the lift. |
| **bind** | `layer` | text | no | Id of a layer directly in this rig's `layers` (not inside a group in it). A layer has at most one bind. |
| | `bone` | text | no | The bone it follows. |
| | `bone2` | text | no | "" = **rigid** (the layer follows `bone` as one piece). A child bone of `bone` = **bend**: the layer is drawn through a mesh skinned to both bones (a bent arm or leg in one picture). |
| | `grid` | number 4..64 | no | Bend only: mesh divisions along each side. Default 24. |
| | `soft` | number px | no | Bend only: half-width of the blend zone around the joint (0 = a hard crease). Default 40 (about the limb's width or more reads as a bend, less as a crease). |

Rest pose = every animated bone field at its still value (rotation 0, scale 1, moves 0), iks ignored. A layer is
placed by the person at rest; its bind makes it follow its bone's motion **from rest**: its own keys still work on top.

## Evaluation at time t (engine, per frame, pure function of t)

1. **FK**, parents before children. Rest world R_b = T(x, y) · Rot(angle). Local rest L_b = R_parent⁻¹ · R_b (root:
   R_b). Posed world P_b = P_parent · L_b · T(moveX, moveY)' · Rot(rotation) · S(scale), where the move is in the
   parent's posed frame (applied before L_b's rotation: P_b = P_parent · T(move) · L_b · Rot · S).
2. **IK**, chains in order of the upper bone's depth: with the upper bone's posed pivot and both bones' posed
   lengths, the two-bone solve (law of cosines) turns the upper and lower bone so the lower tip reaches the target
   (pinned target per § pin; an unreachable target: the chain points straight at it). The turns found are blended
   with the FK turns by `mix` (shortest angle), then the descendants are re-posed.
3. **Deltas:** D_b = P_b · R_b⁻¹ (a similarity: move, turn, uniform scale).
4. **Rigid bind:** the layer's anchor point (x, y) → D_b · (x, y); `rotation` += turn of D_b; `scale` ×= scale of D_b.
5. **Bend bind:** the layer keeps its transform; the engine gives it a `grid × grid` warp mesh over its box (the
   renderer's `<fewarp>` primitive, `vendor/blitz-paint/src/warp.rs`). Each mesh point, taken to rig px through the
   layer's rest transform, is `w·D_bone(p) + (1−w)·D_bone2(p)`, w from its distance past `bone2`'s pivot along the
   bones (smoothstep over `±soft`), then back to the layer's px.
   "Along the bones" is the mean of the two bones' rest directions. The mesh covers the layer's box plus 15 % of its
   longer side on every edge (so strokes and shadows bend with it); only a layer with a box (`w`, `h`) can be bent
   (not text). The warp is its own filter on the layer's outer box; the layer's blur, glow and shadow are drawn
   inside it, so they bend too.
6. **Pin:** the held target is the target's value at the start of the current stretch where `pin` ≥ 0.5 (found
   from the pin keys alone, so any frame can be drawn on its own); an unkeyed pin that is on holds the target's
   first value.

## Agents' eyes: the engine's `bones` request

`{"bones": {"t": 1.25}}` → `{"ok": true, "rigs": {"<rig id>": {"bones": {"<id>": {"x", "y", "tipX", "tipY", "angle"}},
"iks": {"<id>": {"targetX", "targetY", "gap"}}, "camera": [a, b, c, d, e, f]}}}`: posed pivots, tips and angles in
**screen px** (through the rig's and its parents' 2D transforms and the comp's camera, CAMERA.md; tilt ignored; with no
camera, screen px are comp px), and each IK's (held) target and the distance its tip misses it by. `camera` is the
matrix the camera added (screen = camera · comp px); `inspect_rig_motion` undoes it, so a pinned foot is measured where
it stands in the comp, not where a moving camera shows it.

## Scene description (ENGINE_CONTRACT.md § 2, same version)

A `rig` node is a layer with `layers` and a `rig` list: its bones, iks and binds as nodes (`{"id", "type": "bone",
"props", "anim"?}` …), every field present. Unknown bones / layers named in an ik or bind, a cycle of parents, two
binds on one layer, or a `bone2` that isn't a child of `bone` are refused when the scene loads, naming the item.

## Operations (Python, `rostrum2d/rig/`)

- `layer.add` with `type: "rig"`; layers go into it with `layer.add` targeting the rig.
- `bone.add` (target: rig; `id`, `parent`, `x`, `y`, `angle`, `length`; with a `parent` and no `x`/`y` it starts at
  the parent's rest tip), `bone.remove` (its children go to its parent; its binds and iks go too), `bone.set`.
- `ik.add` (target: rig; `bone`; the target starts at the chain's rest tip), `ik.remove`, `ik.set`.
- `bind.add` (target: rig; `layer`, `bone`, `bone2`), `bind.remove`, `bind.set`.
- Keys: the usual `key.add` / `value.set` on bone and ik fields.
- Script: `with rig("puppet", w=, h=, ...):` then `bone(...)`, `ik(...)`, `bind(...)` inside; `.key(field, {t: v}, ease=)`
  on bones and iks as on layers.
