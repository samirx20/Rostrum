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
3. Look: `look_frame` (`what: "rig"`) (at a time) draws each bone's pivot and tip over the frame and gives them in comp px. Check the
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

Bone fields that move: `rotation` (turn from rest, adds to the parent's turn), `scale`, `moveX`, `moveY`. **Which way
it turns:** positive `rotation` turns a bone clockwise on screen. So an arm hanging down on the right of the screen swings
up and away from the body with negative values, one on the left with positive values (a limb tells you: `arm.out` is the
sign that swings it away from the body, so `arm.upper.key("rotation", {1: arm.out * 100})` raises either arm). Animate them
like any layer field: `key.add target=thigh prop=rotation t=0.5 v=25`; a person's pose drag on the canvas keys the same way at the playhead (`key.add` on a bone's `rotation`, or an IK chain's `targetX` / `targetY`). A root
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

`layer("leg")` gives back an item made earlier in the script by its id; `limb(...)` (below) builds a whole arm or leg in one call.

A re-run merges key by key and field by field: a key a person moved stays (the reply names what was held back).

## 4. IK legs and arms

An IK chain makes the lower bone's tip reach a point; the engine finds the two turns for you.

- `ik.add target=puppet bone=shin` (the **lower** bone; its parent is the upper bone). The target (`targetX`,
  `targetY`) starts at the shin's tip, so nothing jumps.
- Move the foot by keying `targetX` / `targetY`. A target too far to reach: the leg straightens toward it.
- `bend` picks the way the knee folds (`clockwise` / `counterclockwise`). Flip it if the knee points the wrong way.
- Check with `look_frame` (`what: "rig"`): each ik reports its target and `gap`, how far the tip misses it (0 = reached).

### Pin feet in a walk

A planted foot must not slide. Key `pin` with a hold: 1 at the contact, 0 at the lift:
`foot.key("pin", {0: 1, 0.4: 0, 0.5: 1}, ease="hold")`. While pin is on, the target stays where it was when the pin
turned on, whatever the body or the target keys do; so move the body (root `moveX`) and the foot stays on the floor.
Key the target through the lift and swing, and the pin catches it when it lands.

### FK / IK switch

`mode` is `ik` or `fk` per chain. In `fk` the chain follows the bones' own `rotation`, and the target fields are not
shown. To blend over time keep `mode=ik` and key `mix` (1 = the IK pose, 0 = the FK pose): an arm that swings free,
then grabs a handle. Key `mix` over a few frames, not one.

## Limbs, walks and idles in a script

These script calls build the usual parts in one line each and write the motion as **ordinary keys**: everything they
make is bones, IK chains, shapes, binds and keys that you edit, retime or delete like your own. They choose no look:
sizes, colours and timing are yours.

- **`limb(id, x=, y=, angle=90, lengths=(upper, lower, end), widths=, parent=, kind="arm" | "leg")`** makes three
  bones from the joint at (x, y) along `angle` (`<id>_upper`, `<id>_lower`, `<id>_end`: the hand or foot; give two
  lengths for none), and plain shapes bound to them. `pieces="bend"` (the default) is one tapered piece bent across the
  elbow or knee by a bend bind (`soft` = how wide the fold is); `"parts"` is two tapered pieces, each rigid, meeting at
  the joint; `"none"` makes bones only, for your own pictures (bind them with `bind`). A leg gets an IK chain (`<id>_ik`), an
  arm only with `ik=True`. `bend` is the way the joint folds: `"left"`, `"right"`, `"up"`, `"down"` (the side of the screen
  it points to), `"out"` / `"in"` (away from / toward the body: the parent bone's joint) or `clockwise` /
  `counterclockwise`; an arm's default is `"out"`, a leg's `"right"`. A foot points along `end_angle` (0 = right,
  180 = left). It returns the limb: `arm.upper`, `arm.lower`, `arm.end`, `arm.ik`, `arm.parts` (its shapes),
  `arm.out` (see "Which way it turns" above), `arm.reach({t: (x, y)})` keys its IK target, `arm.pose({t: turn})` keys
  its swing, `arm.set(fill="#f2b23c")` sets a field on every part.
  - **Thickness.** `widths=(upper, forearm or calf, hand or foot)` in px. Leave it out and the limb is sized to its body
    at the end of the script: the upper part 0.26 × the width of the biggest shape bound to the bone it hangs from (or
    the nearest bone above with one; a leg 0.3 ×; legs on a bare hip use the body the arms found), the forearm or calf
    0.85 × that, the hand 1.05 × (a foot 0.8 ×). A 250 px wide body gets 65 px arms. Nothing bound: 0.4 × the upper
    length. Arms under about a fifth of the body's width read as noodles in a small still: `look_frame` with `what: "review"` (and `run_script`'s notes) name a character whose arms or legs are under 0.7 × that default width, with the numbers.
  - **Hands.** `hand="mitten"` (the default) is an oval palm `widths[2]` wide and at least 1.25 × that long with a thumb
    toward the body, one outlined path (`<id>_hand`) you can edit or swap like any layer; `hand="ball"` is a plain circle
    (a robot's or puppet's hand). A hand of your own: bind it to `arm.end` and hide the made one.
  - **Colour.** `color=` (and `end_color=` for the hand or foot). Without one, the parts take the fill of the biggest
    plain-coloured layer bound to the bone the limb hangs from (the body), worked out at the end of the script, so bind
    the body before or after: either works. Nothing bound there: light grey.
  - **Reading in a small still.** Two even tubes of one colour don't read as bent when shrunk, and a forearm in front
    of a body of the same colour disappears. So by default a limb **tapers** (`widths[0]` at the shoulder or hip, a
    little thinner at the elbow or knee, swelling back to `widths[1]` along the forearm or calf, then thinner by `taper`
    (default 0.2) at the wrist or ankle; `taper=0` is even), has a **joint shape** at the elbow or knee (`joint="round"`: a circle
    under the limb that rounds the outside of the bend; `"ball"`: on top, a visible ball joint for a robot or puppet;
    `"none"`), `joint_size` times the joint's width, and an **outline** (`outline=True`: each part's fill, darker;
    a colour; `False`: none) `outline_width` px wide (default a tenth of `widths[0]`, at least 2). Give the upper part
    and the forearm different widths (`widths=(44, 34, 60)`) and the bend shows in the silhouette alone. Check the
    pose in `look_frame` at the size the video will be watched; if an elbow still hides, bend it further or turn
    the outline colour up.
  - **Rest pose.** An arm without IK rests with its elbow bent `relax` degrees (default 35; a leg without IK 10) toward
    `bend`, the upper bone turned back half that much so the hand hangs under the shoulder. `relax=0` is dead straight.
  - **A living arm from upper keys alone** (`natural=True`, the default, for limbs without IK). Key only
    `arm.upper`'s `rotation` (or `arm.pose`) and, at the end of the script, the lower bone gets: the relaxed bend while
    the arm hangs or swings up to 75°; past that it turns into a bend the way the arm swings (a raised arm's
    forearm keeps going up) at 1.5 × `relax`, back to the relaxed bend under 55° (an elbow is never straight in a
    held pose); that bend arrives a beat late and swings past a little (a spring); and where you did not run `follow()`
    on that arm, a lighter follow-through of the forearm and hand. Keys you put on `arm.lower` add to this bend (0 = the
    natural bend, 30 = 30° more). `natural=False` keys it raw. `look_frame` with `what: "review"` names an arm whose elbow stays bent under
    25° for 4 s or more ("holds its arms nearly straight"): a straight arm reads as a stick in a small still.
