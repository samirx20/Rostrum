# Making your first animation

This page takes you from an empty project to something that moves, and shows you how to take a step back. There is one workspace and no pages to switch between: the picture is in the middle, the settings of what you picked are on the right, and the timeline, which is also the list of your layers, runs along the bottom.

![The workspace](pictures/workspace.png)

## 1. Start a new project

1. Click **≡** at the top left, then **New** (or press Ctrl+N).
2. An empty black picture opens, called "Untitled", with nothing picked. The thin outline with the tab **Frame · 1920 × 1080** is the frame: what the export shows.
3. With nothing picked, the panel on the right shows the scene's own settings, headed **Scene**: **Format** (a list of sizes, such as Wide 16:9), **Size** (W and H), **Frame rate**, **Length** and **Background**. Change them here if you need a different size or length. A click on empty canvas, or **Esc**, brings them back at any time. The frame is picked only when you ask for it (part 2), so a first drag on the empty canvas never moves the shot.

## 2. Add text

1. Making things lives in the **tool rail**, the column of icons at the left of the canvas: **Shapes**, **Pen**, **Text**, **Brush**, **Add from a file…** (pictures, video, files), **Library**. The frame (what the export shows) is picked with **C** or its Frame row.

![The Shapes panel beside the tool rail](pictures/shapes-panel.png)

2. Press **T**, then click on the picture where the words go and type. A row appears in the timeline at the bottom. **Esc**, **Ctrl+Enter** or a click outside the text ends the typing, and the text stays picked, so the panel on the right shows its settings.
3. In the panel, change **Size**, **Weight** and **Colour** (a swatch plus a hex box) in the short list. A new text starts dark on a light spot (a light shape, a picture) and white on a dark one (the empty canvas, a dark shape), judged where you click, so it can be read at once. Change it in the panel.

## 3. Pick, move and change things

1. Click a thing in the picture, or its name in the timeline, to pick it. Small squares appear round it.
2. Drag it to move it. Drag a square on its edge to resize it. With the Select tool on, the arrow keys nudge the picked layers by 1 pixel, **Shift** with an arrow by 10 and **Alt** with an arrow by a tenth of a pixel. Each press is one change you can undo.
3. The panel on the right shows a few essential settings first (for text: the words, size, weight, colour, position, opacity). The rest are in named groups below them, such as **Paragraph**, **Width and slant** (and other font settings) and **Outline**. Click a group's name to open it, and again to fold it. **+ Outline** adds an outline at once (its colour and width show; **−** removes it). **Font** is a list of the fonts you can use, each shown in its own letters: the fonts that come with Rostrum2D first (the same on every computer), then the fonts installed on this computer; type to find one. **Weight** lists the weights the font really has (a variable font takes any weight in its range), and **Italic** appears when the font has one.
4. Not sure where a setting is? Click **Find a setting** at the top of the panel (or press **Ctrl+F**), type a word such as "opacity", and pick the setting from the list. Its group opens and it is shown to you. A word such as "blur" names an effect: it shows a line **Add Blur**, and the effect's settings appear under **Effects** once it is added.
5. A setting appears only when it can be used. Turn something on and the settings that go with it appear; turn it off and they go. Nothing sits there greyed out.
6. To rename a layer, double-click its name in the timeline (or press **F2**) and type.

## 4. The timeline is the layers list

1. The names on the left of the timeline are your layers, newest on top, under the **Frame** row (the box that is exported). Each layer has a bar beside its name, with its name in it: the time the layer shows, from its start to its end. A new layer's bar runs the whole length; its keys (part 5) sit on it as diamonds.
2. Drag the middle of a bar to show the layer later or earlier, or drag an end of the bar to start it later or end it sooner. A bar snaps to the playhead and to markers (see [the-screen.md](the-screen.md)). The **Timing** group of the settings panel has the same **Starts at** and **Ends at** as numbers.
3. The ruler above the bars counts seconds. The blue marker is the **playhead**, the moment you are looking at. Click or drag on the ruler to move it. The time shows beside the play button, for example "1.00 s".

