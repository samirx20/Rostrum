# The Rostrum3D window

One window, five areas. The viewport is in the middle and gets all the room the controls don't need. Nothing else
sits on top of it.

## The top bar, left to right

| Piece | What it does |
|---|---|
| **≡** | The File menu: New, Open, Open recent, Duplicate, Save a version, Show folder, Start screen, Export… (Ctrl+E) |
| **Rostrum3D**, then the project's name | Click the name to rename the project |
| **› Hero 01 ▾** | The shot this window shows. Click for the list of shots: pick one to see its settings (camera, length, size), or **New shot** |
| **Saved · 4 changes** | A scene in a project folder saves after every change. Click the count for History (Ctrl+H) |
| **Build · Animate · Render** | The pages (Ctrl+1, Ctrl+2, Ctrl+3). It is the same scene, camera and selection on every page. Animate gives the keys more rows |
| **↶ ↷** | Undo and redo (Ctrl+Z, Ctrl+Shift+Z) |
| **Search or run a command** | Ctrl+K: every action and setting by name |
| **View: Shot camera** | Which camera the viewport looks through: the shot camera, a free camera, or through the selected light. \` switches between the shot and the free camera. Orbiting in the shot camera turns it into **Free camera** (the shot's own camera stays where it is) |
| **Look: Quick · Final** | Quick is the live view. Final draws the render's own picture in place (Shift+F) |
| **Materials** | The project's materials. Pick one to edit it in the settings panel, or make a **New material** |
| **Render** | One final picture of the playhead's frame through the shot camera (F12). Esc cancels it |
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
- **Shapes** (R): Box, Sphere, Cylinder, Torus, Plane, Disc.
- **Lights** (L): Softbox, Round softbox, Strip, Bulb, Sun, Sky.
- **Camera** (C): Camera, Camera rig.

Each pick adds the thing as one undo step and selects it. It goes into the selected group, or the group that holds the
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

An item's rows come from its own settings:

- The thing's **own group** is always open: a shape's size, a light's brightness, a camera's lens.
- Any other group with a changed value is open too.
- The rest sit as **one row of names** ("+ Rotation · + Scale · + Display · + Aim"). Click a name to open that group.

The diamond at a row's right end keys that setting at the playhead.

## The bottom panel: the scene list and its keys

- **Left:** the scene as a tree. A group's items sit indented under it, and the arrow folds them. Each row shows its
  material's name, dimmed; click that name to edit the material. Click a row to select the item.
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
- **Export** (≡ › Export…, or Ctrl+E) opens in the settings panel's place. Pick this frame or the whole shot, as PNG,
  EXR or both. It renders through the same path as the Render button and agents' renders, so the file matches what you
  see in Final.
