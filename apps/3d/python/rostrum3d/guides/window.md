# The Rostrum3D window

One window, five areas. The viewport is in the middle and gets all the room the controls don't need. Nothing else
sits on top of it.

## The top bar, left to right

| Piece | What it does |
|---|---|
| **The 3D mark ▾** | The File menu: New, Open, Open recent, Duplicate, Save a version, Show folder, Start screen, Export… (Ctrl+E: the render sheet) |
| **The project's name** | Click it to rename the project. A scene in a project folder saves after every change; an amber dot on the name means it is not being saved (the sample), red that saving failed (its hover says why) |
| **› Hero 01 ▾** | The shot this window shows. Click for the list of shots (the one shown is ticked): pick one and the window shows it (its time, its frame size, its camera in the viewport). While something is selected, **Frame the selection** moves the shown shot's camera so the selection sits in the middle of the picture and fills it with a margin: the camera keeps the way it looks and its lens (aimed at a point, the point moves with it; aimed at an item, it only goes nearer or farther, so it keeps looking at that item); one undo step, and the viewport then looks through it. In the free camera the list ends with **New shot from this view**: a camera where you are looking from and a shot through it, named "Shot 3" (the first shot's size, frame rate and length), one undo step; the window then shows it through its camera. Through the shot camera it ends with **New shot** instead (same camera). The shot's own settings: with nothing selected, click a line under **Shot** in the settings panel |
| **Make this the shot** | Right after the shot's name, only while you look through the free camera (or a light): the shown shot's camera moves to this view, one undo step (Ctrl+Alt+0). Rest the pointer on it first: the viewport shows the shot's frame, exactly the picture it will take. Then the viewport looks through the shot camera again. A camera that moves gets a key at the playhead; an aimed camera keeps aiming, at the middle of this view. In a window narrower than 1400 px it reads **Make shot** |
| **Build · Animate · Render** | The pages (Alt+1, Alt+2, Alt+3). It is the same scene, camera and selection on every page. Animate gives the keys more rows. Render shows the shots and the render queue at the bottom and the shot's render settings on the right ([Rendering](rendering.md), "The Render page and its queue") |
| **Undo, Redo, History** | Undo and redo (Ctrl+Z, Ctrl+Shift+Z); the clock opens History (Ctrl+H) |
| **Search** | Ctrl+K: every action and setting by name |
| **Shot camera · Quick ▾** | How the viewport shows the scene, in one menu. **Camera**: the shot camera, a free camera, or through the selected light (and **Make this the shot** while the view isn't the shot's). \` switches between the shot and the free camera. Turning the view in the shot camera turns it into **Free camera** (the shot's own camera stays where it is). **Look**: Quick is the live view; Final draws the render's own picture in place (Shift+F). In a narrow window it reads **Shot · Quick** |
| **Render ▾** | **Render** (F12) makes the final picture of this frame at once: the time so far against the time it will take shows in its place, × cancels, the picture shows when done with Show in folder. **▾** opens the render sheet (Ctrl+E) in the settings panel's place: the shot, other qualities, size, what file. Not on the Render page, whose settings panel has its own Render. See [Rendering](rendering.md) |
| **?** | Guides (F1), keys (Ctrl+/), Connect an AI agent, About |
| **– ▢ ✕** | Minimise, maximise and close the window. Drag the bar's empty parts to move the window; double-click them to maximise |

## The viewport (middle)

- Through the shot camera, the shot's frame sits in the middle with a thin edge. The scene just outside it is shown
  too, dimmed, so you see what is in the picture and what is just out of it. (Dim outside, in the Scene panel, turns
  the dimming off.)
- **Moving around works the same in every tool.** Right-drag turns the view (a right click, without dragging, opens the
  menu). A left drag on empty space turns it too where the tool gives the left drag no other job (Select, the clay
  brushes off the clay, Pose off the clay); while Draw, Spin, Paint or Edit mesh's box take the left drag, it never
  turns. Middle-drag also turns, Shift+drag pans, the wheel zooms. On a touchpad, two fingers turn the view and a pinch
  zooms. While you turn the pointer shows four arrows, while you pan a closed hand. Turning the view while looking
  through the shot camera switches to the free camera; the shot's own camera never moves (Make this the shot moves it,
  on purpose). A click selects what is there; a click on empty space selects nothing. Double-click goes back to the
  shot's view.
- **Right-click** an item (here or in the scene list): the same actions as the settings panel's top and Ctrl+K, only what
  applies, six at most, each with its key: Edit mesh (Enter), Combine (two solids), Copy material (Ctrl+Alt+C) / Paste
  material (Ctrl+Alt+V) on shapes, Look through and Pick what it lights (lights), Focus on a point (a camera with depth of
  field), Send to 2D (a shot), Lip sync… (a mouth group: a group whose children are mouth shapes named like `mouth_rest`,
  `mouth_closed`, `mouth_wide`; it opens a sheet in the settings panel: click a voice line from RostrumSound, check the
  mesh each shape shows, Apply: one undo step, keys on the timeline), **Make copies ›** (a shape, group, import or clay),
  **Scatter '<it>' on '<surface>'** (right-click a surface while something else was selected) and **Change near ›** (a
  copies item), see *Copies and scatter* below, then Duplicate (Ctrl+D) and Delete (Delete). An item
  outside the selection is selected alone first. Right-click empty space (nothing there): Make this the shot (Ctrl+Alt+0),
  Back to the shot's view (`) and New shot from this view, while you look through the free camera; Frame the selection
  while something is selected.

