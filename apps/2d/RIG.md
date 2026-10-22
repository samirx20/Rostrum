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

## Swap sets (a slot that shows one drawing at a time)

A swap set is an ordinary `group` with two more fields (Python side only, `rostrum2d/swap.py`; the engine never sees
them). `swap` ("One at a time", group "Swap set", secondary) turns the group into a slot. `show` ("Shows", whole number
0–999, animatable) exists only while `swap` is on (rule of individuality): which child shows, **0 = the first in the
list**. In the inspector it is a choice among the slot's own children by name, not a number (`screen2d/swap_rows.py`).

`show` is a **stepped choice**: its keys always read as jumps, whatever ease they carry (the value holds until the next
key), and it is clamped to the children (a number past the last child shows the last). Operations that key it use `hold`.

Scene translation (`swap.apply`, after layout and chains, before stepped timing): the set is sent as a plain group.
`show` is sampled on every frame; each child's opacity is multiplied by 1 (shown) or 0 (hidden). A child with no opacity
keys gets one `hold` key where it turns on or off; a child with its own opacity keys gets one `hold` key per frame of
its own value × shown. The document's keys stay as they are. A swap set with no children sends nothing extra.

Operations (`rostrum2d/ops_swap.py`):
- `swap.show` (target: a swap set; `t`, and `layer` = a child id or `index` counted from 0): a hold key on `show`.
  A layer that is not a child is refused, naming the children.
- `blink.add` (target: a swap set; `open`, `closed`, optional `half`, `start`, `end`, `every` = mean gap in s (3.5),
  `vary` 0..1 (0.3), `seed` (0), `frames` = frames closed (2)): hold keys on `show`. With `half`, it shows one frame
  either side of closed. It only adds keys: a time that already has one (or a key moved away from it) stays. The same
  seed gives the same blinks.
- `lipsync.apply` / `lipsync(..., slot=<swap set>)`: when the target is a swap set and the mouth shapes are its
  children, the slot's `show` is keyed (one key per change of mouth) instead of each layer's opacity (LIPSYNC.md).
- Script: `slot = group("mouth", swap=True)`, children inside `with slot:`, then `slot.show({0: "open", 1.2: "closed"})`
  (a child, its id or its place; hold keys), or `slot.key("show", {t: n}, ease="hold")`.
- MCP: `inspect_swaps {time}` lists each set's children (place, id, name) and the one showing then. No rendering.

## Long IK chains (engine, `engine/render/src/rig/fabrik.rs`; P16, native since H18)

An `ik` with `chain` > 2 (field "Bones in chain", 2..32, not animatable) reaches with the lower bone and its parents,
`chain` bones in all: a spine, a tail, an arm with a hand bone. `chain` = 2 is the two-bone solve above. The scene
check refuses a `chain` the rig cannot give (fewer bones from the lower one up).

