# Characters, sound and styles

Short how-tos for the parts of the screen that are not on every project.

## Characters

A character is a **rig**: its parts (head, arms, legs ...) tied to bones, so you pose it by moving the bones.

1. Draw or import the parts as separate layers. Name them like body parts (for example head, torso, upper arm L, forearm L, hand L, thigh, shin, foot).
2. Select the parts and click **Make a puppet (for bones)** at the top of the settings panel (on parts named like a body it is the first button; otherwise it is under **More › Make**). The top bar says what it made and that **J** (the Bone tool) draws its bones (the buttons there show what you can do with your selection; less common ones are under **…**).
3. Select the rig. If it has no bones yet and its parts are named like a body, **Bones from part names** appears. Click it: bones, arm and leg chains, and the binding of each part are made in one step. Undo takes it all back.
4. To draw bones yourself, press **J** (the **Bone** tool, there only while a rig exists). Click joint after joint, or drag from a joint to the bone's tip. **Esc** ends the chain.
5. To attach a part to a bone: select the part, **Ctrl+click** the bone, then click **Attach to bone**.

### Posing and Poses

Pose the character on the canvas by dragging its bones: press on a bone's middle and drag (an arm or leg bends as a chain to reach the pointer; any other bone turns about its joint). One drag is one undo step. With the rig (or its bones) selected, the settings panel has a **Poses** group:

- **Save pose** keeps the pose at the playhead. A rig with no poses yet shows only this button.
- Click a saved pose to key it at the playhead. Drag its slider to key only part of the way there from the pose the rig has now; the number beside it shows how much.
- Click **⋯** at the end of a pose's row (or right-click it) to **Rename** or **Delete** it. Double-click a name to rename it too.
- **Mirror pose** in the settings panel copies the left side onto the right, or the other way, or swaps them.

### Lip sync

