# Posing by dragging

Any clay can bend. You pose it the way you would a real figure: grab a hand and pull it. The app finds the joints
from the shape itself (where limbs meet the body and where they bend), and the chain from the part you drag back to
the body bends to follow, each joint turning as little as it can.

## On the screen

1. Select a clay and click **Pose** on the tool rail (Build or Animate page). The first time, or after the shape
   changed, the joints are found (a second or so); thin bone lines and joint dots show while Pose is on, never
   otherwise.
2. **Hold** what should stay still: click a spot once (an orange ring). Click a ring again, or hover it and press
   **Del**, to let go; drag a ring to move it.
3. **Drag** any part: a hand, the head, a tail tip. The chip by the pointer shows the part and its biggest bend.
   **Esc** while dragging puts everything back as it was.
4. Bent in the wrong place: undo, add a hold nearer to where it should bend, drag again. Holds are how you choose
   where the body bends: it bends only between the nearest hold and the spot you drag.
5. A joint in the wrong place: **Alt+drag** its dot. A joint you placed stays where you put it when the joints are
   found again.

Right-click the clay while Pose is on: **Pose: back to rest**, **Find joints again**, **Joint names: Plain /
Humanoid**. The window guide has every key and pointer of the Pose tool.

## Keys and time

A drag keys the Turn of every joint that moved, at the playhead. On the Build page that is the clay's pose for the
whole shot. On the Animate page, drag at one time, move the playhead, drag again: the timeline's keys, stretches and
easing then move it from one pose to the next (Timing On 2s / 3s steps it like the rest of the shot). **Pose: back to
rest** on the Build page removes every Turn key (back to the resting shape); on the Animate page it keys the resting
pose at the playhead.

## What the joints are

- **body** is the root (the thickest part); **chest** starts where the arms join; **head** sits above a narrowing.
- A limb gets a joint where it meets the body, where it bends most, and a middle one when it is long: **arm /
  forearm / hand**, **leg / shin / foot**; a short limb at the bottom is a **foot**; one pointing up from the top a
  **neck / head**, one pointing back a **tail**; anything else **part3**, **part4** ….
- **.L** is the character's left: the clay's +X side (the character faces +Z, towards the default camera); **.R**
  is −X. A mirrored clay (built with Mirror on, or left–right the same) is read on one side and mirrored, so its
  .L and .R joints are always a matched pair.
- **Humanoid** names (Hips, Spine, Head, LeftUpperArm, LeftLowerArm, LeftHand, LeftUpperLeg, LeftLowerLeg,
  LeftFoot …) are the ones Unity's Humanoid and VRM use, for motion capture and humanoid rigs. Only the names
  change; the bones and their keys stay.

## When the shape changes

The joints are found again from the new shape. Joints a person or agent placed stay where they were put, and every
bend stays: each joint keeps its turn against its resting direction, so a raised arm is still raised. Holds are
spots on the resting clay, so they stay too.

**Sculpting a posed clay** sculpts it as it stands: each brush touch is carried back through the joints to the
resting shape, so the change follows the character into every pose (Mirror works on the resting shape: a change on
one arm shows on both, in every pose).

## For agents

Every step above is an operation (one undo step each); positions are world points unless said otherwise.

```
pose.find_joints(target="c", names="plain")       -> {"joints": [{id, joint, head, tail, parent}, …]} (world)
pose.hold(target="c", bone="foot.L")              -> holds the middle of that joint (off=True lets go)
pose.hold(target="c", spot=[x, y, z], at=0)       -> holds the joint under a world spot on the clay
pose.drag(target="c", part="hand.R", to=[x, y, z], at=1.0)
                                                  -> {"moved": [{id, joint, turn}], "miss": metres, "held": [...]}
pose.drag(target="c", grab=[x, y, z], to=[x, y, z], holds=["foot.L", "foot.R"])
pose.rest(target="c")                             -> every Turn key removed;  pose.rest(target="c", at=2.0) keys rest
pose.move_joint(target="c", joint="forearm.L", to=[x, y, z])   -> placed: kept when the joints are found again
pose.names(target="c", names="humanoid")
```

- **Find, look, then pose.** After `pose.find_joints`, check the reply (or `look_frame`; `look_at` on a pixel names
  the nearest joint, "forearm.R, 3 cm off"): a joint in the wrong place is fixed with `pose.move_joint` before posing.
  `look_shape` measures the clay at rest, whatever its pose; `look_frame highlight="steps:arm"` outlines a step as posed. `cells` (8–128, default 48) samples the shape more finely for thin
  limbs.
- **Grab by name** (`part="hand.R"`, `"RightHand"` or the bone id `c_hand_R`): the grabbed spot is the end of that
  bone. `grab` is a world point on the clay as it stands at `at`.
- **Holds** (`holds`, names or bone ids) replace the clay's own holds for one drag; left out, the clay's holds
  (`pose.hold`) apply. A held joint and every joint that carries it (its parents) never turn, so holding both feet
  keeps the body still and only the arm bends. With no holds the body (root) doesn't turn.
- **miss** above 0 means the spot couldn't reach `to` (the chain is fully stretched): move `to` closer, or release a
  hold so more of the body can bend.
- **Keys.** A drag keys `rx`, `ry`, `rz` of each moved bone at `at`: absolute turns, the bone's rest turn plus the
  bend (the same keys `key.add` writes on any bone; `anim.ease`, poses and the timeline work on them). Bone ids are
  `<clay>_<part>` (`c_arm_L`), so keys survive finding the joints again.
- **Bend with joints** (`clay.set skinned=false`) keeps the clay at rest while its joints and keys stay.
- A clay's joints are its `bones` (nested bone items, as a mesh's chain; guide `agents` › Bones); each bone has
  `joint` (its part name) and `placed`; the clay has `holds` (resting spots in its own space), `jointNames` and
  `jointsKey` (the shape the joints were found for).
