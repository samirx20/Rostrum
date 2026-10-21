# Character rigging and lip sync

How to make a figure move from a few joints instead of redrawing every pose, and how to make a mouth follow a voice.
This guide is about the tools; what you build, and how it moves, is yours. Design and exact maths: `apps/2d/RIG.md`;
lip sync: `apps/2d/LIPSYNC.md`.

## The parts

```
rig (a layer, like a group; its box is the space everything inside is placed in, in px)
 ├ layers  ─ the pictures (shapes, paths, images, drawings), placed by you at rest
 ├ bones   ─ joints: a pivot, a rest direction and length, and a pose (turn, scale, move)
 ├ iks     ─ "reach this point with this foot / hand"
 └ binds   ─ "this picture follows that bone"
```

All positions are px from the rig box's top-left. Angles are degrees, clockwise on screen: 0 = right, 90 = down.
The engine poses the bones and moves the pictures on every frame, so the canvas, the look tools and the export all
show the same thing.

## 1. Build the skeleton

1. `layer.add type=rig id=puppet` (w, h = the box), then your pictures into it: `layer.add target=puppet type=shape ...`.
   Place each picture where it sits at rest.
2. Bones, root first. `bone.add target=puppet id=hip x=300 y=400 angle=90 length=0` makes a root. A child with
   `parent=hip` and no x / y starts at the parent's tip, pointing the same way, so a leg is just
   `bone.add id=thigh parent=hip length=180`, `bone.add id=shin parent=thigh length=170`.
   Fix a bone's rest place later with `bone.set` (x, y, angle, length). That is the *rest pose*: pivot on the
   real joint of the picture (the knee, the shoulder), not the middle of the part.
3. Look: `look_rig` (at a time) draws each bone's pivot and tip over the frame and gives them in comp px. Check the
   pivots sit on the joints.

## 2. Bind pictures to bones

- **Rigid:** `bind.add target=puppet layer=head bone=neck`. The picture moves, turns and scales with the bone,
  from where you placed it. A layer has at most one bind. Its own keys still work on top.
- **Bend:** a leg or arm drawn as one picture that must bend at the knee or elbow:
  `bind.add layer=leg bone=thigh bone2=shin`. `bone2` has to be a child of `bone`. The picture is drawn through a mesh
  that follows both bones. `soft` (px) is how wide the blend around the joint is: 0 is a hard crease, a few dozen
  px a soft fold. `grid` is the mesh detail; raise it for a big picture with fine lines.
- Unbind with `bind.remove`. Deleting or moving a layer out of its rig takes its bind away too.

## 3. Pose with keys (FK)

