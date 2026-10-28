# Text on a path

Make words run along a line or a curve. The words stay real text: you can still change the font, the size and the words themselves, and the letters follow the path as it changes.

## 1. Make the path

1. Press **P** (the **Pen** tool in the tool rail).
2. Click for a corner, drag for a curve. Click the first point to close the shape, or press **Enter** to leave it open.
3. The path is now a layer in the timeline.

## 2. Make the text and put it on the path

1. Press **T** (the **Text** tool), click on the canvas and type your words.
2. With the text selected, find the **On a path** group in the settings panel.
3. Open **Follows path** and pick your path layer from the list. **None** is the first choice and takes the text off the path again.

The list shows only path layers that sit beside the text: in the same scene, or in the same group. If your path is somewhere else, put the two in the same group first (select both, then **Group**).

**From a script or an agent:** put the text on a path layer with `text.follow` (`path:"<path layer id>"`), or write `text("title", body="Words", pathLayer="trend")` in a script. The text's own `path` field is different: it holds raw path data (`M 0 0 C ...`), never a layer's id, and a layer id written there is refused with this line to write instead.

## 3. Slide it, align it

With the text selected, these show in **On a path** once it follows a path:

- **Start along path**: moves the words along the path, in pixels. A negative number moves them back.
- **Align on path**: **start**, **center** or **end**. Where the words sit on the path before **Start along path** moves them.
- **Off the path**: what happens to letters that do not fit on the path. **hide** leaves them out; **Carry on straight** continues them in a straight line.

These show only while they can be used. If the text follows no path, they are not there.

## 4. Move the path, move the text

The text follows its path as the path is moved, reshaped or drawn on. Edit the path's points as usual and the words follow at once. If you delete the path, the scene says the text has lost its path until you pick another one or set **Follows path** to **None**.

## 5. Animate along the path

1. Click the diamond beside **Start along path** to start animating it.
2. Move the playhead, change the number. A key is added.
3. Set the ease of the keys with the Key block in the settings panel (see [curve-editor.md](curve-editor.md)).

The text slides along the path between the keys.

## Good to know

- Hide the path with its eye in the timeline if you don't want to see the line. The words stay on it.
- Painted, hand-lettered words can bend along a curve too: `paint.letters` with `path` (SVG path data in composition px)
  and `start`. They are brush strokes, not text, and write on with Drawn so far (painted-backgrounds.md › Hand-lettered words).
- A text on a path exports to Lottie as a straight line. The Export panel lists it under "Lottie couldn't carry".
