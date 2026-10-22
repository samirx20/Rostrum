# Drawing

Paint by hand, and draw one picture after another for frame-by-frame animation. Drawing is a **tool** you pick, not a page you go to: the same workspace stays, the right-hand panel shows your brush, and the timeline gives the picture the room.

Paint always belongs to something. Paint on a shape, a text or a picture and the paint becomes part of its look: it stays inside its outline, and it moves, turns, grows and fades with it. A **drawing** is simply paint with no outline around it.

![The Draw tool, with the brush on the right and two drawings with the onion skin on](pictures/draw-tool.png)

## 1. Pick the Draw tool

1. Click **Draw** in the tool strip at the top left of the canvas, or press **B**.
2. What you paint on depends on what is picked:
   - **a shape, a text, a picture or a path**: the paint goes onto it, kept inside its outline. Paint a grain on a card, a texture in letters, shading on a picture. Strokes that go past the edge are simply not shown there.
   - **a drawing**: the paint goes onto the drawing.
   - **nothing**: **your first stroke makes a new drawing** and picks it. It is one step, so **Ctrl+Z** takes back the drawing and the stroke together.
3. **+ Add**, then **Drawing**, also makes a drawing layer and turns the Draw tool on.
4. Press **V** (or **Esc**) to go back to Move.

When Draw is on, the timeline shrinks to its compact height: the top strip, the ruler and only the drawing's own row. The picture gets the room, and Play and the playhead are still there. Click the button at the right end of the top strip to bring all the rows back; the tool remembers which height you last used with it.

## 2. Choose your brush

Every brush setting lives in **one** place, never two.

**The bar at the top-centre of the canvas** holds what you change while painting: the **tip**, **Size**, the
**colour**, **Opacity**, **Eraser** (**E**), **Fill** (**G**, see part 4), **+ Paint layer** and **Painting on**.
**[** and **]** make the brush smaller or bigger. On a narrow window, Opacity, then Eraser, then Fill move under the
bar's own **⋯** button; Size and the colour always stay.

**The right-hand panel, Brush,** holds the rest: how the next stroke is laid.

1. **Hardness**: how crisp or soft its edge is.
2. **Mode**: how the stroke meets what is already there (multiply darkens like a glaze, screen and add light it up).
   It is not shown while the eraser is on: an eraser only takes paint away.
3. Under **Pen**, **Size from pressure** and **Opacity from pressure** say how much a pressure-sensitive pen changes
   the stroke. A mouse has no pressure.
4. **More** opens the rest (spacing, scatter, paper grain, colour drift, wet paint). Only the settings that apply to
   the tip you chose are shown.

Under the brush, the panel shows **Paint on** and the name of what you paint on (part 5).

## 3. Draw a stroke

1. Press and drag on the picture, then let go. That is one stroke.
2. Each stroke is one change, so **Ctrl+Z** takes back the last stroke.

### Pick a colour from the picture

Hold **Alt**. The pointer becomes a picker, and a small round swatch beside it shows the colour of the picture under
it, as you see it on screen (paint, shapes, pictures and all). Click, and that colour becomes the brush colour. Let go
of **Alt** and you are painting again.

### Select strokes, then move, copy, paste or delete them

1. Hold **Ctrl** and drag a loop round the strokes (and fills) you want, or click **Select strokes** in the bar and
   then drag. Anything with most of its length inside the loop is picked, and is outlined.
2. The bar now shows what applies: **Copy**, **Paste**, **Delete** and **Done**. Drag the picked strokes to move them.
   They stay strokes, so they stay sharp.
3. **Ctrl+C** copies them and **Ctrl+V** pastes them a little down and right of the originals, onto the paint layer
   that is highlighted. **Delete** removes them.
4. **Esc**, **Done**, or a press outside the box lets go.

Each of these is one change, so **Ctrl+Z** takes back a move, a paste or a delete. Only paint layers that are not
locked can be picked from.

## 4. Fill a closed shape

1. Draw the lines around an area, closed or nearly closed.
2. Press **G**, or click **Fill** in the bar. The bar now shows the colour, Opacity and **Close gaps**.
3. Click inside the area. It fills with the colour, right up to the lines and a little under them, so no thin light
   edge shows between line and colour.
4. Lines that don't quite meet: pick **Medium** or **Large** under **Close gaps** and click again.
5. A click on a line, or in an area that is open to the edge of the painting, fills nothing and says why at the bottom.
6. The fill finds its edges in **all** the paint layers of the thing, so you can fill on a colour layer under the
   lines of your line layer.
7. Press **G** again (or click **Fill**) to go back to the brush.

A fill is kept as a shape, not as dots of colour, so it stays as sharp as your strokes. Each fill is one change:
**Ctrl+Z** takes it back.

## 5. Paint on: layers and settings of what you paint on

Under the brush, **Paint on Card** (the name of what you paint on) shows:

1. **The paint layers**, the top one first. A thing starts with one, called "Paint". To keep lines above colour, press
   **+ Paint layer** in the bar: your next stroke or fill starts a new layer on top.
   - Click a layer's name to paint on it; it is highlighted.
   - The eye hides or shows it.
   - Drag a name up or down to change the order.
   - Right-click a name and pick **Delete** to remove it and its strokes.
   - **Opacity** and **Blend** under the list belong to the highlighted layer.
2. **Keep inside the outline**: on by default. Turn it off and the paint can spill over the whole box around the
   thing. (A drawing has no outline, so it does not have this switch.)
3. **Draw each frame**: off means the thing has one painting that holds for the whole time. On means each frame can
   have its own drawing, as in the next part. **Alt+N** turns it on by itself when you start a new drawing.
4. **Onion skin**, while Draw each frame is on (part 7).

The same switches are in the thing's settings panel with the Move tool, under its folded **Paint** group.

## 6. Frames: one drawing after another

The drawing's row in the timeline shows its frames as marks on its bar. A drawing starts at a mark and is held until the next one. The number on a mark is the frame where it starts.

1. Move the playhead to where you want the next picture (click the ruler).
2. Click **New drawing**. A blank picture starts there.
3. **New from this** starts the next picture as a copy of the one before. It is there only when there is something to copy.
4. **Previous** and **Next** step between drawings. The **,** and **.** keys do the same.
5. **Hold longer** and **Hold shorter** make the current picture last more or fewer frames. The **=** and **−** keys do the same.
6. **Clear** empties the current picture.
7. These buttons show only when they can apply. For example, there is no **New drawing** where a drawing already starts.

## 7. Onion skin

1. Turn on **Onion skin** under the brush (with Draw each frame on), or press **Alt+O**. With the Move tool it is a
   button above the timeline. The neighbouring drawings show faintly over the picture, so you can see where the last one was. The ones before are tinted red and the ones after are tinted green.
2. Click it again to turn it off. The faint pictures are for you only; they do not appear in an export.

## 8. Play it

Press **Space**. The pictures play in order at the project's speed. **Preview size** makes playback lighter.

## 9. More than one drawing layer

Lines on top, colour below works best with paint layers (part 5). For two separate things you move apart, pick **+ Add**, **Drawing** again for a second layer, then drag its name under the first in the timeline. Both are in the same list, and each keeps its own frames. Strokes go onto the drawing layer that is picked, so click the name of the one you want to paint on.

Next: [the-screen.md](the-screen.md), and [exporting.md](exporting.md) to get a video file out.