Bone fields that move: `rotation` (turn from rest, adds to the parent's turn), `scale`, `moveX`, `moveY`. Animate them
like any layer field: `key.add target=thigh prop=rotation t=0.5 v=25`, `value.set` while a person drags. A root
bone's `moveX/moveY` move the whole figure. Rest fields (x, y, angle, length) are not animatable: they describe the
skeleton, not a moment.

In a script:

```python
with rig("puppet", w=600, h=800):
    hip   = bone("hip", x=300, y=400, angle=90, length=0)
    thigh = bone("thigh", parent=hip, length=180)
    shin  = bone("shin", parent=thigh, length=170)
    thigh.key("rotation", {0: -20, 0.5: 25, 1: -20}, ease="smooth")
    leg = shape("leg", w=60, h=350, x=300, y=580)
    bind(layer=leg, bone=thigh, bone2=shin)
```

A re-run merges key by key and field by field: a key a person moved stays (the reply names what was held back).

## 4. IK legs and arms

An IK chain makes the lower bone's tip reach a point; the engine finds the two turns for you.

- `ik.add target=puppet bone=shin` (the **lower** bone; its parent is the upper bone). The target (`targetX`,
  `targetY`) starts at the shin's tip, so nothing jumps.
- Move the foot by keying `targetX` / `targetY`. A target too far to reach: the leg straightens toward it.
- `bend` picks the way the knee folds (`clockwise` / `counterclockwise`). Flip it if the knee points the wrong way.
- Check with `look_rig`: each ik reports its target and `gap`, how far the tip misses it (0 = reached).

### Pin feet in a walk

A planted foot must not slide. Key `pin` with a hold: 1 at the contact, 0 at the lift:
`foot.key("pin", {0: 1, 0.4: 0, 0.5: 1}, ease="hold")`. While pin is on, the target stays where it was when the pin
turned on, whatever the body or the target keys do; so move the body (root `moveX`) and the foot stays on the floor.
Key the target through the lift and swing, and the pin catches it when it lands.

### FK / IK switch

`mode` is `ik` or `fk` per chain. In `fk` the chain follows the bones' own `rotation`, and the target fields are not
shown. To blend over time keep `mode=ik` and key `mix` (1 = the IK pose, 0 = the FK pose): an arm that swings free,
then grabs a handle. Key `mix` over a few frames, not one.

## Seeing a rig

- `look_rig time=…` (or `frame=`): the frame with every skeleton drawn over it: each bone a yellow line from pivot to tip, a
  white dot at the pivot, each IK target a red cross (green square while pinned). It also returns the posed bones in comp px.
- `inspect_rig_motion start end`: per IK chain, sampled every frame: the tip's path, the largest gap to its target, and for
  each pinned span how far the tip moved (over 0.5 px = a sliding foot). Facts only.
- `look_frame`, `look_sheet`, `look_motion` as always. A rig's `x`, `y`, `scale` and so on animate like any layer's.

## Cut-out characters

A cut-out figure is a rig whose layers are separate pictures (shapes, paths, images, drawings), one per moving part, each
with a rigid bind (or a bend bind at a fold). Bring the parts in with `import-and-export` (PSD layers come in as image layers,
SVG as paths), put them in a `rig`, then add bones at the joints.

## Poses

Not yet: named poses, pose libraries, mirror pose, copy a pose between frames. A pose today is the keys on the bones' `rotation`
/ `scale` / `moveX` / `moveY` and the IK `targetX` / `targetY` / `pin` / `mix`. To reuse one, key the same values again at
another time (a loop in the script).

## Lip sync

A mouth drawn in a few shapes (one layer per shape, X A B C D E F G H; any subset works, the nearest drawn shape stands in
for a missing one) follows a voice clip. The clip is heard once, the result is stored, and the mouth layers get ordinary
`opacity` keys with `hold` ease: 1 while their shape shows, 0 otherwise. You can move or change any of them by hand.

Hear it first, changing nothing: `inspect_lipsync source=<wav> text="the words said" at=0.5 shapes={"X": "mouth_X", ...}`.
It lists every phone, word and mouth cue in composition seconds, and with `shapes` which layer shows when. Timing tools:
`lead_frames` (shapes start before the sound; default 1), `min_frames` (shorter shapes give their time away; default 1),
`rest_gap` (a silence longer than this closes the mouth; default 0.25 s), `tail` (how long a sound lasts; default 0.08 s).

Apply it in a script (the mouth layers must be made earlier in the same script; a re-run keeps a person's edited keys):

```python
with rig("puppet", w=1920, h=1080):
    rest = path("mouth_X", d="M 0 0 L 40 0")
    wide = path("mouth_D", d=polygon(6, 24))
    said = lipsync("take.wav", at=0.5, text="Every city keeps one hour.", shapes={"X": rest, "D": wide}, lead_frames=1)
```

Or as an operation: `lipsync.apply` with `target` = the rig or group, `source`, `at`, `text`, `shapeX` … `shapeH`, `leadFrames`.
It only adds keys; to redo a mouth, `key.clear` its opacity first. Words the dictionary lacks need
`pronounce={"rostrum": "R AA1 S T R AH0 M"}`. Check with `look_frame` on the mouth at a few word starts, then listen to a render.
The first run on a clip loads a speech model (a GPU job, a few seconds); after that it reads the cache.

Not yet: lip sync from a RostrumSound voice line or a shared marker as `at` (today `source` is a WAV and `at` is seconds),
languages other than English with words.

## Tips

- Bones are cheap: add a short bone for a wrist or a spine, rather than bending a picture too far.
- Keep pictures one piece per moving part; split where a hard edge turns (hand, forearm, upper arm), bend where
  skin folds (use a bend bind).
- Removing a bone moves its children up to its parent and deletes its binds and IK chains.
- Frames from a rig are checked like any others: render stills at the extreme poses and look before you key the in-betweens.
