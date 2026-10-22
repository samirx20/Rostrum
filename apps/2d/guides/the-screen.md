# The screen

A tour of the window, from the top and round the edges. There is one workspace: the picture in the middle, the settings on the right, the timeline along the bottom. There are no pages to switch between.

![The workspace](pictures/workspace.png)

## 1. The top bar

1. **File** at the far left opens the file menu (see [files.md](files.md)). Next to it is the project's name. A small dot after the name means there are changes not saved yet.
2. The line on the right says what you did last, and how many changes you have made since you opened the project. If it is cut short, point at it to read the whole line.
3. The undo and redo arrows come next. They appear only when there is something to undo or redo. **Ctrl+Z** undoes; **Ctrl+Shift+Z** or **Ctrl+Y** redoes.
4. **+ Add** puts something new in the picture: a shape, text, a path, an image, a video, a drawing, a camera or a 3D render. **Import** brings in a file (see [importing.md](importing.md)). The arrow button opens **Export** (see [exporting.md](exporting.md)).
5. The box that says "Search or run a command" is the **command box**. Press **Ctrl+K**, type a few letters of what you want, and pick it from the list. It lists only what you can do right now, with the shortcut beside each, and it acts on everything you have picked.
6. The **?** at the far right opens **Help**, with these guides.
7. When the window is narrow, things give way in a fixed order and never slide under each other: first the line that says what you did last gets shorter, then the project's name, then the search box becomes just its icon.

## 2. The canvas

1. The big rectangle in the middle is your picture, as it will come out. Its size and speed show at the top right of the canvas.
2. The **tool strip** at the top left of the canvas has three tools: **Move** (V), **Pen** (P) and **Draw** (B). Move picks, moves and resizes. Pen draws shapes point by point. Draw paints by hand (see [drawing.md](drawing.md)). The tool you pick changes what the mouse does and what the right-hand panel shows.
3. **Picking.** A click on a thing picks it. It goes to what is painted: the empty part of a drawing, or an empty group, does not catch the click. If the thing is inside a group, the click picks the outermost group (so the whole logo moves); **double-click** goes one level in; **Ctrl+click** picks the piece under the pointer straight away. **Shift+click** adds a thing to what is picked or takes it out. Drag a box on empty canvas to pick everything it touches. **Ctrl+A** picks every layer, and **Esc** lets go of the picking.
4. Drag a picked thing to move it, or drag a small square on its edge to resize it. The box and the picture move together. While you drag, the picture is drawn a little smaller so it keeps up; one full-size picture follows when you let go.
5. **Nudge** with the arrow keys: 1 pixel, or 10 with **Shift**, for every picked layer. Each press is one change.
6. **Copy, cut and paste**: **Ctrl+C** copies the picked layers, **Ctrl+X** cuts them and **Ctrl+V** pastes them, in the same place and in the same project or another one. **Ctrl+D** makes a copy next to the original.
7. With nothing picked, the right-hand panel shows the picture's own settings: **Width**, **Height**, **Frame rate**, **Length** and **Background**.

## 3. Select first, then act

Anything that relates layers to each other starts from what you have picked: you pick the things, then act. The same short list of actions shows up in four places, and only what applies to your picking is ever in it:

1. The **action bar**: a small bar just under the picked layers on the canvas, with the most used: **Group**, **Ungroup**, **Mask with top layer**, **Boolean** (two or more shapes), **Align** and **Distribute** (three or more layers). **⋯** opens the whole list.
2. A **right-click** on the picked layers on the canvas, or on a layer's name in the timeline, opens the whole list.
3. **Ctrl+K**, by name.
4. Shortcuts: **Ctrl+G** group, **Ctrl+Shift+G** ungroup, **Ctrl+D** duplicate, **Ctrl+C** / **Ctrl+X** / **Ctrl+V** copy, cut and paste, **Delete**, **F2** rename, **Ctrl+]** and **Ctrl+[** bring forward and send backward (with **Shift**: to the front, to the back).

The whole list: Group, Ungroup, Clip to a box, Auto layout, Make swap set, Make rig, Mask with top layer (and the other ways a mask can cut), Release mask, Union, Subtract, Intersect, Exclude, Align (left, centre, right, top, middle, bottom), Distribute, Match width, height or size, Copy style and Paste style, Lock, Hide, Duplicate, Delete, the four order moves and Rename. Each is one step, so **Ctrl+Z** takes back the whole thing. Nothing is made empty to be filled afterwards: you do not add an empty group and drag things into it, you pick the things and group them.

## 4. The settings panel

1. The panel on the right shows the settings of what is picked. Its heading is the layer's name, and the line under it says what kind of thing it is. When several things are picked it says how many, and shows what they share: a value that differs says "Mixed", and a change sets it on all of them as one step.
2. A few **essential** settings come first. The rest sit in named groups below them (for text: **Text**, **Font**, **Outline**, **Type** and more). Click a group's name to open it, and again to fold it.
3. **Find a setting** (**Ctrl+F**) finds any setting by a word: pick one from the list and its group opens and it is shown.
4. It shows only the settings that apply. Turn something on and the settings that go with it appear; turn it off and they go away. Nothing sits there greyed out.
5. A diamond at the right of a setting is its key mark (see [first-animation.md](first-animation.md)).
6. With the Draw tool on, the same panel shows the **Brush** instead (see [drawing.md](drawing.md)).

## 5. The timeline is the layers list

1. Along the bottom: a top strip, a ruler, and a row for each layer. The names on the left are your layers, newest on top; the bar beside each name shows when the layer is on screen, with its keys as diamonds.
2. The top strip has the play button, the time, **Preview size** (**Full**, **Half**, **Quarter**), **Add marker**, and **Keys** / **Curves**. **Space** plays and stops.
3. A name's small arrow folds or opens what is inside a layer: a group's layers, its keyed settings, its effects and masks.
4. Click a name to pick the layer. **Ctrl+click** adds a layer to what is picked or takes it out, and **Shift+click** picks every layer from the last one you clicked to this one; every picked row and bar is lit. Double-click a name (or press **F2**) to rename it. A long name is cut short in the list; point at it to read it whole. Drag it up or down to change what sits in front, or onto a group to put it inside. A line shows where it will land.
5. At the right of a name sit a **lock** and an **eye**. They show when you point at the row, and stay visible while they are on. A **locked** layer cannot be picked or moved on the canvas, and everything refuses it until you unlock it. A **hidden** layer is not drawn, in the preview or in an export, and its name and bar fade. Click to switch; it is one step.
6. Drag the middle of a bar to move the layer in time, and an end to trim it. When several layers are picked, dragging one picked bar moves all the picked bars together. Drag a diamond to move a key. They snap to the playhead and to markers. Click a diamond to change how that key eases; **Curves** shows the curves.
7. **The timeline has two heights.** The full height shows every layer. The **compact** height shows only the top strip, the ruler and the picked layer's row, to give the picture the room; the name there is a menu of all your layers. Switch with the button at the right end of the top strip, or drag the timeline's top edge. Each tool remembers its own height: Move and Pen the full one, Draw the compact one, so picking a tool gives you the right amount of picture.

## 6. Markers

1. A marker is a named flag on the ruler for a moment you care about.
2. Click **Add marker** to put one at the playhead.
3. Drag a flag to move it. Double-click it to rename it. Click its **×** to remove it.
4. A layer's bar that you let go of on a marker snaps to it and stays tied to it: when the marker moves, the layer follows. A key snaps to a marker too. Other Rostrum apps can follow the same marker, so a sound can be placed on it.

## 7. Problems

If something in the project is wrong, a button such as **1 problem** appears at the top. Click it for the list. It is not there when everything is fine.

Next: [first-animation.md](first-animation.md), [drawing.md](drawing.md), [files.md](files.md).