### The gizmo

The selected item shows its handles: **arrows** move it along X (red), Y (green) and Z (blue), the **square** in the
middle moves it across the view, the **rings** turn it, and the small **cubes** scale it. A selected bone (Animate
page) shows only rings, on its head: a drag keys its Turn at the playhead (see Bones below).

| Key | Does |
|---|---|
| V | Select: all the handles (and out of Paint or Clay) |
| W · E · S | Only move · only turn · only scale |
| ← → ↑ ↓ | Nudge the selection 1 cm along X (← →) or up and down (↑ ↓); Shift 10 cm, Alt 1 mm. One undo step a press |
| D (hold) | The arrows move the **pivot** (the point it turns and scales around), not the item |
| K | Keys what the gizmo moved, at the playhead (Position when nothing moved yet) |
| Ctrl (while dragging) | No snapping |
| Esc (while dragging) | Cancels the drag: the item goes back where it was, nothing is recorded |

- The handle under the pointer lights up, and the pointer shows which way a press drags: a two-headed arrow along an
  arrow, a cube or a ring, four ways on the middle square, a cross while D is held.
- Each drag is one undo step. While you drag, a small box beside the pointer reads the move ("X 0.150 m", "Turn
  15.0°", "Scale ×1.25"); the settings panel shows the new numbers when you let go.
- Moves snap to the ground's 0 and to other items' places, turns to every 15°, scale to ×½, ×1 and ×2 (within 6 px,
  as in 2D).
- The label at the top left says what the drag is doing ("X 0.150 m · ball", "Turn 15.0°").
- An animated setting gets its key at the playhead as you drag.
- Agents do the same with the same operations: `value.set` and `key.add` on `x y z`, `rx ry rz`, `sx sy sz` and the
  pivot `px py pz`.
- **Visible** has a key mark too: key it to show or hide an item at a moment. It switches at each
  key and holds until the next (lip sync shows its mouth shapes this way). Agents: `key.add` `visible` with `v` 1 or 0.

## The tool rail (left edge)

Icons only. Hover one to see its name. A small corner mark means it opens a list beside the rail.

- **Select**: click a thing in the viewport or in the scene list.
- **Clay** (Q): make clay and sculpt it. The settings panel shows **Make** (Draw: drag an outline and it puffs into
  clay, on a clay it joins; Spin: drag half a profile beside the vertical line; Lump: a click drops a ball of clay;
  Turn into clay, with an exact part or import selected) and, with a clay selected, **Brush** (Add, Carve, Smooth, Pull,
  Flatten, Crease, and Mask on its own row), Size and Strength, the **Steps** list (an eye hides a step, double-click
  names it, a click shows its settings), then **More** (closed at first: Falloff, Spacing, Front faces only, Mirror). A drag on the clay sculpts (Ctrl: the
  opposite, Shift: Smooth; a pen's pressure sizes each touch), one undo step per stroke; with a brush chosen, a drag on empty space turns
  the view (with Draw or Spin a left drag always draws); F held and the pointer moved left or right sizes the brush (its size shows beside the ring). Q again, V or Esc goes back to Select, and so does picking a shape from
  Shapes (the next click places it). The guide `sculpting` has it all.
- **Shapes** (R): Box, Sphere, Cylinder, Cone, Torus, Capsule, Plane, Disc. Pick one, then click in the viewport
  where it goes: it sits on the surface under the pointer (the plinth's top, the side of a box, the ground), standing
  along that surface, sized to what you clicked: a fifth of it (a 10 cm box on a 50 cm plinth), 10 cm on the floor or
  in an empty scene. The pointer is a cross while a shape waits; Esc or a right-click lets go of it.
- **Type & logo** (T): 3D text, SVG logo, 2D drawing. Pick one, then click where it goes: it stands upright (never
  flat on the floor) with its front turned to the shot camera, its base on the top you clicked, or just in front of the
  side you clicked; its size is a fifth of what you clicked. **3D text**: a cursor shows where it landed; type the
  words and they change in the viewport as you type; Enter or Esc ends. The whole typing is one undo step; ending with
  nothing typed keeps the word "Text". **SVG logo** asks for the .svg file first. **2D drawing** lists the 2D items in
  this project, then the picked one's path layers; it stays linked, so a change in Rostrum2D shows here.
- **Lights** (L): Soft light, Round soft light, Strip, Bulb, Spot, Sun, Sky (a soft light is what photographers call a softbox).
- **Camera** (C): Camera; then the rigs, which put the camera on a rig in one step, starting exactly where it
  was (the selected camera, else the shot camera; absent while it already rides one): **Orbit** and **Turntable** wait
  for a click on what to circle (a turntable also turns once round over the shot); **Crane**, **Dolly** and
  **Handheld** start at once and run the way the camera looks. The new rig is selected: its Distance, Angle, Lift …
  are in the settings panel (guides/camera-rigs.md).

- **Paint** (B), at the bottom while one mesh or clay is selected: paint on it (colour, roughness, relief, metal, glow). The
  settings panel becomes Brush and Paint layers; a drag on it paints, one undo step per stroke; B or Esc leaves.
  The guide `painting` has it all.
- **Pose** (Shift+P), on the Build and Animate pages while one clay is selected: bend the clay by dragging its parts. The
  first time (or after the shape changed) it finds the joints from the shape, one undo step ("Finding joints…" shows
  meanwhile). While Pose is on, the clay's bones are thin lines with a small dot on each joint, posed at the playhead;
  the gizmo hides. Rest the pointer on the clay: the bones a drag there would bend light up in blue.
  - **Drag a part** (a hand, the head, a tail tip): the chain from it back towards the body bends to follow the pointer;
    a chip beside the pointer names the part and its biggest bend ("forearm.R · 64°"). Letting go is one undo step: the
    Turn of every bone that moved is keyed at the playhead. **Esc** during the drag puts everything back, with nothing
    in the history.
  - **Click a spot** (no drag): a **hold**, an orange ring; that part stays where it is while you drag others (a foot
    on the ground), and the body bends only between the nearest hold and the part you drag. Click a ring to let it go,
    drag a ring to move it, or rest the pointer on it and press **Delete**.
  - **Alt + drag a joint dot**: moves the joint itself (its rest place; it is kept when the joints are found again).
  - A left drag off the clay, or a right drag anywhere, turns the view; a right click opens the menu: **Pose: back to
    rest** (Build page: every bend of the shot gone; Animate page: the rest pose keyed at the playhead), **Find joints
    again**, **Joint names: Plain / Humanoid**.
  - The settings panel shows **Joints** (how many; Find again), **Names** (Plain or Humanoid: Hips, Spine, LeftUpperArm …
    as motion-capture tools name them) and **Holds** (how many; Clear).
  - On the Animate page a drag at another playhead time keys there: the clay's bones show their keys on the timeline as
    a mesh's bones do. Shift+P again, V or Esc goes back to Select. The guide `sculpting` tells what posing does to the clay.

**On the Animate page** the rail is Select, **Poses** (P), **Onion skin** (O), **Bones** (Shift+B, while a mesh is selected), **Pose** (Shift+P, while a clay is selected; above), Lights and Camera:

- **Poses** (P): with items selected (a lid and its buds), type a name and **Save pose**: it keeps their Position, Turn
  and Scale as they are at the playhead. Click a saved pose to key all of that at the playhead (one undo step).
  **Shift+click** a pose for a breakdown: each of its settings keyed halfway between its key before and its key after.
  Each saved pose shows a small picture: what the viewport showed when you saved it (a pose an agent saved has none).
  Hover a pose for what it holds; its × deletes it (the keys it wrote stay).
- **Onion skin** (O turns it on and off): ghosts of the selected item in the viewport, red before, green after, to
  time an arc by eye. Its panel picks the frames: **At the keys** (its previous and next keys) or **2 and 4 frames**
  each way. The quick look only: Final shows no ghosts. It never changes the scene.
- **Bones** (Shift+B; shows while a mesh is selected): a chain of bones the mesh bends with (a strap, a cable, a tail). Click
  points along the mesh, root first: dots and a line show them; **Backspace** or **Delete** takes the last one back. **Enter** makes the
  chain (one undo step), **Esc** or Shift+B again cancels. Each bone is a row under the mesh in the scene list, each inside the one before.
  On this page the selected mesh's bones are drawn over the picture as thin diamonds, posed at the playhead (the
  selected bone in blue). **Click a bone** in the viewport to select it (a click near its line picks the bone, not the
  mesh behind). A selected bone shows **turn rings** on its head: drag one to bend it (Ctrl frees the 15° steps); each
  drag is one undo step and keys the bone's **Turn X / Y / Z** at the playhead, so the mesh bends with it and the bones
  after it, in the viewport and the render alike. You can also type its Turn in the settings panel (the Turn it has plus
  the bend you want). The mesh's **Bend with bones** turns the bending off
  and on. A mesh bends only where it has points along its length: the ready shapes have none along their straight part (a
  capsule's or cylinder's Segments go around it), so make it an editable mesh (Enter) and cut across it with the Knife
  (Shift+K) every few centimetres first.
- The Poses and Onion skin panels open and close on their own: click a rail button to open its panel, again to close it, Esc
  closes the one you are in. Both can be open side by side; leaving the Animate page closes them.

Each shape, light or camera is added as one undo step and selected. It goes into the selected group, or the group that holds the
selected item. The rail only shows tools that work today. Simulation appears when it is built.

## Import

Bring in a model made elsewhere: glTF or GLB, OBJ, FBX, Alembic (its animation plays with the shot) or USD. The file is
used where it is and never changed.

- **The Import list** (Build page, under Type & logo; **Ctrl+I**): **glTF / GLB…**, **OBJ…**, **FBX…**, **Alembic…**,
  **USD…** each open the file window showing only that kind of file. The file you pick lands at once on whatever is in
  the middle of the view (its bottom on the surface there), or on the ground when the middle shows empty floor, or in
  front of the camera when it shows only sky. Last in the list, **Asset library** (below).
- **Drag files from Explorer** onto the viewport: while one hovers, a small ring shows where it will land; let go and it
  lands on the surface under the pointer. Several files dropped together land on the same spot.
- Each import is **one undo step**, arrives **selected**, and the tool is back to Select. It goes into the selected group
  (or the group holding the selected item), else the top of the scene list. Its name is the file's.
- **Sizes**: Rostrum works in metres. A file made in another unit (centimetres, millimetres, inches …) is scaled to
  metres on the way in, so a 20 cm toy is 20 cm here, and the line at the top says so once ("Imported at 1/100: it was
  in centimetres"). Under its settings, **Keep original size** takes the file's own numbers instead (a 20 cm toy then
  stands 20 m tall); it stays there until your next edit and is one undo step. A file made with Z pointing up is stood
  upright.
- **Parts**: the meshes inside the file are listed under the import in the scene list (open it with its arrow). Click a
  part to select it: its settings have its own **Material** (pick or drop one) and **Visible** (hide just that part).
  The import's own Material, when set, goes over the whole file.

## Asset library

Import › **Asset library** opens a sheet in the settings panel's place with the sources of free models: Poly Haven and
ambientCG, both CC0 (free to use, no credit needed). Every source is **off** until you switch it on there; while it is
off nothing is asked of its site, and agents can't switch it on. With a source on: type words in the search field
(Enter) and its models show as tiles; **More** at the end loads the next ones. With two on, the bar at the top picks
whose models show. Click a tile: the model downloads (a bar fills on the tile) into the project folder, under
`assets\<source>\<model>\`, and lands on the surface in the middle of the view, selected, as one undo step. A
model already downloaded is used again at once. The scene must be in a project folder (the sample scene isn't). Esc
or × closes the sheet.

## Copies and scatter

One thing, many times, without making a thousand items (the guide *copies* has the fields and the script). By hand:

- **Twelve buds in a line:** right-click the bud › **Make copies › Line**, type **12** (the Count box is already waiting for
  you), Enter. Right-click › Make copies also has **Grid**, **Circle** and **On a surface…** (then click the surface).
  The new copies item holds the bud and is selected; one undo step.
- **Scatter over a surface:** select the pebble, then right-click the plinth: **Scatter 'Pebble' on 'Plinth'**. By default
  only the copies the shot camera sees are drawn (Only what the camera sees, under the copies' settings); under **Count** a
  grey line says how many: "212 of 400 in Hero 01" (or "400 copies" before the camera has been asked).
- **Drag a number:** drag **Count**, **Space X / Z**, **Radius** or **Keep apart** in the settings panel and the copies
  follow the pointer live; letting go is one undo step (Esc puts it back).
- **One copy:** click a copy; the copies item is selected and the line at the top says "Copy 7 of Buds". The arrows move,
  turn and size just that copy; the drop keeps it there (it never moves again when you change the count or the layout; **Release held
  copies** in the right-click menu lets them go back). One undo step.
- **Change near ›** (right-click a copies item): **Scale**, **Turn**, **Push** or **Colour** the copies close to something.
  With another item selected too (Ctrl+click), the change follows that item; alone, a small sphere is added beside the copies
  and selected: move it and the copies near it change. Its settings (Radius, Amount, Falloff) are the effector's row under
  the copies in the scene list; key Amount or Radius for change over time.

## The settings panel (right)

The panel shows what is selected: an item, a material, a shot or a key. With **nothing selected** (Esc, or a click
on empty space; a scene also opens that way) it shows the **Scene**:

- **View:** Exposure, Studio light, Scene lights, Shadows (contact shadows, and their strength), Depth of field (when
  the camera has it) and Dim outside. These are how the viewport looks: never part of the scene, never undone. In
  Final they are absent (Final uses the Render settings).
- **Sky:** **Picture ▾** chooses the photographed sky that lights the scene (a new scene starts on **Studio**; one
  undo step), and **Light** opens the sky light itself (brightness, turn); with no sky, **Sky +** adds one.
- **Shot:** size, frame rate, length and camera. Click any of them for the shot's own settings.

A setting with a small **Final** tag after its name (a panel light's Spread and Lights only, a material's coat colour, sheen, brushing and thin film) shows in the Final look only: the Quick view can't draw it. A material's light under the surface and its colour inside carry the tag too: the Quick view only tints the colour a little, and only Final shows the soft shadows and the glow of thin parts. Hover the tag for that.

An item's rows come from its own settings:

- The thing's **own group** is always open: a shape's size, a light's brightness, a camera's lens.
- Any other group with a changed value is open too.
- The rest sit as **one row of names** ("+ Rotation · + Scale · + Display · + Aim"). Click a name to open that group.

The diamond at a row's right end keys that setting at the playhead.

**Timing** (on the Animate page only, in the row of names, once an item or something inside it has keys): **Smooth**, **On 2s** or **On 3s**.
On 2s holds every value for two frames, the stepped look of hand-drawn animation; the camera, left Smooth, still
glides. A group's Timing steps everything inside it.

**A camera** has a **Lenses ▾** button beside its Focal length: the real lenses 24, 35, 50, 85, 105 and 135 mm (rest the pointer on
one to see it through the camera; any other focal length: type it in Focal length). With **Depth of field** on:
**Focus on a point** (top of the panel), then click in the viewport where it should be sharp: Focus distance becomes how far in front of the
camera that spot is. **Pick** (beside Focus on), then click the item (or Alt+click while focusing on a point): the camera keeps
it sharp as it moves; **Focus on** names it and Focus distance goes (it is worked out every frame). Set Focus on back to
None to type a distance again. Each click is one undo step.

**An item's material** sits under its settings: the **Material** row (click its ball to pick another, or start a new one
from a substance), and under it the material's own settings, including "Used by 3 items" and **Make its own** when the
material is shared. See the guide *materials*.

**Several things selected.** Pick more in the scene list: Ctrl+click adds one (or takes it out), Shift+click picks the
run from the first one. The panel then shows the settings they share, and a change goes to all of them. With two or
more solids (shapes or combines in the same group) the top of the panel offers **Combine: Union · Subtract ·
Intersect**; the first one you picked is the base. Rest the pointer on one for a moment and the viewport shows the
result; move off and it goes back. Click to make it (one undo step); see the guide *modelling*. Only what applies is
shown, so with one thing selected there is no Combine.

### Follow and stick (an item's settings)

- **Follow** (a bud riding on an opening lid): in the item's **Follow** group, pick the item to ride on with the
  target (click it, then the lid in the viewport or the scene list). From then on it moves and turns with the lid,
  from wherever it stands. **Amount** is 1 while it rides; key it **0** at the moment it should be let go and it stays
  exactly where it is then, never jumping back. Key 0 first and 1 later to pick it up at a time. **Follow the pose**
  (riding a posed clay): it rides the bone nearest it instead, so it bends with the pose there; a shape clicked onto a
  clay has it on already.
- **Stick to**: pick a mesh (a floor, a table, a ball) and the item stands on its surface straight below as it moves;
  its **Y** is then its height above that surface. Off the surface's edge it keeps its own Y.
- **A hinge**: hold **D** and drag the gizmo to the lid's back edge (its pivot), then key **Turn X**: the lid opens
  around that edge. A bud following the lid rides the same hinge.

## The bottom panel: the timeline

The same timeline as Rostrum2D's. It is taller on the Animate page.

- **Top row:** ▶ plays (Space), the playhead's time, **⚑ Add marker** (in a project folder: a shared marker at the playhead that
  other apps see too: 2D, Sound, the Editor), then the ruler in seconds with the project's markers as flags. Click or drag the
  ruler to move the playhead; ← → step one frame. Drag a flag to move it, double-click to rename it.
- **Left:** the scene as a tree. A group's items sit indented under it, and the arrow folds them. A **combine** is a row with its own icon and its
  inputs indented under it; in a Subtract the cutters carry a minus sign. Ctrl+click and Shift+click pick several. Each row shows its
  material's name, dimmed; click that name to edit the material. Click a row to select the item. Drop a material ball on a row to give
  that item the material. Right-click a row for its menu.
- **Right, on the same rows:** an animated item's keys as diamonds on a slim bar from its first key to its last.
  - The selected item opens a row for each animated setting, and a second line where two of its animations overlap in time.
  - Click a diamond to pick its key (the settings panel shows the key); Ctrl+click adds one, Shift+click picks the run between,
    and a box dragged on an empty part of a row picks every key it touches. Drag a key to move it, or all picked keys together;
    drag the bar to move all of the item's keys in time. One drag is one undo step. Keys land on whole frames, and on a marker,
    the playhead or another key when they come close (hold Ctrl to move freely); a label shows how far ("+6 f · logo lands").
  - **Stretch keys in time:** pick two or more keys, then **Alt+drag the first or last** of them: the others stretch or squeeze
    around the far end (one undo step; the moved end stays inside the shot). Agents: `key.scale`.
  - **Right-click a key** for the Ease list (Linear, Ease in, Ease out, Smooth, Spring, Jump, Custom): every picked key gets that ease.
  - **Click the stretch between two keys** (the lid's Turn): the settings panel becomes that animation. Its header says what moves
    ("Turn · lid · Turn X"); then From and To, Start, Length, the easing presets **Linear, Smooth, In, Out, Spring, Bounce, Hold**,
    the curve (drag its two handles), and **Reverse** | **Delete**. One click on a preset eases it (one undo step). ‹ or Esc
    goes back to the item.

## Keys

Every key is listed on the Keys sheet (Ctrl+/) and found in Ctrl+K by what it does; nothing on the sheet is dead. The
keys every Rostrum app shares mean the same here as in 2D and Sound: Space plays, Ctrl+← → step a frame, Home / End,
`,` and `.` (here: the previous / next key of the selection, or of everything, or marker), M adds a marker, the arrows
nudge, Tab / Shift+Tab walk the scene list, Enter goes in (Edit mesh on a shape; the first item of a group), Shift+Enter
goes out, Ctrl+A selects all, Ctrl+D duplicates, Delete deletes, Ctrl+Alt+C / Ctrl+Alt+V copy and paste a material,
K keys what the gizmo moved, F9 / Shift+F9 / Ctrl+Shift+F9 / Ctrl+Alt+J ease the picked keys (Smooth, Ease in, Ease out,
Hold), Ctrl+= / Ctrl+- zoom the view, V is Select, B is Paint. 3D's own:

| Key | Does |
|---|---|
| Q | Clay: make clay and sculpt it (Q again: Select) |
| F (held) | Clay: move the pointer left or right to size the brush; let go to keep it |
| R · T · L · C | The Shapes, Type & logo, Lights and Camera lists of the rail |
| Ctrl+I | The Import list of the rail (Build page) |
| P · O · Shift+B | Poses, Onion skin, Bones (Animate page; Shift+B with a mesh selected) |
| Shift+P | Pose: drag the selected clay's parts (Shift+P again: Select) |
| W · E · S | The gizmo's move, turn or scale handles only (V: all) |
| 1 · 2 · 3 | Edit mesh: points, edges, faces |
| Shift+K · Alt+Z | Edit mesh: Knife, X-ray |
| Alt+1 · Alt+2 · Alt+3 | The Build, Animate and Render pages |
| ` | The shot camera's view, or the free camera from it |
| Ctrl+Alt+0 | Make this the shot: the shot's camera to this view |
| Shift+F | Look: Quick or Final |
| F12 | Render: the final picture of this frame (on the Render page: the shown shot's render, next in the queue) |

**Esc steps back one thing per press**, always in this order: an open menu, list, popup or sheet closes first (the
newest one); then a gizmo drag, a pose drag (or a hold or joint being moved), a clay stroke or an outline being drawn (Draw, Spin) still under way is cancelled (the item or the clay goes back, nothing
is recorded); then a running render is cancelled; then a render shown over the viewport is put away; then a shape waiting
for its click is let go; then placing bones, picking a camera's focus or picking what a light lights stops; then the
Knife's line is dropped; then Edit mesh, Paint, the Clay tool or Pose is left; then an animation picked on the timeline goes back to its item;
then several picked keys are let go; then the selection is let go (the Scene panel shows).

## Files

- The mark's menu (top left) and the start screen work the same in every Rostrum app.
- A new scene is "Untitled scene" in your projects folder. It saves after every change, so there is no Save and no
  question when you close.
- **Export** (the mark's menu › Export…, or Ctrl+E) opens the render sheet, the same as the ▾ beside Render (see [Rendering](rendering.md)).
  It renders through the same path as agents' renders, so the file matches what you see in Final.
