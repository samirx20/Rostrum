# Characters, sound, camera and styles

Short how-tos for the parts of the screen that are not on every project.

## Characters

A character is a **rig**: its parts (head, arms, legs ...) tied to bones, so you pose it by moving the bones.

1. Draw or import the parts as separate layers. Name them like body parts (for example head, torso, upper arm L, forearm L, hand L, thigh, shin, foot).
2. Select the parts and click **Make rig** in the context bar (the bar above the canvas that shows what you can do with your selection).
3. Select the rig. If it has no bones yet and its parts are named like a body, **Bones from part names** appears. Click it: bones, arm and leg chains, and the binding of each part are made in one step. Undo takes it all back.
4. To draw bones yourself, press **J** (the **Bone** tool, there only while a rig exists). Click joint after joint, or drag from a joint to the bone's tip. **Esc** ends the chain.
5. To attach a part to a bone: select the part, **Ctrl+click** the bone, then click **Attach to bone**.

### Posing and Poses

Pose the character on the canvas by moving its bones. With a rig selected, the settings panel has a **Poses** group:

- **Save pose** keeps the pose at the playhead.
- Click a saved pose to key it at the playhead. Its slider goes part of the way there.
- Right-click a pose, then **Delete**, to remove it.
- **Mirror pose** in the context bar copies the left side onto the right, or the other way, or swaps them.

### Lip sync

1. Make a swap set of mouth drawings (select the drawings, then **Make swap set**). Name them by mouth shape, or name the set "mouth".
2. Select the set. **Lip sync…** appears in the context bar.
3. In the sheet, click a **Voice line**. Voice lines come from RostrumSound. Check the drawing shown for each mouth shape and change a wrong one in its list.
4. Click **Apply**. The mouth is keyed to the voice in one change. **Cancel** or **Esc** leaves everything as it was.

### Add blinks

1. Make a swap set of eye drawings (open, closed, and half closed if you have it). Name the set "eyes" or one drawing "closed".
2. Select the set. **Add blinks…** appears in the context bar.
3. Set **Every** (seconds), **Varies by**, and which drawing is **Eyes open**, **Eyes closed** and **Half closed**.
4. Click **Apply**. Blinks are keyed over the whole scene. They are normal keys you can move.

## Sound in 2D

Sound is made in RostrumSound. Rostrum2D plays it with the picture and lets you place things on it. For hearing it, muting, beats and snapping, see [timing-to-music.md](timing-to-music.md).

- **The Sound row** is the last row of the timeline. It shows the waveform and is there only when the project has sound.
- **Add a sound here…**: select one layer and click it in the context bar. Search for a sound (type words, then **Enter**), and click one. It is tied to the layer's start, so it moves with the layer. RostrumSound mixes it. This appears only when the project has sound.
- **A video's own sound** shows as a thin row **Its sound** under the video layer. Its speaker button mutes it in the song's mix. **Ctrl+Z** brings it back.
- **MP4 with the project's sound:** open **Export**, pick **MP4**, and leave **Include the project's sound** on. It shows only when the project has sound. See [exporting.md](exporting.md).

## The Camera tool

1. Click **+ Add**, then **Camera**. A camera layer is added. Without a camera, the Camera tool is not in the tool strip.
2. Press **C** (or click **Camera** in the tool strip).
3. Drag on the canvas to pan. The picture follows your pointer.
4. Hold **Alt** and drag up to push in, down to pull out.

If the camera's settings are animated, a drag adds a key at the playhead. Otherwise it changes the camera's start look. One drag is one undo step. The camera's settings (**Looks at X**, **Looks at Y**, **Zoom**, **Roll**) are in the settings panel. While the project plays, the tool is off.

## Styles

A style keeps the look of a text (font, size, weight, colour ...) so other texts can follow it.

1. Select a text. In the context bar, open **Styles** and click **Save as style**.
2. Select other texts. Open **Styles** and pick the style. They follow it, and changing the style later changes all of them.
3. **Detach style** makes a text its own again. Changing one of a style's settings by hand on a text also detaches it.
4. **Copy style** then **Paste style** copies a look from one layer to others without making a named style.

## Library and Brand kit

Press **Ctrl+L**, or click **+ Add** then **Library**, to open the **Library** on the left of the canvas. It pushes the canvas aside and never covers it. Press again to close.

- **Brand kit** keeps the project's **colours**, **text styles** and **logos**. Every scene of the project sees them. It needs the scene to be in a project; if it is not, the drawer says so.
- Click a colour: the selected shapes, paths and texts take it. Click a text style: the selected texts follow it. Click a logo: it goes onto the canvas.
- To add: select a text and click **+ This text's style**, or select a layer and click **+ This colour**. Click **+ Logo…** to keep a logo file.
- **This scene · text styles** lists the styles made in this scene.

## The + Add button

At the foot of the tool strip. It holds what is not a drawing tool:

- **Import…** brings in files (see [importing.md](importing.md)).
- **Camera** adds a camera layer.
- **3D render** adds a Rostrum3D render. It is there only when Rostrum3D is installed.
- **Library** opens the Library (above).

Shapes, text, paths and drawings are made with their tools in the strip (**R**, **O**, **T**, **P**, and **Draw**).
