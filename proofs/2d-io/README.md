# 2D import / export (Team Hem, H9)

**Question.** Can Rostrum2D bring in SVG, PDF, PSD and Figma files as real, editable layers, and send its work out as
MP4, ProRes 4444 with transparency, WebM with transparency, GIF, PNG sequences (8 or 16-bit) and Lottie, every
picture made by the same render path the screen uses, and every file checked after it is written?

**Verdict: pass with conditions.** Our own SVG, PDF and PSD come in as layers (names, order, groups, opacity, blend)
and, drawn by the engine, look like their sources side by side. All five picture formats export the same frames with
real transparency and are read back (frame count, size, alpha, bit depth). Lottie carries shapes, paths, groups,
images, masks and keys; what it can't carry is listed. Conditions: text is placed from its letters' box, so it can sit
a few px off (PDF ~10 px low); Lottie has no text yet; Figma is built but not tried against the live service (no token).

## How it works
- **Export** (`apps/2d/python/rostrum2d/io/export.py`, `formats.py`, `readback.py`): the engine draws every frame as
  for the screen and hands it to an encoder. `"alpha": true` leaves the comp's background out; a scene loaded with
  `"depth": 16` sends 16-bit frames. Encoders: FFmpeg for MP4 / ProRes (`prores_ks`) / WebM (`libvpx-vp9`, BSD), the
  engine itself for GIF (`encode-gif`: `gif` + `color_quant` crates, MIT/Apache; not gifski, AGPL) and PNG
  (`encode-png`, `png` crate). Each file is then read back and a wrong one raises with what was found.
- **Lottie** (`io/lottie*.py`): the scene description → Lottie JSON plus a report of everything it couldn't say.
- **Import** (`io/svg.py`, `pdf.py`, `psd.py`, `figma.py` → one import tree → `io/tree.py` → document operations,
  one undo step). SVG is read by usvg inside the engine (`rostrum2d-render svg-tree`, `render/src/svg_tree.rs`), PDF by
  pdfium (pypdfium2), PSD by psd-tools, Figma by its REST API with the user's own token (never stored or logged).
- Sources and the run: `make_sources.py` (makes our own SVG / PDF / PSD), `run_proof.py` (imports, renders, exports),
  `scene.py` (the export test scene).

## Results (`C:\Users\Sam\.rostrum\waves\results\stage2\2d-io\`)
| File | What |
|---|---|
| `import-svg-vs-source.png`, `import-pdf-vs-source.png`, `import-psd-vs-source.png` | source (left) beside the imported layers drawn by Rostrum2D (right) |
| `export-formats-over-checker.png` | frame 36 from every export over a checkerboard (transparency shows), beside the still |
| `export.mp4`, `export-prores4444-alpha.mov`, `export-vp9-alpha.webm`, `export.gif`, `png8\`, `png16\` | the exports (3 s, 1280×720, 30 fps) |
| `export-lottie.json`, `lottie-vs-engine-1.2s.png` | the Lottie file; our engine (left) beside lottie-web (right) at 1.2 s |
| `facts.json` | what every read-back found, and each import's layers and report |

Read back (3 s = 90 frames): MP4 90 frames, opaque; ProRes 90, `yuva444p12le`, alpha down to 0; WebM 90, alpha down
to 0; GIF 90, transparent; PNG 90 at 8-bit; PNG 16-bit 15 frames (1.0–1.5 s), 16 bits. Export times on this laptop:
MP4 1.7 s, ProRes 5.0 s, WebM 5.0 s, GIF 9.8 s, PNG 2.1 s (90 frames each).

## Known limits
- Text is placed by its letters' box, not its line box: a few px off (PDF ~10 px low). A gradient fill in SVG / Figma
  comes in as its first colour (reported); SVG clip paths, masks and filters are reported, not carried.
- Lottie: no text yet (needs the engine's glyph outlines); tilt and blur / glow / shadow / backdrop are reported;
  springs, bounces and colour keys are baked to one key per frame (reported).
- MP4 still uses FFmpeg's libx264 (GPL) as before H9; the shipped app must use the OS / GPU H.264 encoder and an
  LGPL FFmpeg build (ProRes and VP9 are both in an LGPL build).
- The FFmpeg on this laptop is a GPL build (dev tool only, not shipped).

## Attribution rows
| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| gif | 0.14.2 | MIT OR Apache-2.0 | `apps/2d/engine/render` (GIF export) | static (Rust crate) | yes | keep the licence notice | https://crates.io/crates/gif |
| color_quant | 1.1.0 | MIT | `apps/2d/engine/render` via gif (GIF palettes) | static (Rust crate) | yes | keep the licence notice | https://crates.io/crates/color_quant |
| png | 0.18.1 | MIT OR Apache-2.0 | `apps/2d/engine/render` (PNG sequence export) | static (Rust crate) | yes | keep the licence notice | https://crates.io/crates/png |
| usvg (our patched copy) | 0.48.1 | Apache-2.0 OR MIT | `apps/2d/engine/render` (SVG import, `svg-tree`) | static (Rust crate) | yes | keep the licence notice | https://crates.io/crates/usvg |
| psd-tools | 1.26.0 | MIT | `apps/2d/python/rostrum2d/io/psd.py` | Python package | yes | keep the licence notice | https://pypi.org/project/psd-tools/ |
| attrs | 26.1.0 | MIT | psd-tools | Python package | yes | keep the licence notice | https://pypi.org/project/attrs/ |
| pypdfium2 (with PDFium) | 5.14.0 | Apache-2.0 OR BSD-3-Clause (PDFium: BSD-3-Clause) | `apps/2d/python/rostrum2d/io/pdf.py` | Python package (bundled pdfium DLL) | yes | keep the licence notices (PDFium's third-party notices too) | https://pypi.org/project/pypdfium2/ |
| skia-pathops | 0.9.2 | BSD-3-Clause | `rostrum2d` (already declared in pyproject; installed into the venv) | Python package | yes | keep the licence notice | https://pypi.org/project/skia-pathops/ |
| lottie-web | 5.13.0 | MIT | proof only: renders our Lottie for the comparison (scratch folder) | not linked | no | — | https://www.npmjs.com/package/lottie-web |
