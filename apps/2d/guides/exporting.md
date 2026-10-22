# Exporting a video

For a person using the Rostrum2D app: turn your project into a video, pictures or another file you can share or hand on.

## 1. Open the Export panel

1. Click the arrow button at the top right, next to **Import**. The **Export** panel opens at the right of the canvas.
2. Click the arrow button again, or **Close**, to put it away.

![The Export panel](pictures/export-panel.png)

## 2. Pick a format

The **Format** picker lists:

- **MP4 (H.264)**: a normal video that plays almost anywhere. Good for sharing and for most video editors. It cannot carry transparency.
- **ProRes 4444**: a high-quality video (.mov) that keeps transparency. Big files. For handing to a video editor.
- **WebM (VP9)**: a video for web pages. Can keep transparency.
- **GIF**: a small looping picture. Limited colours, no sound.
- **PNG sequence**: one picture for every frame, in a folder. Keeps transparency.
- **EXR sequence (for the Editor)**: one picture for every frame, made to be opened in Rostrum Editor.
- **Lottie (JSON)**: moving graphics for apps and web pages. It cannot carry everything. After the export, the panel lists what it left out under "Lottie couldn't carry".
- **Motion samples (for RostrumSound)**: not a picture. It is the movement of your layers, for placing sounds against.

## 3. Settings

Only the settings that apply to the chosen format are shown.

1. **Quality** (MP4): **Standard**, **High** or **Best**. Higher keeps more detail and makes a bigger file.
2. **Transparency**: a switch for formats that can keep it. Turn it on to keep see-through areas see-through.
3. **Bit depth** (PNG): how finely colour is kept, **8-bit** or **16-bit**.
4. **From** and **To**: the part of the project to export, in seconds. They start at the whole length.
5. If the project has more than one picture to choose from, a **Composition** picker appears first.

## 4. Where the file goes

1. Under **Save to** you see the file's name, and "Saved in" with its folder. By default it goes inside your project's folder, in its own new version folder, so an export never replaces an earlier one.
2. To choose another place, click **Choose…**, pick a folder and a name. **Default** goes back to the usual place.
3. If a file with that name is already there, the app asks **Replace?** with **Cancel**, **Keep both** and sometimes **Replace**.

## 5. Export

1. Click **Export**. A progress bar runs, and the button becomes **Cancel** while it works.
2. When it finishes, the panel says **Done** and lists what was made: the file, its frames, its size and the rest.
3. Click **Show in folder** to open where it went.
4. If something goes wrong the panel says so in red. Nothing is reported as done unless the file was made.

Next: [first-animation.md](first-animation.md), [files.md](files.md).
