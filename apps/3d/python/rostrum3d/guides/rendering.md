# Rendering

Rendering makes the final pictures of a shot with Cycles. The pictures look like the viewport's Look: Final.

## Open the render sheet

Press **F12**, or click **Render** at the right of the top bar. Ctrl+E and ≡ › Export… open the same sheet. The sheet
takes the settings panel's place, so the viewport stays in sight. Esc or × closes it.

On the Build page it opens on **This frame**. On the Animate and Render pages it opens on the shot.

## The sheet, top to bottom

| Row | What it does |
|---|---|
| **What** | **This frame**: one picture at the playhead. **Hero 01 · 120 frames**: every frame of the shot, as numbered pictures. The count follows the frames set on the shot (the whole shot, or a stretch of it: the shot's Render group, Frames) |
| **Quality** | **Draft** (32 samples), **Good** (128) or **Final** (512), each with noise clean-up. The line under it says the numbers. Custom numbers are set on the shot (select the shot, then its Render group) |
| **Size** | The shot's own size, **½** or **× 2**. The line under it says the size in pixels when it isn't the shot's own |
| **Save as** | PNG picture, EXR (for the Editor), or both. Then the file's name and its folder (the project's next render version; Browse… picks another folder) |
| **The time** | How long it will take, measured on this computer (below) |
| **Render this frame / Render 120 frames** | Starts it. It runs in the background on its own engine; the top bar's job chip shows how far it is, with Cancel |

Quality and Size are **the shot's own settings**. Changing them in the sheet changes the shot (one step in the history;
↶ undoes it) and they are saved with it. Agents read and set the same settings, so a render an agent starts looks the
same as yours.

When it is done the line under the button says "Rendered …" with **Play** and **Show in folder**. A failure says what
went wrong in red, and nothing is called finished.

## The time

The time is **measured, never guessed**. When the sheet opens, the row says **Measuring…** while a short test runs in
the background: the shot's middle frame (or the playhead's frame, for This frame) through the same engine and settings
as the real render, at a quarter of the size and once at the real size with few samples. Then it says, for example:

> **About 6 min · 120 frames · 3.0 s a frame**
> from a test frame just rendered on this computer

The small picture beside it is the test frame: what you are about to render.

- **Changing Quality, Size or the frames** changes the number at once. No new test is needed.
- **Changing the scene** (moving, adding or re-lighting something) tests again, 0.4 s after the last change.
- The test is kept for the scene, so opening the sheet again on the same scene answers at once ("kept").
- **Another render on the graphics card** (another app, another window) makes everything slower. The row says so in
  amber when the test ran while the card was busy, and that test is not kept, so the next one measures a free card.
  The sheet never tests while one of this window's own renders is running; it waits for it.
- **Couldn't measure: …** means the test gave no answer in time (about two minutes: a very slow frame, or the
  engine stopped answering). The test is stopped and the row says why; change a setting or reopen the sheet to try again.

## A time budget

Click **Set a budget** under the time and type how long you can spend: `10 min`, `90 s`, `1 h` (a plain number means
minutes). Press Enter. When the render would take longer, the box turns red and lists the one-setting changes that fit,
each with its time: **Draft · about 2 min**, **Size ½ · about 3 min**. Click one to make that change on the shot.
Nothing fits by one setting alone? Shorten the frames on the shot.

## For agents

The sheet is built on the same pieces agents use: `render_estimate` (the same test and the same arithmetic),
`render_still` and the shot's render fields (`renderQuality`, `renderSize`, `renderRange`). See
[Working with an AI agent](agents.md), "Render settings and the time estimate".
