# Characters, sound, camera and styles

Short how-tos for the parts of the screen that are not on every project.

## Characters

A character is a **rig**: its parts (head, arms, legs ...) tied to bones, so you pose it by moving the bones.

1. Draw or import the parts as separate layers. Name them like body parts (for example head, torso, upper arm L, forearm L, hand L, thigh, shin, foot).
2. Select the parts and click **Make rig** at the top of the settings panel (the buttons there show what you can do with your selection; less common ones are under **…**).
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

1. Make a swap set of mouth drawings (select the drawings, then **Make swap set**). Name them by mouth shape, or name the set "mouth".
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

## The Camera tool

1. Press **C**, or click **Camera** in the tool rail. It moves the scene's **frame** (the box that is exported, its camera), which every scene has.
2. The Camera tool is then on.
3. Drag on the canvas to pan. The picture follows your pointer.
4. Hold **Alt** and drag up to push in, down to pull out.

If the frame's settings are animated, a drag adds a key at the playhead. Otherwise it moves the frame for the whole piece. One drag is one undo step. When you let go, the picture slides to the camera's new view in about a tenth of a second instead of jumping; that is only how the screen shows it (the file and the export are not touched). The frame's settings (**X**, **Y**, **Zoom**, **Rotation**) are in the settings panel with the **Frame** row picked. While the project plays, the tool is off.

Pick the camera to see where it goes: its frame now is outlined, a faint outline shows its frame at each of its keys (cut at the picture's edge, never drawn into the grey margin), and a line with a dot per frame shows the point it looks at travelling. Drag a key's square or handles to change the move, as for any moving thing (see [the-screen.md](the-screen.md)). While you drag a camera key, the picture holds still as it was when you pressed, so the square stays under your pointer even with the playhead between two keys; when you let go, the picture shows what the camera now sees. **Camera frame** in the **Fit · 54 % ▾** menu (on at first) keeps the camera's frame and path showing even when the camera isn't picked.

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
- Click a colour: the selected shapes, paths and texts take it. Click a text style: the selected texts follow it. Click a logo: it goes onto the canvas.
- To add: pick a shape and click **+ This colour**, pick a text and click **+ This text's style**, or click **+ Logo…** to keep a logo file.
- **This scene's text styles** lists the styles made in this scene (it shows only when there are some).

## Adding a file

In the tool rail, the picture icon is **Add from a file…** (Ctrl+I): one door for pictures, videos, SVG, Lottie, PDFs and Photoshop files. It opens the file picker at once and the file comes in straight away (see [importing.md](importing.md)); a Figma frame comes in by pasting its link. The **Library** (Ctrl+L) is the books icon under it.
Once a Rostrum3D item of the project has a finished render, the picture icon opens a short list instead: **Add from a file…** first, then each rendered item by its name. Click an item's name to place its render.