- **Solve.** In step 2 with the two-bone chains, in order of the chain's top bone's depth, each on the pose the chains
  above it left (a tail hanging from a leg that two-bone IK moves starts where the leg put it). FABRIK on the posed
  joints (each bone's pivot, then the last tip): at most 24 passes, ending early when the tip is within 0.01 px; an
  unreachable target points the chain straight at it. Each bone's world turn is blended with the pose by `mix`
  (shortest angle) and applied top first.
- **Fields.** `targetX`/`targetY`, `mix`, `mode`, `pin` mean what they mean for two bones. `bend`: a joint that is
  straight (under 2 degrees) at that frame is pushed 2 % of the bone above it sideways this way before solving (a
  straight chain has no way to fold otherwise); a bent chain keeps the way it bends.
- **Agents' eyes.** The engine's `bones` answer reports every chain in `iks` (target, gap, and its `bones`, top
  first), so `look_rig` and `inspect_rig_motion` cover long chains as they do two-bone ones.

## Poses (Python, `rostrum2d/rig/poses.py`, P16)

A rig holds a `poses` list (`pose` items: `id`, `name`, `note`, and `values` = `{item id: {field: value}}`). A pose
holds the bones' `rotation`, `scale`, `moveX`, `moveY`, the iks' `targetX`, `targetY`, `mix`, and each swap set's
`show` (§ Swap sets) inside the rig.

- `pose.save` (target: rig; `id`/`name`, `t`, `parts` = only these bone / ik / swap ids, empty = all): the values at `t`.
- `pose.apply` (target: rig; `pose`, `t`, `with` + `mix` = blend with a second pose, `amount` = part of the way from
  what is at `t` now, `ease`): keys every field of the pose at `t`. Numbers blend linearly; a swap choice jumps at the
  half (`mix` ≥ 0.5 takes the second pose's; `amount` < 0.5 keeps the current one) and is keyed `hold`. A bone deleted
  since the save is skipped. One operation = one undo step; it only puts keys.
- `pose.remove`; `pose.set` (rename, note).

## Bones from part names, joints, K and pins (Python, `rostrum2d/rig/guess.py`, `joints.py`, `bodynames.py`; H32)

- `rig.make` on **one plain group** (a PSD's parts) turns that group into the rig: its layers go straight into the rig,
  which takes the group's name (any other selection is wrapped as before).
- `rig.guess_bones` (target: a rig with no bones; `ik` default on): reads the parts' names (`bodynames.part`: torso /
  body, hip, neck, head, upper arm, forearm, hand, thigh, shin, foot, with L / R or left / right; face words → head) and
  proposes a skeleton from their rest boxes: a root "body" bone from the hip to the neck, a head bone, and per limb a
  bone per part from the shoulder or hip out (a joint is halfway between the two parts' long axes, nearest each other).
  An IK chain on each limb of two or more parts (its bend follows the drawn bend, else outwards). Every part is bound
  rigid to its bone; face parts to the head; others to the nearest bone. Refused, saying why, on a rig with bones or with
  fewer than two body-named parts.
- `rig.move_joint` (target: bone; `x`, `y` rig px, `end` pivot / tip): fixes a joint at rest. The parent's tip and
  bones starting at the same joint follow; the bone's own tip stays.
- `rig.key` (target: rig; `t`): K on a rig keys every bone's turn, scale and move and every IK chain's target and amount.
- `ik.pin` (target: ik; `t`, `on`): a hold key on `pin` (right-click a chain's end › Pin on the canvas).
- `group.make` inside a rig (Make swap set on mouth drawings after the bones exist): the drawings' binds go and the new
  group is bound to the bone most of them followed.
- On the screen (`screen2d/rig_view.py`, `rig_drag.py`, `qml/BoneOverlay.qml`): the posed bones and joints come from the
  engine's `bones` and `place` answers (the canvas's own engine, `frames.ask`), so the overlay is the pose the export draws.

## Drawing bones by hand and Mirror pose (Python, `rostrum2d/rig/draw.py`, `mirror.py`; screen `screen2d/bone_tool.py`; H33)

- `bone.draw` (target: one rig; `x`, `y` = the joint, `tipX`, `tipY` = where the bone ends, rig px at rest; `parent`,
  `attach`): one bone. It hangs from the bone that **ends** at that joint (within 2 px: a chain), else beside a bone that
  **starts** there (a branch, same parent), else it is a root; `parent` given wins. A tip on the joint is refused. With
  `attach` (default on) every part of the rig with no bind yet whose middle the bone runs through (its centre within half
  the part's shorter side of the bone, at rest) is bound rigid to it: an arm's bone takes the arm, a head's the eyes and
  mouths. The first bone through a part keeps it; Attach to bone moves it. New bones are named "Bone 1", "Bone 2" …
- **The Bone tool (J)**, only while a rig is in hand: press at a joint and drag to the tip, or click joint after joint
  (each bone one `bone.draw` = one undo step; the next starts at its tip). A press within 8 screen px of a joint the
  rig shows starts there (posed joints are found where they show, used where they are at rest). Esc ends the chain;
  Esc again goes back to Move. Steps: `bonedrag x0 y0 x1 y1`, `boneclick x y`, `bonehover x y`, `boneend`.
- `pose.mirror` (target: rig; `t`, `how` = `left_to_right` (default) / `right_to_left` / `swap`): keys one side from the
  other at `t`. Sides are read from names (`bodynames` words: L / R, left / right, camelCase); a bone with no side in its
  name takes its bound parts' side ("Bone 4" bound to "upper arm L"). Two items pair when their names match without the
  side words. Turn and Move X change sign; Scale, Move Y, IK amount and a swap set's drawing are copied; an IK target
  keeps its offset from its own chain's rest tip, mirrored sideways. `swap` exchanges the sides and turns the middle
  bones the other way (the whole pose seen in a mirror). One call = one undo step; it only puts keys. Refused, saying
  why, on a rig with no left / right pairs. On screen: the context bar's **Mirror pose ▾** (Left side onto the right ·
  Right side onto the left · Swap left and right), only on a rig that has pairs.
