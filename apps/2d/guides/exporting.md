# Exporting a video

Turn your project into a video, pictures or another file you can share or hand on. The export is made the same way the picture on the canvas is drawn, so what you see is what you get. Layers you have hidden (the eye at the right of their name in the timeline) are left out.

## 1. Open the Export panel

1. Click **Export** at the top right (or press **Ctrl+E**). The **Export** panel opens at the right of the canvas.
2. Click **Export** at the top again, or the × at the panel's top right, to put it away.

![The Export panel](pictures/export-panel.png)

## 2. Pick what it is for

The panel lists what each export is for, with its file type at the right. Click one:

- **Video to share** (MP4): a normal video that plays almost anywhere. Good for sharing and for most video editors. It cannot carry transparency.
- **Video for editing, with transparency** (MOV, ProRes 4444): a high-quality video that keeps transparency. Big files. For handing to a video editor.
- **Video for the web** (WEBM): a video for web pages. Can keep transparency.
- **Moving picture for a chat or a page** (GIF): a small looping picture. Limited colours, no sound. It starts at half the size and 15 frames a second, so a 4-second full-HD scene comes out well under 1 MB for flat motion graphics (a full-size GIF at the scene's rate is many times that).
- **Still frames** (PNG): one picture for every frame, in a folder. Keeps transparency.
- **Frames for the Editor** (EXR): one picture for every frame, made to be opened in Rostrum Editor.
- **Animation for apps and websites** (JSON, Lottie): moving graphics for apps and web pages. It cannot carry everything. After the export, the panel lists what it left out under "Lottie couldn't carry".
- **Motion for RostrumSound** (JSON): not a picture. It is the movement of your layers, for placing sounds against.

## 3. Settings

Only the settings that apply to the chosen format are shown.

1. **Quality** (MP4): **Standard**, **High** or **Best**. Higher keeps more detail and makes a bigger file.
2. **Transparency**: a switch for formats that can keep it. Turn it on to keep see-through areas see-through.
3. **Size** and **Frame rate** (GIF): **Full size**, **Half size** (the default) or **480 px wide**; **15 frames a second** (the default) or **The scene's rate**. Below them one line, **File**, says what they come to: about how big the file will be, its pixel size and its frames, such as "about 0.3 MB · 960×540 · 150 frames at 15 fps". The size is measured, not guessed: the app draws a few frames in the background and makes a small GIF of them, so it says "size: working it out…" for a few seconds first. A drawing held for several frames or a still background costs almost nothing; a moving full-screen gradient costs a lot. After you export, this line goes and the result line below **Export** says the same facts for the real file. One palette for the whole GIF and a fixed dither pattern keep it small; it never makes the GIF larger than the scene or faster than the scene.
4. **Bit depth** (PNG): how finely colour is kept, **8-bit** or **16-bit**.
4. **Include the project's sound** (MP4 only, and only when the project has sound): a switch.
5. **Range**: a picker at the top of the sheet, above the list of formats. **Everything** (with the length in seconds) is the first choice; after it come the stretches between your markers, one for each pair of neighbouring markers, such as "intro → drop". It shows only when the project has at least two markers to pick from; with none, you export everything.
6. If the project has more than one picture to choose from, a **Composition** picker appears first.

## 4. Where the file goes

1. Under the settings you see the file's name and its folder. The file is named after the item you worked in ("loop.mp4"), with the composition's name after it only when the item has several compositions or the composition has a name of its own ("Title walk - Credits.mp4"). A new project's first item, "main", takes the project's name. A project that has its own folder saves inside it, in its own new version folder, so an export never replaces an earlier one.
2. A document that is not a saved project yet (for example the built-in sample) saves into your **Videos** folder, or your Documents folder if you have no Videos folder. It is never hidden away in a cache. A long folder path is shortened in the middle on one line; hover it to read the whole path.
3. To choose another place, click **Browse…** and pick a folder. **Renders folder** (shown once you have picked another) goes back to the usual place.
4. If a file with that name is already there, the app asks "… is already there" with **Cancel**, **Keep both** (the new one gets a number) and, for single files, **Replace**. A folder of frames can't be replaced.

## 5. Export

1. Click **Export**. A progress bar runs, and **Cancel** appears beside it while it works.
2. When it finishes, the panel says **Exported** and the file's real name (for a run of pictures: how many, and the first and last, such as "48 pictures, Scene_0001.png to Scene_0048.png"), with **Play** and **Show in folder**. One line above it says the file as written: its size on disk, its pixel size and its frames, such as "0.2 MB · 960×540 · 150 frames at 15 fps". Only what that line and the settings above don't already say is listed under the settings (for an MP4: how it was encoded). Change a setting and the result line goes, because it no longer describes what **Export** would make.
3. Click **Show in folder** to open where it went.
4. If something goes wrong the panel says so in red. Nothing is reported as done unless the file was made.

Next: [first-animation.md](first-animation.md), [files.md](files.md).
