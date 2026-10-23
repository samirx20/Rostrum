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

Pose the character on the canvas by moving its bones. With the rig (or its bones) selected, the settings panel has a **Poses** group:

- **Save pose** keeps the pose at the playhead. A rig with no poses yet shows only this button.
- Click a saved pose to key it at the playhead. Drag its slider to key only part of the way there from the pose the rig has now; the number beside it shows how much.
- Click **⋯** at the end of a pose's row (or right-click it) to **Rename** or **Delete** it. Double-click a name to rename it too.
- **Mirror pose** in the settings panel copies the left side onto the right, or the other way, or swaps them.

### Lip sync

1. Make a swap set of mouth drawings (select the drawings, then **Make swap set**). Name them by mouth shape, or name the set "mouth".
2. Select the set. **Lip sync…** appears at the top of the settings panel.
3. In the sheet, click a **Voice line**. Voice lines come from RostrumSound. Check the drawing shown for each mouth shape and change a wrong one in its list.
4. Click **Apply**. The mouth is keyed to the voice in one change. **×** or **Esc** closes the sheet and leaves everything as it was. A voice line whose voice is not made yet in RostrumSound is not listed; the sheet says how many are waiting.

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

1. Press **C**, or click **Camera** in the tool rail. The first time, a camera layer is added for you.
2. The Camera tool is then on.
3. Drag on the canvas to pan. The picture follows your pointer.
4. Hold **Alt** and drag up to push in, down to pull out.

If the camera's settings are animated, a drag adds a key at the playhead. Otherwise it changes the camera's start look. One drag is one undo step. The camera's settings (**Looks at** with its X and Y boxes, **Zoom**, **Roll**) are in the settings panel. While the project plays, the tool is off.

Pick the camera to see where it goes: its frame now is outlined, a faint outline shows its frame at each of its keys, and a line with a dot per frame shows the point it looks at travelling. Drag a key's square or handles to change the move, as for any moving thing (see [the-screen.md](the-screen.md)). **Camera frame** in the **Fit · 54 % ▾** menu (on at first) keeps the camera's frame and path showing even when the camera isn't picked.

## Styles

A style keeps the look of a text (font, size, weight, colour ...) so other texts can follow it.

1. Select a text. In the settings panel's top buttons, open **Styles** and click **Save as style**.
2. Select other texts. Open **Styles** and pick the style. They follow it, and changing the style later changes all of them.
3. **Detach style** makes a text its own again. Changing one of a style's settings by hand on a text also detaches it.
4. **Copy style** then **Paste style** copies a look from one layer to others without making a named style.

## Library and Brand kit

Press **Ctrl+L**, or click **Media** in the tool rail then **Library**, to open the **Library** beside the tool rail, over the left edge of the canvas; the rail stays where it is and the canvas keeps its size. Press again to close.

- **Brand kit** keeps the project's **colours**, **text styles** and **logos**. Every scene of the project sees them. It needs the scene to be in a project; if it is not, the drawer says so.
- Click a colour: the selected shapes, paths and texts take it. Click a text style: the selected texts follow it. Click a logo: it goes onto the canvas.
- To add: select a text and click **+ This text's style**, or select a layer and click **+ This colour**. Click **+ Logo…** to keep a logo file.
- **This scene · text styles** lists the styles made in this scene.

## The Media group

In the tool rail, under the picture icon. It holds what is not a drawing tool:

- **Picture** and **Video** pick a file and put it on the canvas.
- **Import…** brings in files, PDFs, Photoshop files and Figma frames (see [importing.md](importing.md)).
- **Library** (Ctrl+L) opens the Library.
- **3D render** adds a Rostrum3D render. It is there only when Rostrum3D is installed.