- **`walk(legs=[a, b], body=hip, arms=[a, b], head=, start=, end=, step=0.5, stride=, lift=, bounce=, travel=True,
  facing="right")`** keys a walk: each foot's IK target planted on the ground for half the cycle and lifted on an arc for
  the other half (the foot kept flat against the shin's turn, its toe tipping in the swing by `toe` degrees), the body's
  bounce (lowest just after each contact) and forward `lean`, the arms swinging against the legs (`swing`, `elbow`
  degrees), the head steadied against the lean. `step` is seconds per step, `stride` px per step. With `travel` the body
  moves on `stride` each step and a planted foot stays put on the floor; with `travel=False` it walks on the spot (the
  feet slide back under it: for a background that moves instead). `stride=0` steps in place. It blends in over half a
  step, and after `end` settles to standing over half a step. It points the knees the way it walks.
- **`idle(chest, head=, arms=, legs=, start=, end=, breath=3.5, amount=1, seed=0)`** adds breathing and weight shift on
  top of what the bones do: the chest bone's scale rising with each breath (a quicker in, a slower out), a slow sway, the
  head drifting and kept level against the sway, the shoulders lifting. Each breath is a little longer or shorter than
  the last (`seed` changes the pattern), so a hold never freezes. `amount` scales it all. **With `legs=[left, right]`**
  (two leg limbs) the hip also slides slowly from foot to foot (`shift` px, default 3.5 % of the leg), tips a little and
  sinks, so with IK feet planted the knees bend in turn; an FK leg bends its knee as the weight leaves it.
  `weight=False` leaves that out. Legs drawn as plain shapes bound to the hip can't bend: make them with `limb(…, kind="leg")`.
- **`pose({limb or bone: value, …}, at=, take=0.5, anticipate=0.12, overshoot=0.1, settle=0.35, stagger=0.04)`** moves
  several bones into a key pose together, landing at `at`: each starts from where it is `take` s before, first pulls
  back by `anticipate` of the move, arrives swung past by `overshoot` of it and settles `settle` s later; each next entry
  lands `stagger` s after the one before (overlap). A value is a turn (a limb's upper bone, a bone's `rotation`), a
  dict of fields for a bone (`{"rotation": 8, "moveY": -20}`), or for a limb `{"upper": a, "lower": b, "end": c}`.
  `anticipate=0, overshoot=0` is a plain ease. Write poses in time order: each starts from what the one before left.
- **`step(legs=[a, b], by=px, at=, take=, lead=, lift=, dip=)`** moves a figure that faces the camera to a new spot in
  side-steps: the foot on the side it moves steps out first (`lead` to choose), the other follows to its place beside
  it, as many steps as the legs need, with the body carried over them and dipping at each step. `by` is px (+ right,
  - left); it returns the time it ends, so chain the next move from it. Seen from the side, use `walk`. **Crouch, sit
  back, rise on the toes:** move the hip, not the legs: `pose({hip: {"moveY": 40}}, at=t)`; IK feet stay planted and
  the knees bend. An IK leg's foot stays flat on the floor however the body moves (unless you key its `end` bone).
- **`follow(bone, start=, end=, lag=0.12, overshoot=0.4, amount=1)`** is `rig.follow` in a script (see Staging below).
  `walk` and `idle` run it on the arms' upper bones by default (`follow_through=False` leaves it out), so forearms and
  hands trail.
- **`blink(eyes, open="eyes_open", closed="eyes_shut", half=, every=3.5, vary=0.3, seed=0, frames=2)`** is `blink.add` in a
  script: hold keys on the swap set's `show`, never over a key that is there.
- **`layer("id")`** gives back an item made earlier in the same script (a layer, a group, a bone, an IK chain), to key it
  or hand it to `lipsync(shapes=…)`, `bind(layer=…)` and the calls above.

Key poses across a whole shot with a few `pose` calls, an `idle` over the holds between them, and `follow` on a gesture:

```python
pose({armR: armR.out * 105, armL: armL.out * 15, neck: 6}, at=4.0)            # a wave up
pose({armR: armR.out * 80}, at=4.5, take=0.25, anticipate=0, overshoot=0)      # the wave's beats: plain keys work too
pose({armR: 0, armL: 0, neck: 0}, at=7.0, take=0.7)                             # back to rest
idle(chest, head=neck, arms=[armL, armR], legs=[legL, legR], start=7.2, end=12)
```

Walks and idles only put keys inside their time range and blend into what the bones do before and after, so layer a
gesture on top (key `armR.upper` after the walk call) or hand-key the stretch around it. A re-run rewrites their range.
Check with `look_frame` (`what: "rig"`) at a contact and a passing time, and `look_motion` (`what: "rig"`). A walk is
drawn from the side; for a figure facing the camera use `stride=0` (a step in place) and `swing=0`, or key the legs by hand.

```python
with rig("kid", w=1920, h=1080):
    hip = bone("hip", x=500, y=600, angle=-90, length=0)
    chest = bone("chest", parent=hip, length=200); neck = bone("neck", parent=chest, length=40)
    legB = limb("legB", parent=hip, x=500, y=600, lengths=(170, 160, 60), kind="leg")
    armF = limb("armF", parent=chest, x=500, y=420, lengths=(120, 110, 20))
    ...                                                   # the other leg and arm, the torso and head bound to chest / neck
    walk(legs=[legF, legB], arms=[armB, armF], body=hip, head=neck, start=0.3, end=4.3, step=0.5, stride=150)
    idle(chest, head=neck, arms=[armF, armB], start=4.6)
```

## Seeing a rig

- `look_frame (what "rig") time=…` (or `frame=`): the frame with every skeleton drawn over it: each bone a yellow line from pivot to tip, a
  white dot at the pivot, each IK target a red cross (green square while pinned). It also returns the posed bones in comp px.
- `look_motion (what "rig") start end`: per IK chain, sampled every frame: the tip's path, the largest gap to its target, and for
  each pinned span how far the tip moved (over 0.5 px = a sliding foot). Facts only.
- `look_frame`, `look_frame` (`what: "sheet"`), `look_motion` as always. A rig's `x`, `y`, `scale` and so on animate like any layer's.

## Cut-out characters

A cut-out figure is a rig whose layers are separate pictures (shapes, paths, images, drawings), one per moving part, each
with a rigid bind (or a bend bind at a fold). Bring the parts in with `import-and-export` (PSD layers come in as image layers,
SVG as paths), put them in a `rig`, then add bones at the joints.

## Poses

A pose library keeps named poses on the rig, so a person or an agent can reuse a pose instead of keying it again.

- **Save.** Pose the rig at some time (keys or still values), then `pose.save target=puppet id=wave_up t=1.2`. With
  `parts=[...]` it saves only those bones, IK chains and swap sets: a hand shape, a face, one arm.
- **Apply.** `pose.apply target=puppet pose=wave_up t=2` keys every field the pose holds at that time (one undo step).
  `amount=0.5` goes half way from what is there; `with=other mix=0.3` keys a blend of two poses (a swap set's drawing
  jumps at the half, never blends).
- **Ways to use it:** block a shot with key poses first, then key the in-betweens; keep a library per character
  (`item.rename target=wave_up name="Wave up"` renames; `pose.remove` deletes); make a variation by blending two poses a little instead of
  posing a third by hand.
- **Mirror.** `pose.mirror target=puppet t=1.2 how=left_to_right` keys the right side of the rig from its left side at that time (`right_to_left` the other way; `swap` makes the whole pose as seen in a mirror). Sides are read from names (`arm L`, `hand R`, `left`, `right`); a rig with no sided names is refused with the names to give. On the screen it is the **Mirror pose** menu at the top of the settings panel with the rig picked (left to right, right to left, swap); it shows only when the rig has left and right names. One undo step; like Apply it only puts keys at that time.
- Not yet: copying poses between rigs.

## Long chains: spines, tails, arms with hands

`ik.add target=puppet bone=hand chain=3` reaches with the hand and its two parents (forearm, upper arm). Any number of
bones from the lower one up: a tail of 6, a spine of 4. Keys on `targetX` / `targetY`, `mix` and `pin` work as for a
leg; `bend` says which way a straight chain starts to curl. The turns are worked out per frame in Python and drawn by
the engine (RIG.md › Long IK chains), so the canvas and the export show the same.

- Fade `mix` from 0 to 1 to lift an arm from its own (FK) swing into a reach, and back down.
- A long chain spreads the bend over all its joints. For a joint that should stay stiff, shorten the chain or key that
  bone yourself.
- Check the tip with `look_frame` / `look_frame` (`what: "sheet"`) at the extremes. `look_frame` (`what: "rig"`) draws the bones; its IK crosses are
  two-bone chains only for now.

## Lip sync

A mouth drawn in a few shapes (one layer per shape, X A B C D E F G H; any subset works, the nearest drawn shape stands in
for a missing one) follows a voice clip. The clip is heard once, the result is stored, and the mouth layers get ordinary
`opacity` keys with `hold` ease: 1 while their shape shows, 0 otherwise. You can move or change any of them by hand.

**The source.** A Sound voice line of the project: `"voice:<line id>"` (`"voice:<song>/<line id>"` when two songs share
the id; Sound's `inspect_item` lists the lines). It hears the line's made take and uses its words as `text` unless you
give one, so changing the words in Sound never leaves a stale path in your script (re-run the script after Sound's
`render_voice` makes the new take). A take not made yet is refused, naming the line. Or any WAV file (a recording).
`at` is still the comp seconds where the line starts: give the same time the line has in Sound.

**Order.** Make the composition first (`comp(...)` in a script, or `comp.add`): hearing and applying both read its
frame rate, and are refused with "no composition yet" before it exists.

Hear it first, changing nothing: `inspect_sounds (what "lipsync") source="voice:line_1" at=3 shapes={"X": "mouth_X", ...}`.
It lists every phone, word and mouth cue in composition seconds, and with `shapes` which layer shows when. Timing tools:
`lead_frames` (shapes start before the sound; default 1), `min_frames` (shorter shapes give their time away; default 1),
`rest_gap` (a silence longer than this closes the mouth; default 0.25 s), `tail` (how long a sound lasts; default 0.08 s).

Apply it in a script (the mouth layers must be made earlier in the same script; a re-run keeps a person's edited keys):

```python
with rig("puppet", w=1920, h=1080):
    rest = path("mouth_X", d="M 0 0 L 40 0", x=960, y=540)
    wide = path("mouth_D", d=polygon(6, 24), x=960, y=540)
    said = lipsync("voice:line_1", at=0.5, shapes={"X": rest, "D": wide}, lead_frames=1)    # or "take.wav", text="…"
```

Or as an operation: `lipsync.apply` with `target` = the rig or group, `source`, `at`, `text`, `shapeX` … `shapeH`, `leadFrames`.
It only adds keys; to redo a mouth, `key.clear` its opacity first. Words the dictionary lacks are refused by name;
give their sound in ARPAbet, in the script as `lipsync(..., pronounce={"rostrum": "R AA1 S T R AH0 M"})` or as the
operation's `pronounce` (the refusal suggests one for a word like "clockmaker's"). Check with `look_frame` on the mouth at a few word starts, then listen to a render.
The first run on a clip loads a speech model (a GPU job, a few seconds, longer on a busy computer); after that it reads the cache. On the screen the Lip sync sheet shows its progress (step 1 to 3 of 3, a moving bar) and the window stays free.

Not yet: a shared marker as `at` (today `at` is seconds), languages other than English with words.

## Swap sets: one drawing at a time

A swap set is a slot on a character that shows one of several drawings: mouth shapes, hands, eyes, a blink. It is a group
with **One at a time** on (the field `swap`: in a script `with group("mouth", swap=True):`, as an operation
`group.set {swap: true}`); its children are the drawings, in order, and **Shows** (`show`) says which one (0 is the first).

- **Draw the set.** One layer per drawing, all placed where they should sit, as children of the group. Keep the same
  registration (the same pivot and size) so a swap does not make the part jump. A child may have its own animation
  (opacity fades, moves); it plays only while it is the one showing.
- **Key a choice.** `slot.show({0: "open", 1.2: "closed", 1.3: "open"})` in a script: each child is named by its id
  (the text you gave it when you made it), or its place (0 is the first). As an operation, `swap.show` with `t` and `layer`
  (or `index`) as an operation. Each is a jump: it holds until the next key. No ease is needed or has any effect.
  `look_frame (what "swaps") time=1.25` says which child shows then; `look_frame` shows it.
- **Blink.** In a script, `blink(eyes, open="eyes_open", closed="eyes_shut")`; as an operation, `blink.add` on the eyes'
  slot (`{"op": "blink.add", "target": ["eyes"], "args": {"open": "eyes_open", "closed": "eyes_shut"}}`). Both take `open`,
  `closed` and optionally `half` (a half-closed drawing for the frame before and after). `every` is the mean gap in seconds,
  `vary` how uneven it is, `frames` how long the eyes stay closed, `start` / `end` the stretch. A `seed` makes the same
  blinks every run; change it for others. It never moves or replaces a key that is there, so keep a blink you like and
  key the rest by hand. Look at a few blink frames.
- **Lip sync into a slot.** Put the mouth drawings in a swap set and give `lipsync(..., slot=mouth)` (or the operation
  `lipsync.apply` on the swap set) the shapes as before (`shapes={"X": mX, …}` takes the layers or their ids; a later
  `mouth.show({24.6: "mouth_smile"})` names a child by id). The slot's `show` is keyed, one key per change of mouth, in
  place of an opacity key per layer. A person can move any of those keys on the timeline.

## Tips

- Bones are cheap: add a short bone for a wrist or a spine, rather than bending a picture too far.
- Keep pictures one piece per moving part; split where a hard edge turns (hand, forearm, upper arm), bend where
  skin folds (use a bend bind).
- Removing a bone moves its children up to its parent and deletes its binds and IK chains.
- Frames from a rig are checked like any others: render stills at the extreme poses and look before you key the in-betweens.

## Staging a character: framing, pose, arcs

Technique, not a recipe. Where a figure feels stiff, the cause is usually one of these.

- **Frame the part the shot is about.** A figure small in a wide frame cannot act. `frame.fit to=items ids=[head_layer] at=t pad=0.2` frames any layer inside a rig where it is *posed* at that time (the engine's place for it), so a face fills the shot (add `keep=[body]` to keep the body whole in it); key a second fit at a later time on the whole body to pull back. A rig's parts work as ids like any layer.
- **Shot sizes and head room.** A *wide* shot shows the whole figure and its place (feet included): it says where and how big. A *medium* shot cuts at the waist or thighs: it says who and what they are doing, with hands in view. A *close-up* shows the head and shoulders, or just the face: it says what they feel, and nothing else in the picture competes. Head room is the space above the head: a little (a few percent of the height) reads as a framed person; none reads as a crop; a lot reads as small or alone. A crop reads as deliberate when it falls at a joint or a natural line (a medium shot at the waist, a close-up through the shoulders), is the same in the shots around it, and nothing the story needs is cut (a hand holding the thing the scene is about). It reads as an accident when it falls through a joint (an ankle, a wrist, the knees), cuts a prop the figure holds or looks at, or differs by a few pixels from a size you meant to hold. `frame.fit to=items ids=[head] keep=[body]` fits the head and keeps the body whole too (the wide-ish shot with the face as large as it can be); without `keep`, a fit on the head alone crops the body on purpose.
- **Check the edges.** `look_frame` says in its reply when a layer, group or rig is cut by the frame edge (which, which edge, how much of it is outside, e.g. "robot (rig) cut at the bottom edge, up to 17 % of it outside"), and `look_frame what=empty` gives the stretches over time. Layers that span the picture (a backdrop, a floor strip) are not named; a rig is named even when a close-up shows only part of it, so a name there is a fact to confirm ("yes, I meant that crop"), not an error. It checks boxes, so a pose that swings a limb out of the picture shows only in the picture itself.
- **One pose per beat.** Save the pose of each beat (`pose.save`), key them on the beat times (`pose.apply`), then add the in-betweens. A pose reads from its silhouette: if the outline alone says what the figure is doing, the pose is working. Arms straight out from the shoulders and legs side by side read as a puppet; turn the shoulders and hips against each other, tilt the head a few degrees, and let one arm and one leg bend more than the other.
- **Bend by default.** A chain whose bones lie in one line is straight, and an IK chain asked for a target at full reach is straight too. Rest the bones with a slight bend (a forearm 10-20 degrees off its upper arm), keep IK targets a little inside the chain's reach, and pick the side the joint folds to with the IK's `bend`.
- **Arcs.** Hands, heads and tails travel on curves, not lines. A swing on a bone's `rotation` moves its tip on an arc by itself; for an IK target, key it at both ends and at a middle time with a sideways offset. `inspect_rig_motion` returns the tip's path so you can check the curve.
- **Overlap and follow-through.** `rig.follow target=upper_arm start=0 end=1 lag=0.12 overshoot=0.4`: the bones below the target trail behind its turn, swing a little past and settle, each step down the chain a bit later. It is baked as ordinary `rotation` keys (linear between dense samples, thinned to what the curve needs) on those bones, plus the settle after `end`, so edit or delete them like any keys; run it again to re-bake the range. A bigger `lag` is looser (hair, a tail), a small one a stiff arm; `amount` below 1 shows only part of it. The target bone itself is not changed.
- **Shot changes on one character.** One framing for a whole piece flattens it, however well the figure moves. Change
  the shot on the beats: a cut is `frame().cut(at=t, to="items", items=["head"], pad=0.2)` (or `frame.cut` as an operation),
  an instant jump to a new framing, best on a change of action or a line of dialogue; a push-in is `f.fit(["head"], at=t2,
  ease="easeInOut")` after a fit on the whole body at `t1` (the frame travels between the two times); a pull-out is the
  same the other way. Cut or push between shot sizes that differ clearly (wide to medium, medium to close-up); a
  change of a few percent reads as a wobble. Keep the eyes in about the same part of the frame across a cut, and the figure
  facing the same way, so the viewer does not have to search. Frame a walk wide enough for the stride, or let the frame
  travel with it (`f.fit` on the figure at the walk's start and end times).
- **Acting over a shot.** A figure that only gestures with its arms while its feet stay put reads as standing still.
  Give each beat of the brief its own key pose with a clearly different silhouette (weight on the other leg, a step
  toward what it reacts to, a crouch before a jump, the body turned), roughly every two to four seconds, and let the
  holds between them breathe with `idle`. Move the legs whenever the body's weight moves: a step toward, a step back
  in surprise, a shift before a line (make the legs with `limb(…, kind="leg")`: shapes bound to the hip can't step). Check with a contact sheet across the whole piece: if two stills a few seconds
  apart look alike, a beat is missing there.
- **A lively face.** Change the eyes and mouth with the beats, not just the blink: a swap set per feature
  (`eyes_open`, `eyes_wide`, `eyes_happy` …) keyed with `eyes.show({t: "eyes_wide"})` at each reaction, a few frames
  *before* the body moves (thought leads action); `blink` over the rest, and a blink on a head turn. Lip sync from the
  voice is one call once the line is made in Sound: `lipsync("voice:<line id>", at=<the line's start>, slot=mouth,
  shapes={...})`; keys you add to the same slot (a smile after the line) sit between its keys.
- **Holds.** Let a pose rest for a few frames (a `hold` ease, or the same value at two times) before the next move; constant motion reads as drifting.
- **Easing on IK.** Keys on an IK target (`targetX`, `targetY`, `mix`) take an ease like any key (`key.add ... ease=easeOut`): the hand leaves its place quickly and settles.
