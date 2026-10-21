# Hand-offs between apps

How the four apps pass finished pictures and sound to each other, and how colour and timing line up. In short:

- **Pictures:** OpenEXR image sequences with named layers.
- **Sound:** WAV stems.
- **Colour:** one OpenColorIO set-up for the whole project.
- **Timing:** markers, not copied numbers.

Related contracts:
- [`shared/project-service/CONTRACT.md`](project-service/CONTRACT.md): project items, markers, live links, the content-keyed cache, the jobs queue.
- [`shared/core/OPERATIONS.md`](core/OPERATIONS.md): every setting below is changed by an operation, recorded in the history.
- [`shared/mcp/CONVENTIONS.md`](mcp/CONVENTIONS.md): the `render_*` tools that write these files.

**Inside Rostrum the Editor reads these through live links.** People never pick or name these files ("one project, files hidden"). The same files are what outside tools (Nuke, Resolve, Pro Tools) get.

## 1. Where hand-offs land in the project folder

The top-level project layout belongs to the project service contract. Hand-offs use these folders in it:

```
<project>/
  colour/
    config.ocio           the project's one OpenColorIO config (§4)
    luts/                 LUT files the config or grades use
  renders/
    <item-id>/
      v001/               one finished version
        manifest.json     what this render is (§5)
        <item-id>.1001.exr  …  <item-id>.1240.exr
      v002/
      v003.partial/       a render in progress, or one that failed (never linked)
    <sound-item-id>/
      v001/
        manifest.json
        <item-id>_dialogue.wav  _music.wav  _effects.wav  _ambience.wav  _mix.wav
  exports/                final deliveries (MP4, ProRes, delivery WAV) from the Editor's Deliver page
```

- **One folder per version.** A render never overwrites an earlier version. Old versions are cleared by the project service's clean-up, never by an app.
- **Written whole or not at all.** A render writes into `vNNN.partial/`. It is renamed to `vNNN/` only after every check in §5 passes. A failed render stays `.partial`, and the job's error names it.
- `item-id` is the project item's stable id. File names use only letters, digits, `_` and `-`.

