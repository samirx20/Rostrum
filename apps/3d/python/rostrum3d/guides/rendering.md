# Rendering

Rendering makes the final pictures of a shot with Cycles. The pictures look like the viewport's Look: Final. A shot whose
Quality is **Stylized** renders with the stylized renderer instead, and looks like the viewport's Look: Stylized.

## Render: the final picture, one click

Click **Render** at the right of the top bar (or press **F12**). It starts at once and always makes the **final-quality**
picture of the shot's current frame (the Final preset, whatever Quality the sheet shows; a shot set to Custom samples
keeps its own, a shot set to Stylized renders Stylized). From the click, the button's place shows the seconds so far against the time it will take ("12 / 40 s";
rest the pointer on it for the whole sentence) when this scene's time was measured before (the render sheet's test).
Otherwise there is no number yet (a scene's set-up, Cycles loading its kernels and what else the computer is doing all
change it): the button shows only the seconds so far ("12 s") and the note says "measuring the time". Once the final renderer has
drawn a little of the frame (usually within a few seconds), the time is measured on that frame itself: "about 25 s
left", and the clock follows it. **×** beside it cancels. When
it is done the picture shows over the viewport, saved in the project's Renders folder (`renders/<item>/vNNN/`, a PNG
and an EXR); **Show in folder** opens that folder with the picture selected, **Close** (Esc) goes back to the view.

## Open the render sheet

For anything else (the whole shot as frames or as an MP4 video, Draft or Good, another size, EXR passes, a file of your own): click the
**▾** beside Render. Ctrl+E and the mark's menu › Export… open the same sheet. The sheet
takes the settings panel's place, so the viewport stays in sight. Esc or × closes it.

On the Build page it opens on **This frame**. On the Animate and Render pages it opens on the shot.

## The sheet, top to bottom

| Row | What it does |
|---|---|
| **What** | **This frame**: one picture at the playhead. **Hero 01 · 120 frames**: every frame of the shot, as numbered pictures. **Hero 01 · MP4 video**: the same frames as one MP4 (H.264), plus a small `-share.mp4` copy beside it (about 8 Mbit/s at 1920 × 1080, less for smaller sizes) to send or post; Save as and Passes are not shown for it. The count follows the frames set on the shot (the whole shot, or a stretch of it: the shot's Render group, Frames) |
| **Quality** | **Draft** (32 samples), **Good** (128) or **Final** (512), each with noise clean-up. The numbers (samples, noise clean-up) are on the same line, at the right. Custom numbers are set on the shot (select the shot, then its Render group). **Stylized** is there while a material has Lines or Halftone on: the stylized renderer (lines, halftone, light to colour; guide `materials`), drawn at twice the size and smoothed down; its EXR holds the picture only (no passes) |
| **Size** | The shot's own size, **½** or **× 2**. The size in pixels shows at the right of its name when it isn't the shot's own |
| **Save as** | PNG picture, EXR (for the Editor), or both. Then the file's name and its folder (the project's next render version; Browse… picks another folder) |
| **Passes** | Only while it saves an EXR. The extra layers inside the EXR, beside the picture (which is always there): **Light**, **Shadow**, **Reflections**, **Masks per item**, **Depth**, **Surface direction**. Click a name to add it (✓) or take it out (+). Masks are on to start with. See "Passes" below |
| **The time** | How long it will take, measured on this computer (below) |
| **Render this frame / Render 120 frames / Render 120 frames as MP4** | Starts it. It runs in the background on its own engine; the line under the bar says **Frame 12 of 120 · about 4 min left** (the time left is worked out from the frames this render has drawn, so it appears once the first frame is done), the top bar's job chip shows how far it is, with Cancel |

Quality, Size, Save as and Passes are **the shot's own settings**. Changing them in the sheet changes the shot (one step in the history;
↶ undoes it) and they are saved with it. Agents read and set the same settings, so a render an agent starts looks the
same as yours.

When it is done the line under the button says "Rendered …" with **Play** and **Show in folder**. A failure says what
went wrong in red, and nothing is called finished.