## 5. Make a value move, right where you are

A value moves over time when it has **keys**. A key is a small diamond that remembers the value at one moment. You do not need another page for this: you change the value where it is.

1. Pick your text. Put the playhead at 0 seconds.
2. In the panel, find **Position**. At the right edge of its row is a faint diamond. Click it. It fills in, and a key of X and Y together is saved at 0 seconds.
3. Move the playhead to 1 second.
4. Change **X** or **Y**: type a new number and press Enter, or drag the text in the picture. A second key appears at 1 second by itself. In the timeline, open the layer (the arrow by its name): its row **Position** shows these keys.

![Two keys on the text's bar](pictures/animate-in-place.png)

5. The diamond beside a value tells you its state, and a click does the one thing that fits it:
   - **Faint**: it is not animated yet. Click it to start: a first key at the playhead.
   - **Outlined**: the value is animated, but there is no key at this moment. Click it to add a key here, holding the value it has now (the other keys stay).
   - **Filled**: there is a key at the playhead. Click it to delete just that key; the top bar says so ("Delete Opacity key at 2.00 s") and **Ctrl+Z** brings it back. The setting's other keys stay.
   - To stop animating a setting altogether (every key goes; it keeps the value it has at the playhead), right-click its diamond › **Stop animating**.
6. **See where it goes.** While a layer with position keys is picked, its **motion path** shows on the picture: a thin line through every place it passes, with one dot per frame. Dots close together mean it moves slowly there; far apart, fast. Each position key is a small square on the line:
   - Drag a square to move that key's place. Only that key changes, and the whole drag is one step you can undo. It snaps, like a thing dragged on the picture, to the frame's edges and centre and to other things; hold **Ctrl** or **Alt** to place it freely. A key timed on a marker shows on the path too, at the marker's time, and stays on its marker when you drag it.
   - Click a square to pick that key. Its **handles** appear; drag a handle's round end to bend the line into a curve. The other handle turns with it so the curve stays smooth; hold **Alt** to move one handle alone.
   - The path hides while playing, and for a layer riding a path layer (that path already shows where it goes).
7. The same keys show as diamonds on the layer's bar in the timeline. Drag a diamond to move that key in time. It snaps to the playhead and to markers. Keys too close to tell apart (a frame or two apart on a long, zoomed-out timeline) show as one diamond with a second one peeking out behind it; diamonds never sit on top of each other, even at a bar's very start or end. Click it to pick them all, or zoom the timeline in to see each one.

## 6. Change how it feels

1. Click a diamond on the bar. The **Key** block appears at the top of the settings panel, short so the layer's settings stay in view under it: **Key** with its **Ease** beside it (a button showing the key's ease and its curve: **Smooth**, say), a small curve, and for one key its **Time** and **Value** (in the setting's own unit). A Position key is one key: its Time moves X and Y together. The ease is how the value speeds up and slows down on its way to the next key.
2. Click **Ease** to open the list: **Linear**, **Smooth**, **Ease in**, **Ease out**, **Spring**, **Hold**, each with its curve, the key's own ticked, and **More** for Snappy, Natural, Heavy, Stronger smooth and Bounce. Rest the pointer on one and the canvas plays it, nothing changed; click it and every picked key changes at once, as one step. On a setting's last key there is no move after it, so the ease you pick there is set on the key before it: the move into the last key (the Ease button then shows that move's ease). You can also right-click a diamond for the same list, or press **F9** (Smooth), **Shift+F9** (Ease in), **Ctrl+Shift+F9** (Ease out) or **Ctrl+Alt+J** (Hold).
3. Drag the two small dots on the curve to shape it by hand: the ease becomes **Custom**.
4. **Spring** overshoots and settles. Two sliders appear: **Bounce** (none to a lot) and **Speed** (slow to fast).
5. The bar itself stays plain. A click on a **diamond** picks that key and shows the **Key** block above. A click on the **bar between two keys** picks the whole move from one key to the next and the settings panel turns into a **Move** view instead: **‹** (or **Esc**) goes back to the layer; one row per setting with its start and end value; **Start** and **Length** in seconds; its **Ease** (the same button and list as the Key block's) with the curve under it (Bounce and Speed sliders for a spring); **Reverse** swaps the two values and **Delete** removes the move (undo brings it back). The two views change the same keys; use whichever you reached first.
6. Click **Curves** at the left of the timeline's header row, over the layer names, to see each value's curve between its keys. Click **Keys** to go back to the diamonds.

## 7. Key many layers at once, and retime

1. Pick the layers, put the playhead where the pose should be, and press **K**. Each picked layer gets a key for its position, scale, rotation and opacity, as one step. The message line says what it did ("Keyed 4 settings on 3 layers"). Pressed again where every setting already has a key holding its value, it says so ("Key here would change nothing here") and changes nothing. Typing a value a setting already has says "Nothing changed: it already is that way."
2. To pick several keys: **Ctrl+click** diamonds, **Shift+click** for the run between two, or drag a box over the diamonds, starting on an empty part of a row or in the thin gap between two rows (it can cross several layers; a drag that starts on a bar moves the layer instead).
3. Drag a picked diamond to move them all. Hold **Alt** and drag the first or the last picked diamond to stretch or squeeze them all in time.
4. **Ctrl+C** copies the picked keys. Pick other layers, move the playhead and press **Ctrl+V**: the keys land on the same settings of those layers, starting at the playhead and keeping their spacing. A picked layer that has no such setting (a rectangle has no text Size) gets nothing, and the top bar says which one and why.
5. **,** and **.** jump the playhead to the previous or next thing that happens: a key, a marker, a drawing, or where a layer starts or ends. With layers picked, only theirs.
6. To make layers start one after another, pick them and click **Stagger…** at the top of the settings panel. A small box opens under the button (the picture stays as it is: nothing dims). Set "Each starts [2 f] after the one before" and an **Order** (stack, as picked, left to right, top to bottom, from the centre, random). The bars spread as you change it. Press Enter or click away to keep it (one step; the box closes), or press Esc to take it back. Open Stagger again to change it.

## 8. Play it

1. Press **Space**, or click the play button, to play from the playhead. Press Space again to stop. While it plays, the canvas shows exactly the video (what the frame sees); when it stops, your own view comes back. To see the video alone without playing, press **Shift+C** (look through the frame); press it again, or click the × on its label, to go back.
2. **Preview size** (**Full**, **Half**, **Quarter**) is in the **Fit · 53 % ▾** menu in the top bar. It makes playback lighter on a slow computer. It does not change what you export.

## 9. Do something to several layers at once

Select first, then act. Hold **Shift** and click more things in the picture, or **Ctrl+click** more names in the timeline, or drag a box round them on empty canvas, or press **Ctrl+A** for every layer at the level you are in. The panel then shows the settings they share ("Mixed" where they differ); change one and it changes on all of them, as one step. One box is drawn round everything picked: drag its squares to resize them all together, or just outside a corner to turn them all (one undo step each).

The top of the **settings panel** shows only what applies to them: **Combine** (two or more shapes), **Group**, **Mask**, **Align**, **Distribute** (three or more); **…** (more) holds the rest. Right-click gives the short menu (cut, copy, group, order, hide, lock, rename); everything is also in **Ctrl+K**, and in a few shortcuts (Ctrl+G groups, even one layer, Ctrl+Shift+G ungroups).

![Two layers picked: their actions are the buttons at the top of the settings panel](pictures/settings-actions.png)

## 10. Undo a mistake

1. Press **Ctrl+Z** to take back the last change. **Ctrl+Shift+Z** (or **Ctrl+Y**) brings it back.
2. The undo and redo arrows near the top do the same. They appear only when there is something to undo or redo; undo is always the right-hand one, so clicking it twice takes back two steps. Point at one to read what it would take back.
3. The line next to them says what you did last, and how many changes you have made since you opened the project.

Next: [the-screen.md](the-screen.md) for every part of the window, [drawing.md](drawing.md) to draw by hand, and [exporting.md](exporting.md) to get a video file out.
