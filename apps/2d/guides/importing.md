# Importing pictures and files

Bring a picture, a video, a PDF page, a Photoshop file or a Figma frame into your project, then work on the pieces like any other layer.

Add › Image and Add › Video work the same way: the picture or clip is copied into the project (its `media` folder), so moving the project or the original file never breaks the layer.

## 1. Bring a file in

1. Click **Media** in the tool rail (or press **Ctrl+I**), then **Import…**. The file picker opens at once.
2. Pick the file: pictures (PNG, JPG, WEBP, BMP, GIF, TIF), videos (MP4, MOV, WEBM, MKV, M4V, AVI), SVG, PDF and PSD. It comes in straight away, centred, as one step (**Ctrl+Z** takes it back). Dropping the file on the canvas does the same, where you let go.
3. A PDF comes in from its first page, an SVG's words as real text you can edit, and a page (SVG, PDF, PSD) fitted into your picture. (An agent's `run_import` can choose another page, letter outlines or the original size.)

## 2. What came across

1. The line at the top says what was imported ("Imported logo.svg: 4 layers").
2. If anything did **not** come across, the Import panel opens at the right of the canvas and lists it under "Didn't come across". Close it with the **×** in its corner.
3. The new layers appear in the timeline at the bottom, which is also the layers list. A file with several parts (an SVG logo, a PDF page, a PSD) comes in as one group; click the small arrow beside its name to open it and see the pieces.

## 3. Work on the pieces

1. Click a piece's name in the timeline to pick it, or click it in the picture. Pieces can be moved, changed and animated like any other layer.
2. To change several pieces together, pick them first: **Shift+click** on the canvas, or drag a box round them on empty canvas. The panel on the right then shows what they share, and a change applies to all of them as one step.
3. Look at the top of the settings panel for what you can do to them together: **Group**, **Align**, **Distribute**, **Mask**, **Combine** for shapes, and **…** (more) (see [the-screen.md](the-screen.md)).
4. **Hide** (the eye at the right of a piece's name) takes a piece out of the picture and the export without deleting it. **Lock** keeps a piece from being moved by mistake.

## 4. A single picture or video

You can also use **Media**, then **Picture** or **Video**, and pick the file there. It is the same result for one picture or clip.

A video layer's **Loop** has three choices: **Off** holds the last frame, **Loop** starts again, **Ping-pong** plays forward and then backward, over and over. (Its own sound can't play backwards, so with Ping-pong the sound simply starts again, forward.)

A picture or video you import is **copied into the project** (its `media` folder), so you can move, copy or rename the project folder and the layers still find their files, even after the original is deleted. Projects made before this are updated when you open them (one step in Undo). If a layer's file goes missing, the problems list and the export name the layer and the file. A file you point a layer at by hand, outside the project, stays where it is; the problems list says "File outside the project" because it will not travel with the project.

## 5. Figma

1. In Figma, copy the frame's link, then press **Ctrl+V** on the canvas. The Import panel opens set to **Figma**, with **File key** and **Frame** filled in from the link.
2. Type your own Figma access **Token** (it is not saved).
3. Click **Import**. A progress line shows while it works, and **Cancel** appears.

Next: [the-screen.md](the-screen.md), [exporting.md](exporting.md).
