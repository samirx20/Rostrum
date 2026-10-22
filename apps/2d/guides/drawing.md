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

With Draw on, the **bar at the top-centre of the canvas** holds the brush controls you change most: the **tip**, **Size**, the **colour**, **Opacity** and **Eraser**. **E** turns the eraser on and off, and **[** and **]** make the brush smaller or bigger.

The right-hand panel is called **Brush** and has every setting. It sets how the next stroke looks.

1. **Colour**: click the swatch or type a colour.
2. **Size**: how wide the stroke is, in pixels.
3. **Tip**: the shape of the brush.
4. **Opacity**: how solid the stroke is.
5. **Hardness**: how crisp or soft its edge is.
6. **Mode**: how the stroke meets what is already there.
7. Under **Pen**, **Size from pressure** and **Opacity from pressure** say how much a pressure-sensitive pen changes the stroke. A mouse has no pressure.
8. **More** opens the rest. Only the settings that apply to the tip you chose are shown.

## 3. Draw a stroke

1. Press and drag on the picture, then let go. That is one stroke.
2. Each stroke is one change, so **Ctrl+Z** takes back the last stroke.

## 4. Paint settings of a painted thing

Once a shape, text or picture has paint, its settings panel (Move tool) gains a folded **Paint** group:

1. **Keep inside the outline**: on by default. Turn it off and the paint can spill over the whole box around the thing.
2. **Draw each frame**: off means the thing has one painting that holds for the whole time. On means each frame can have its own drawing, as in the next part. **Alt+N** turns it on by itself when you start a new drawing.

## 5. Frames: one drawing after another

The drawing's row in the timeline shows its frames as marks on its bar. A drawing starts at a mark and is held until the next one. The number on a mark is the frame where it starts.

1. Move the playhead to where you want the next picture (click the ruler).
2. Click **New drawing**. A blank picture starts there.
3. **New from this** starts the next picture as a copy of the one before. It is there only when there is something to copy.
4. **Previous** and **Next** step between drawings. The **,** and **.** keys do the same.
5. **Hold longer** and **Hold shorter** make the current picture last more or fewer frames. The **=** and **−** keys do the same.
6. **Clear** empties the current picture.
7. These buttons show only when they can apply. For example, there is no **New drawing** where a drawing already starts.

## 6. Onion skin

1. Click **Onion skin** (or press **Alt+O**). The neighbouring drawings show faintly over the picture, so you can see where the last one was. The ones before are tinted red and the ones after are tinted green.
2. Click it again to turn it off. The faint pictures are for you only; they do not appear in an export.

## 7. Play it

Press **Space**. The pictures play in order at the project's speed. **Preview size** makes playback lighter.

## 8. More than one drawing layer

Lines on top, colour below: pick **+ Add**, **Drawing** again for a second layer, then drag its name under the first in the timeline. Both are in the same list, and each keeps its own frames. Strokes go onto the drawing layer that is picked, so click the name of the one you want to paint on.

Next: [the-screen.md](the-screen.md), and [exporting.md](exporting.md) to get a video file out.