**Stopped or failed? The finished frames are kept.** Cancel a shot render (or have it fail) and the line says "Stopped ·
130 finished frames kept". Open the sheet again with the same choices and it says **Continues from 130 finished frames**:
Render draws only the missing frames, in the same version folder. The frames are reused only while nothing that shows in
them has changed (the scene, the shot, Quality, Size, Save as, Passes); change one and the render starts afresh. A
frame file is reused only when it is whole.

## Passes

An EXR can carry the picture split into layers, so the Editor can change one part without rendering again: brighten
the reflections, soften the shadows, colour one item. Each pass is a named layer of the same file, and the render's
`manifest.json` lists them (its `exr` part: every channel name, which layer it belongs to, and which item each mask is).

| Pass | Layer in the EXR | What it holds |
|---|---|---|
| The picture | `R G B A` | always there: the finished picture, alpha = where something is |
| **Light** | `light.R G B` | the light falling on matte surfaces, direct and bounced, with their colour |
| **Reflections** | `reflections.R G B` | reflections and highlights on shiny surfaces |
| (with either) | `rest.R G B` | everything else: glass, glowing things, the sky, haze |
| **Shadow** | `shadow.A` | 0 where a matte surface is fully lit, 1 where it is in full shadow from the lights |
| **Masks per item** | `masks.<item id>` | one per item (groups too): white where the item is, black elsewhere |
| **Depth** | `depth.Z` | distance from the camera in metres (full precision); 0 where nothing is |
| **Surface direction** | `normal.X Y Z` | which way each surface faces, in the scene's directions (Y up) |

**They add back up.** Light + Reflections + Rest = the picture. With noise clean-up on, the picture is cleaned but the
layers are not, so they add up to a slightly grainier picture; with it off they add up exactly.

Things to know:
- **Shadow doubles the render time**: each frame is drawn a second time with no shadows, to see what the shadows took
  away. The time row counts it.
- **Masks have hard edges** (one sample a pixel), so an edge can look stepped when a mask is used on its own.
- Passes need the final renderer (Cycles); a quick (Storm) render saves the picture alone.

## The time

The time is **measured**, never guessed. When the sheet opens with nothing measured yet, the row says "Measuring…" while a short test runs in
the background: the shot's middle frame (or the playhead's frame, for This frame) through the same engine and settings
as the real render, at a quarter of the size and once at the real size with few samples. Then it says, for example:

> **About 6 min**
> 120 frames · 3.0 s a frame

The small picture beside it is the test frame: what you are about to render. Rest the pointer on the box to see how it
was measured ("from a test frame just rendered on this computer", or "kept" when the scene's earlier test is reused).

- **Changing Quality, Size or the frames** changes the number at once. No new test is needed.
- **Changing the scene** (moving, adding or re-lighting something) tests again, 0.4 s after the last change.
- The test is kept for the scene, so opening the sheet again on the same scene answers at once ("kept").
- **Another render on the graphics card** (another app, another window) makes everything slower. The row says so in
  amber when the test ran while the card was busy, and that test is not kept, so the next one measures a free card.
  A busy-card figure already holds the slowdown: on a free card the render is faster, often several times (a cloth drape
  tested at 54 s a frame while four other renders shared the card drew in 4–5 s a frame on its own at 1280×720, 16 samples).
  Test again once the card is free before giving up Cycles for Storm.
  The sheet never tests while one of this window's own renders is running; it waits for it.
- **The Render button** says "measuring the time" until it has a measured number for this scene or Cycles' own progress gives one
  ("about 25 s left"); it never shows a first guess, and a kept number under what Cycles can do (about a second) is not shown.
- **Couldn't measure: …** means the test gave no answer in time (about two minutes: a very slow frame, or the
  engine stopped answering). The test is stopped and the row says why; change a setting or reopen the sheet to try again.

## A time budget

Click **Set a budget** under the time and type how long you can spend: `10 min`, `90 s`, `1 h` (a plain number means
minutes). Press Enter. When the render would take longer, the box turns red and lists the one-setting changes that fit,
each with its time: **Draft · about 2 min**, **Size ½ · about 3 min**. Click one to make that change on the shot.
Nothing fits by one setting alone? Shorten the frames on the shot.

