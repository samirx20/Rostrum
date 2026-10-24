# The Rostrum3D window

One window, five areas. The viewport is in the middle and gets all the room the controls don't need. Nothing else
sits on top of it.

## The top bar, left to right

| Piece | What it does |
|---|---|
| **≡** | The File menu: New, Open, Open recent, Duplicate, Save a version, Show folder, Start screen, Export… (Ctrl+E: the render sheet) |
| **Rostrum3D**, then the project's name | Click the name to rename the project |
| **› Hero 01 ▾** | The shot this window shows. Click for the list of shots (the one shown is ticked): pick one and the window shows it (its time, its frame size, its camera in the viewport). In the free camera the list ends with **New shot from this view**: a camera where you are looking from and a shot through it, named "Shot 3" (the first shot's size, frame rate and length), one undo step; the window then shows it through its camera. Through the shot camera it ends with **New shot** instead (same camera). The shot's own settings: with nothing selected, click a line under **Shot** in the settings panel |
| **Saved · 4 changes** | A scene in a project folder saves after every change. Click the count for History (Ctrl+H) |
| **Build · Animate · Render** | The pages (Ctrl+1, Ctrl+2, Ctrl+3). It is the same scene, camera and selection on every page. Animate gives the keys more rows |
| **↶ ↷** | Undo and redo (Ctrl+Z, Ctrl+Shift+Z) |
| **Search or run a command** | Ctrl+K: every action and setting by name |
| **View: Shot camera** | Which camera the viewport looks through: the shot camera, a free camera, or through the selected light. \` switches between the shot and the free camera. Orbiting in the shot camera turns it into **Free camera** (the shot's own camera stays where it is) |
| **Look: Quick · Final** | Quick is the live view. Final draws the render's own picture in place (Shift+F) |
| **Materials** | The project's materials, each a rendered ball with how many items use it. Click one to edit it in the settings panel, drag one onto an item to give it that material, or make a **New material** (materials.md) |
| **Render** | Opens the render sheet (F12) in the settings panel's place: this frame or the shot, quality, size, what file, and how long it will take, measured. See [Rendering](rendering.md) |
| **?** | Guides (F1), keys (Ctrl+/), Connect an AI agent, About |

## The viewport (middle)

- Through the shot camera, the shot's frame sits in the middle with a thin edge. The scene just outside it is shown
  too, dimmed, so you see what is in the picture and what is just out of it. (Dim outside, in the Scene panel, turns
  the dimming off.)
- Middle-drag or drag on empty space orbits, Shift+drag pans, the wheel zooms. A click selects what is there; a click
  on empty space selects nothing. Double-click goes back to the shot's view.
- **Right-click** an item (here or in the scene list): Duplicate, Delete, Look through (lights), Copy material /
  Paste material (shapes). Right-click empty space: Frame all, New shot.

### The gizmo

The selected item shows its handles: **arrows** move it along X (red), Y (green) and Z (blue), the **square** in the
middle moves it across the view, the **rings** turn it, and the small **cubes** scale it.

| Key | Does |
|---|---|
| V | All the handles |
| W · E · S | Only move · only turn · only scale |
| D (hold) | The arrows move the **pivot** (the point it turns and scales around), not the item |
| K | Keys what the gizmo moved, at the playhead (Position when nothing moved yet) |
| Ctrl (while dragging) | No snapping |

- Each drag is one undo step, and the settings panel follows as you drag.
- Moves snap to the ground's 0 and to other items' places, turns to every 15°, scale to ×½, ×1 and ×2 (within 6 px,
  as in 2D).
- The label at the top left says what the drag is doing ("X 0.150 m · ball", "Turn 15.0°").
- An animated setting gets its key at the playhead as you drag.
- Agents do the same with the same operations: `value.set` and `key.add` on `x y z`, `rx ry rz`, `sx sy sz` and the
  pivot `px py pz`.

## The tool rail (left edge)

Icons only. Hover one to see its name. A small corner mark means it opens a list beside the rail.

- **Select**: click a thing in the viewport or in the scene list.
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
- **Lights** (L): Softbox, Round softbox, Strip, Bulb, Spot, Sun, Sky.
- **Camera** (C): Camera; then the rigs, which put the camera on a rig in one step, starting exactly where it
  was (the selected camera, else the shot camera; absent while it already rides one): **Orbit** and **Turntable** wait
  for a click on what to circle (a turntable also turns once round over the shot); **Crane**, **Dolly** and
  **Handheld** start at once and run the way the camera looks. The new rig is selected: its Distance, Angle, Lift …
  are in the settings panel (guides/camera-rigs.md).

Each shape, light or camera is added as one undo step and selected. It goes into the selected group, or the group that holds the
selected item. The rail only shows tools that work today. Others (type and logos, editing faces, painting,
simulation, import) appear as they are built.

## The settings panel (right)

The panel shows what is selected: an item, a material, a shot or a key. With **nothing selected** (Esc, or a click
on empty space) it shows the **Scene**:

- **View:** Exposure, Studio light, Scene lights, Shadows (contact shadows, and their strength), Depth of field (when
  the camera has it) and Dim outside. These are how the viewport looks: never part of the scene, never undone. In
  Final they are absent (Final uses the Render settings).
- **Sky:** the scene's sky light (click to edit it), or **Sky +** to add one.
- **Shot:** size, frame rate, length and camera. Click any of them for the shot's own settings.

A setting with a small **Final** tag after its name (a panel light's Spread and Lights only, a material's coat colour, sheen, brushing and thin film) shows in the Final look only: the Quick view can't draw it. Hover the tag for that.

An item's rows come from its own settings:

- The thing's **own group** is always open: a shape's size, a light's brightness, a camera's lens.
- Any other group with a changed value is open too.
- The rest sit as **one row of names** ("+ Rotation · + Scale · + Display · + Aim"). Click a name to open that group.

The diamond at a row's right end keys that setting at the playhead.

**A camera** offers at the top of its panel **Lens ▾**: the real lenses 24, 35, 50, 85, 105 and 135 mm (rest the pointer on
one to see it through the camera; any other focal length: type it in Focal length). With **Depth of field** on, two more:
**Focus on a point**, then click in the viewport where it should be sharp: Focus distance becomes how far in front of the
camera that spot is. **Focus on an item**, then click the item (or Alt+click while focusing on a point): the camera keeps
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

## The bottom panel: the scene list and its keys

- **Left:** the scene as a tree. A group's items sit indented under it, and the arrow folds them. A **combine** is a row with its own icon and its
  inputs indented under it; in a Subtract the cutters carry a minus sign. Ctrl+click and Shift+click pick several. Each row shows its
  material's name, dimmed; click that name to edit the material. Click a row to select the item. Drop a material ball on a row to give
  that item the material.
- **Right, on the same rows:** the item's keys as diamonds.
  - The selected item opens a row for each animated setting.
  - Click a diamond to select its key; drag it to move it (whole frames, one undo step).
  - Click or drag the ruler to move the playhead.
  - Space plays, and ← → step one frame.
- **Add marker** puts a shared marker at the playhead. Other apps see it too (2D, Sound, the Editor).

## Files

- The ≡ menu and the start screen work the same in every Rostrum app.
- A new scene is "Untitled scene" in your projects folder. It saves after every change, so there is no Save and no
  question when you close.
- **Export** (≡ › Export…, or Ctrl+E) opens the render sheet, the same as Render and F12 (see [Rendering](rendering.md)).
  It renders through the same path as agents' renders, so the file matches what you see in Final.