1. Make a swap set of mouth drawings (select the drawings, then **More › Make › Make a set that shows one at a time**; **More** is at the end of the settings panel's top row; a set like this is called a swap set in the agent tools). Name them by mouth shape, or name the set "mouth".
2. Select the set. **Lip sync…** appears at the top of the settings panel.
3. In the sheet, click a **Voice line**. Voice lines come from RostrumSound. Check the drawing shown for each mouth shape and change a wrong one in its list.
4. Click **Apply**. The first time a voice line is used, the sheet listens to it: it shows **Step 1 of 3**, **2 of 3**, **3 of 3** with a moving bar, takes a few seconds (longer on a busy computer), and you can keep working meanwhile. A line heard before applies at once. The mouth is keyed to the voice in one change. **×** or **Esc** closes the sheet and leaves everything as it was. A voice line whose voice is not made yet in RostrumSound is not listed; the sheet says how many are waiting.

### Add blinks

1. Make a swap set of eye drawings (open, closed, and half closed if you have it). Name the set "eyes" or one drawing "closed".
2. Select the set. **Add blinks…** appears at the top of the settings panel.
3. Set **Every** (seconds), **Varies by**, and which drawing is **Open**, **Closed** and **Half**.
4. Click **Apply**. Blinks are keyed over the whole scene. They are normal keys you can move.

## Sound in 2D

Sound is made in RostrumSound. Rostrum2D plays it with the picture and lets you place things on it. For hearing it, muting, beats and snapping, see [timing-to-music.md](timing-to-music.md).

- **The Sound row** is the last row of the timeline. It shows the waveform and is there only when the project has sound.
- **Add a sound here…**: select one layer and click **Add a sound** in the tool rail. Search for a sound (type words, then **Enter**), and click one. It is tied to the layer's start, so it moves with the layer. RostrumSound mixes it. This appears only when the project has sound.
- **A video's own sound** shows as a thin row **Its sound** under the video layer. Its speaker button mutes it in the song's mix. **Ctrl+Z** brings it back.
- **MP4 with the project's sound:** open **Export**, pick **MP4**, and leave **Project sound** on. It shows only when the project has sound. See [exporting.md](exporting.md).

## Moving the frame

Every scene has one **frame**: the box that is exported. There is no camera tool. Press **C** (or click
the frame's name tab, or its **Frame** row at the top of the timeline) to pick it, then drag inside it to move it, drag
a corner square to zoom, and drag just outside a corner to turn it. With no keys a drag moves it for the whole piece;
once it has keys, a drag sets a key at the playhead. One drag is one undo step. With it picked, **Frame the view** fits
it to what your canvas shows and **Cut here** makes a jump at the playhead (**More** has **Frame home**, when the frame is away from home; **Cut here** shows once the playhead is after 0 s). Its path, a faint
outline at each key and its cuts show while it is picked. The whole of it is in [the-screen.md](the-screen.md) part 2 and
[frame-parallax-motion-blur.md](frame-parallax-motion-blur.md).

## Styles

A style keeps the look of a text (font, size, weight, colour ...) so other texts can follow it.

1. Select a text. In the settings panel's top buttons, open **Styles** and click **Save as style**.
2. Select other texts. Open **Styles** and pick the style. They follow it, and changing the style later changes all of them.
3. **Detach style** makes a text its own again. Changing one of a style's settings by hand on a text also detaches it.
4. **Copy style** then **Paste style** copies a look from one layer to others without making a named style.

## Library and Brand kit

Press **Ctrl+L**, or click **Library** (the books icon) in the tool rail, to open the **Library** beside the tool rail, over the left edge of the canvas; the rail stays where it is and the canvas keeps its size. Press again to close.

- **Brand kit** keeps the project's **colours**, **text styles** and **logos**. Every scene of the project sees them. It needs the scene to be in a project; if it is not, the drawer says so.
- The Library shows only what fits what you have picked. **Logos** (with **+ Logo…**) is always there. Pick a shape or path and **Colours** (with **+ This colour**) joins it; pick a text and **Text styles** (with **+ This text's style**) joins it; pick a group and you see only Logos. A section with nothing in it is not shown until you pick something that can fill it.
- Once the Library holds more than 12 things, a **search box** is at the top and has the keys as the Library opens. Type to find a colour (by name or hex), a text style, a logo (by file name) or a painting by name: every section narrows as you type, sections with nothing fold away, and nothing found says "Nothing called …". **Enter** uses the first one shown, as a click on it does. **Esc** clears the search, and **Esc** again closes the Library.
- **Paintings** are this scene's own (see [drawing.md](drawing.md) part 9), so they show with or without a project. The section is there once the scene has a painting, or when the layer you picked already has paint of its own (then a row **From <layer>'s paint** makes a painting from it). With no painting yet and a plain shape picked, there is no Paintings section: make the first one with **+ New painting** in the Fill picker (set the shape's fill to **Painted**), or from paint on a layer. Once the section shows it ends with **+ New painting** (a blank 512 × 512 painting that repeats seamlessly, opened to paint). Each painting is a row: a small picture (four repeats of it when it is seamless, so you see the repeat), its name, and one line, like "Seamless · 128 × 128 · 3 uses", "12 drawings · 1 use" or "not used".
  - **Click** a row to use it on what you picked: every picked shape and path gets it as its fill, in one step (a layer that already has a painted fill keeps how it sits; others are stretched; a layer's solid colour stays as its Colour under it). Texts and locked layers are skipped, and the top bar says so if none can take it. With nothing picked, a click picks the layers that use it.
  - **Open** (the ↗ button at the row's right) opens the painting on its own.
  - **Right-click** a row: **Use as the fill of 2 layers** (only when you picked shapes or paths), **Open**, **Rename** (type in the row, **Enter** keeps it, **Esc** leaves it), **Duplicate** (a copy named "… copy", not used by anything), **Delete**. Delete asks nothing: layers using it get a solid fill of its average colour, the top bar says "Paper grain deleted; 3 layers now have a solid fill", and **Ctrl+Z** brings the painting and every use back.
  - **+ New painting** under the rows makes a blank 512 × 512 painting that repeats seamlessly and opens it, to paint a texture. With one shape, path or drawing picked that has paint of its own, **+ From card 2's paint** turns that paint into a painting (a shape's paint moves in and becomes its fill, looking the same; a drawing is copied).
- Click a colour: the selected shapes, paths and texts take it. Click a text style: the selected texts follow it. Each logo shows a small picture of its file (a **?** and "File missing" when the file can't be read); click it and it goes onto the canvas.
- To add: pick a shape and click **+ This colour**, pick a text and click **+ This text's style**, or click **+ Logo…** to keep a logo file.
- **This scene's text styles** lists the styles made in this scene (it shows only when there are some).

## Adding a file

In the tool rail, the picture icon is **Add from a file…** (Ctrl+I): one door for pictures, videos, SVG, Lottie, PDFs and Photoshop files. It opens the file picker at once and the file comes in straight away (see [importing.md](importing.md)); a Figma frame comes in by pasting its link. The **Library** (Ctrl+L) is the books icon under it.
Once a Rostrum3D item of the project has a finished render, the picture icon opens a short list instead: **Add from a file…** first, then each rendered item by its name. Click an item's name to place its render.