The content-keyed cache is not in the project: it is one machine-wide folder (`C:\Users\<user>\.rostrum\cache\`), see the project service contract › The shared cache.

## 2. Pictures: layered OpenEXR

2D and 3D hand pictures to the Editor as **OpenEXR image sequences**: one file per frame. Each file holds **several named layers**, so the Editor can change a shadow or a glow without rendering again. (OpenEXR is the film industry's open picture format, BSD licence.)

### Frame numbers
- `<item-id>.<frame>.exr`, at least 4 digits: `intro.1001.exr`.
- **The document's first frame is 1001** (the film-industry habit). Frames before 1001 are free for handles (extra frames before a cut, for a transition), and frame 1 never collides with them.
- One file is one frame at the document's frame rate (§6). No gaps: a missing frame is a failed render.

### Layers
Each layer is one **part** of a multi-part EXR. Standard names, so Nuke and Resolve read them too:

| Layer | Channels | Pixel type | Who writes it |
|---|---|---|---|
| `rgba` (beauty, the finished picture) | `R G B A` | half float | 2D, 3D |
| `depth` | `Z` (distance from the camera, metres) | float | 3D |
| `normal` | `X Y Z` (camera space) | half float | 3D |
| `motion` | `X Y` (pixels moved to the next frame) | float | 2D, 3D |
| `diffuse`, `specular`, `emission`, `shadow`, `ao`… | `R G B` | half float | 3D (render passes the shot asks for) |
| `light_<name>` | `R G B` | half float | 3D (one per light group) |
| `crypto_object`, `crypto_material` (+ 2D: `crypto_layer`) | Cryptomatte channels and manifest | float | 2D, 3D |
| `<name>` (any other named layer the shot asks for) | `R G B A` | half float | 2D, 3D |

- **Cryptomatte** is the open standard for "id mattes": every object gets a code, so the Editor can pick any object as a mask later. We follow its published spec (layer names, manifest, hashing) so outside tools read it.
- **Alpha is premultiplied** (colour already multiplied by alpha), the EXR rule.
- **Beauty adds up:** the 3D passes add back to `rgba` (within a small, measured tolerance). If they can't, the manifest says which passes don't add up.
- **Compression:** ZIP (lossless) by default. Data layers (`depth`, `motion`, ids) are always lossless.
- **Overscan** is allowed: the picture can be rendered a little bigger than the frame (for shake or lens effects). The EXR "display window" is the frame; the "data window" is what was rendered.

### Header facts in every file
`chromaticities` (the colour space, §4), `framesPerSecond` (as a fraction, for example `24000/1001`), `timeCode`, camera matrices (`worldToCamera`, `worldToNDC`) for 3D, and `rostrum:item`, `rostrum:version`, `rostrum:engine` (the engine version that made it).

### Outside tools
The Editor's Deliver page also writes ProRes 4444 (with transparency) and PNG sequences for people who need them. Inside Rostrum, EXR is the only picture hand-off.

## 3. Sound: WAV stems

Sound hands over **WAV stems**: separate files for the parts of the mix, which line up exactly when played together.

- **Sample rate: 48,000 Hz** (the video standard). **Stereo** first (5.1 and Atmos later).
- **Hand-off stems: 32-bit float** (no clipping, room to adjust). **Deliveries: 24-bit** (the Deliver page converts, with dither).
- **Broadcast WAV** (WAV plus a small info block): it records the start time, so outside tools place it correctly, and the measured loudness.
- **Stems:** `<item-id>_dialogue.wav`, `_music.wav`, `_effects.wav`, `_ambience.wav`, plus `_mix.wav`. Dialogue, music and effects is the standard split studios expect. A project can add more stems (`_foley.wav`) through an operation.
- **Same length, same start.** Every stem starts at the sound document's time 0 and runs its full length, silence included. Nothing is trimmed, so they line up sample-exact.
- **Stems add up to the mix.** The render checks this. Master-bus processing (limiter, master EQ) is applied only to `_mix.wav`. The manifest says so, because those stems then won't add up exactly to the mix.
- **Loudness:** stems are never made louder or quieter to hit a target. The loudness target (YouTube about −14 LUFS, broadcast −23 LUFS, true peak at or under −1 dBTP) is set once, on the final mix, in Sound's Mix page or the Editor's Deliver page. The manifest records the measured loudness and true peak of each file, and every clipped moment.
- **One audio engine** (AGENTS rule 9): the Editor's final mix is rendered by RostrumSound's engine. The stems are the rendered, cached form of a sound item and what outside tools get. They are not a second mixer.

## 4. Colour: one OpenColorIO set-up

**OpenColorIO** (OCIO; BSD licence) is the film industry's shared colour system. Every app uses the project's **one** config, `colour/config.ocio`, so a colour looks the same in all four apps. (The experiment used its own colour code and kept OCIO only for testing. Now we use the real library everywhere, and that colour code is only a reference.)

- **Starting point:** OCIO's built-in **ACES 2.0** studio config, written into the project when it is made, so the project doesn't change when Rostrum updates. Our extra views (below) are added to it.
- **Working space: ACEScg** (linear light, wide colour range). Everything is combined, blurred and blended in it. Hand-off EXRs are ACEScg.
- **Grading space: ACEScct** for wheels, curves, contrast and saturation. ACEScg for exposure, white balance and keying.
- **Views** (how the linear picture is turned into what the screen shows): **ACES 2.0**, **Neutral** (Khronos PBR Neutral), **AgX**, and **Standard** (clip only). Each has its inverse. The view is a project setting, changed by an operation.
- **Displays:** sRGB (computer screens), Rec.709 (video), Display P3 (Apple), and later HDR (Rec.2100 PQ / HLG).
- **Inputs:** each picture or video declares its colour space: detected, and the person or agent can change it.
  - Camera log footage, EXR and 3D renders come in through their input transform.
  - **Graphics and sRGB images** (2D design, logos, `#ff5a1f` colours) come in through the **inverse of the project's view**. So a brand colour comes out exactly as typed, whatever the view. Resolve and Nuke work the same way.
- **2D:** the 2D document blends in display space by default (like a browser) or in linear light (a per-document setting). Either way, its hand-off EXR is converted to ACEScg as above.
- **Colour ends in one place:** the Editor applies the view, the final grade and the conversion to 8 or 10 bits, once, with dither, at export. Standalone 2D or 3D exports go through the same steps (preview ≡ export).
- **Data layers** (`depth`, `normal`, `motion`, ids) are tagged "raw" and never colour-converted.

> **DECISION (Sam):** which view new projects start with. **ACES 2.0** (the film-industry standard, softer highlights), **Neutral** (keeps product and brand colours closest to what was typed; the experiment's default), or **AgX** (gentle with very bright colours). Any project can switch later. Until Sam picks: Neutral, to match the experiment.

## 5. The manifest: what each render is

Every version folder has a `manifest.json`. The Editor, the cache and agents read it; nobody guesses from file names.

```json
{
  "item": "intro", "version": 3, "kind": "pictures",
  "made_by": "agent:claude-code", "made_at": "2026-10-21T14:02:11Z",
  "source": { "document": "intro", "history_entry": "h_0192" },
  "engine": "rostrum-2d 0.4.1",
  "frames": { "first": 1001, "last": 1240, "fps": "24/1", "start_timecode": "01:00:00:00" },
  "size": [1920, 1080], "overscan": [0, 0],
  "colour": { "config": "colour/config.ocio", "space": "ACEScg" },
  "layers": ["rgba", "motion", "crypto_layer"],
  "checks": { "frame_count": "ok", "readable": "ok", "empty_frames": "none", "nan_pixels": "none" }
}
```

A sound manifest has `"kind": "sound"`, `sample_rate`, `bit_depth`, `stems` and, per file, `loudness_lufs`, `true_peak_db` and `clipped_at`.

- `history_entry` ties the render to the exact version of the document. A changed document means a new render, never a patched one.
- The cache key includes the engine version (AGENTS rule 7): a new engine re-renders.

## 6. Timing and frame rates

- **One project frame rate**, a fraction: `24/1`, `25/1`, `30/1`, `24000/1001` (23.976), `30000/1001` (29.97), `60/1`. A document can use another rate (for example a 60 fps social cut). The Editor then shows, at each moment, the frame that covers that moment; it never blends frames.
- **Time is seconds from the document's start.** Frame `n` (counting from 0) shows the moment `n / fps`, and is file number `1001 + n`. Motion blur is centred on that moment.
- **Sound is sample-exact:** sample `s` is at `s / 48000` seconds. At 23.976 or 29.97 a frame doesn't fall on a whole sample; the seconds are the truth, frames and samples are both read from them.
- **Timecode** (`HH:MM:SS:FF`) is a label for people and outside tools. Drop-frame at 29.97 and 59.94, non-drop otherwise. Rostrum never computes timing from timecode.

## 7. Markers and live links

- **Markers** are named moments ("logo lands", "drop"). Each document publishes its own (the experiment's rule, which Sam chose on 2026-10-12). Others refer to them by name: `"music#drop"`, `"music#drop+0.25"`, `"music#bar:9"`. The music's bars and beats are markers worked out from the tempo, never stored. Where markers live and how they are read is in the project service contract.
- **Cross-app timing only goes through markers.** When a marker moves, single times tied to it (a sound effect, a voice line, a clip start) move with it. Animation tied to it is reported as out of date until its script runs again.
- **Live links** point from a place in one document to another item. The Editor links to the item, never to a file path. The project service resolves it to that item's **latest finished version**, or to a version the person pinned. A new render shows up in the Editor without anyone re-importing it.
- **Sound to 2D / 3D** for lip sync: words and mouth-shape timings travel as markers on the voice item, not as files.
- A link to an item with no finished render shows a clear "not rendered yet" placeholder and an error in the agent's checks. It never shows an old frame silently.