## The Render page and its queue

Click **Render** among the pages (Alt+3). The top bar's Render button is not there on this page: the settings panel
has its own.

- **Settings panel** (nothing selected): the shown shot's render settings, the same rows as the sheet (Quality, Size,
  Save as), its measured time, then **Render** (F12: this shot next) and **Add to queue** (after the others). Select
  an item and its own settings show instead, as on the other pages.
- **Bottom left, the shots**: each shot with its length and when it was last rendered. Click one to show it. Tick
  shots and click **Queue ticked (2)** to add them all. Right-click a shot: **Send to 2D** (one entry per 2D scene
  when the project has several) and **Open its folder** (only when it has a render).
- **Bottom right, the queue**: one render runs at a time; the rest wait in order. A running render shows a bar,
  "frames 3 of 12" and the time left. A waiting one says **Next** or its place in line; **↑ ↓** move it earlier or
  later. **✕** cancels a waiting or running render. Finished renders stay below with the time taken and their
  folder: click one to see its last frame over the viewport (Close or Esc puts it away).

**Cancel** ends that render's own engine at once; the row says **Render cancelled** in red. The frames it finished stay
in its half-made folder: rendering the same shot again, with nothing changed, continues from them (a render cancelled
before its first frame leaves nothing). A render that fails says why in red, and nothing is called
finished. Each render uses the shot's settings as they were when you added it; changes made while it waits or runs
are not in it. While a queued render runs, the render sheet waits for it (one render on the graphics card at a time).

## Send a shot to 2D

Select the shot (or right-click it on the Render page) and pick **Send to 2D**. Its render of the scene as it is now
becomes a **3D render** layer in a 2D scene of the project, with its transparency; an open 2D window shows it arrive.
If the shot has no render of its current state, it is rendered first (the Render page's queue), then sent. With
several 2D scenes, pick one from the menu; a later Send of the same shot goes to the same layer and keeps what was
moved or sized in 2D.

The layer follows that shot's newest render. When you change the 3D scene, 2D's Problems list says
"3D render out of date" until you send (or render) it again; re-running a script that changes nothing does not.
Send to Editor comes with the Editor (not built yet).

## For agents

The sheet is built on the same pieces agents use: `render_estimate` (the same test and the same arithmetic),
`render_still`, `render_send_shot` and the shot's render fields (`renderQuality`, `renderSize`, `renderRange`, `renderFormat`,
and the pass switches `passLight`, `passShadow`, `passReflections`, `passMasks`, `passDepth`, `passNormal`). See
[Working with an AI agent](agents.md), "Render settings and the time estimate".

`render_video` with `estimate_only` answers at once with the measured figures (also over `budget_min`); with `budget_min` alone, over it
is an immediate error naming settings that fit. The estimate counts what a changing scene costs each frame (a cloth or a fall's new shape sent in, animation: one extra small frame at the
next frame is timed by the probe), and learns from your own renders: when the last full render of a shot took 10 % or more over its
estimate, the next estimate of that shot (same project, same session) is raised by that much (never lowered) and its reply says
"raised ×1.6". It is still a guide, not a promise: leave margin under a tight `budget_min`, and a many-polygon cloth or a busy card
runs over. A cloth itself costs little in Cycles (an 18k-triangle drape adds about 0.6 s a frame at 1280×720, 16 samples, over the
same scene without it); the samples, the picture's size and the lights are what cost the time. A refine export with no `quality`,
`renderer` or `samples` never renders lower than your last export of the shot (its reply says "Rendered as your last export …");
asking for lower is done, and the reply names what it loses (Storm: no fabric sheen, no soft bounce light, hard shadows).
A finished video's reply asks for a look-and-fix pass (`look_frame what "sheet"`, `look_frame`,
`look_motion`), and every reply ends with a time line that counts the passes the time left allows ([Working with an AI agent](agents.md), "Your time").

Looking before you render: `look_frame` (one frame, with its clipped share and the text reading direction), `look_frame what "sheet"` (one shot over
time), `look_frame what "shots"` (several shots, a row each) and `look_frame what "material"` (one material on a ball, under the scene's lights).
