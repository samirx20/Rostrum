# The Rostrum3D window

One window, five areas. The viewport is in the middle and gets all the room the controls don't need. Nothing else
sits on top of it.

## The top bar, left to right

| Piece | What it does |
|---|---|
| **≡** | The File menu: New, Open, Open recent, Duplicate, Save a version, Show folder, Start screen, Export… (Ctrl+E: the render sheet) |
| **Rostrum3D**, then the project's name | Click the name to rename the project |
| **› Hero 01 ▾** | The shot this window shows. Click for the list of shots: pick one to see its settings (camera, length, size), or **New shot** |
| **Saved · 4 changes** | A scene in a project folder saves after every change. Click the count for History (Ctrl+H) |
| **Build · Animate · Render** | The pages (Ctrl+1, Ctrl+2, Ctrl+3). It is the same scene, camera and selection on every page. Animate gives the keys more rows |
| **↶ ↷** | Undo and redo (Ctrl+Z, Ctrl+Shift+Z) |
| **Search or run a command** | Ctrl+K: every action and setting by name |
| **Shot camera** | Which camera the viewport looks through: the shot camera, a free camera, or through the selected light |
| **Look: Quick · Final** | Quick is the live view. Final draws the render's own picture in place. Shown once the viewport offers Final |
| **Materials** | The project's materials. Pick one to edit it in the settings panel, or make a **New material** |
| **Render** | Opens the render sheet (F12) in the settings panel's place: this frame or the shot, quality, size, what file, and how long it will take, measured. See [Rendering](rendering.md) |
| **?** | Guides (F1), keys (Ctrl+/), Connect an AI agent, About |

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

The panel shows what is selected: an item, a material, a shot or a key. Its rows come from the item's own settings:

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
- **Export** (≡ › Export…, or Ctrl+E) opens the render sheet, the same as Render and F12 (see [Rendering](rendering.md)).
  It renders through the same path as agents' renders, so the file matches what you see in Final.
