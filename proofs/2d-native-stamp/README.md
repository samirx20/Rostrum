# H8 package B: native brush stamping

**Question.** Can the painting kit's brush engine (`shared/painting-kit`, numpy) lay its strokes natively with
pixel-identical results, and how much faster?

**Answer.** Yes. `apps/2d/engine/stamp/` (Rust library, no dependencies) lays the same pixels bit for bit, about 10–12×
faster on a 1080p layer (0.63 → 0.06 s for 20 pen strokes; 47 → 4 s for 20 long wet sweeps). Details and timings:
`apps/2d/engine/stamp/README.md`.

**The kit change (for Team Sam, `painting-kit.patch`, applies with `git apply` at the repo root):**

1. `brush.py`: `stamp_stroke` split into `plan` (unchanged maths: path, random draws, tip profiles, plus each dab's box,
   turn and wet carry, computed once) and `dabs` (the old dab loop, reading the plan). `stamp_stroke` takes
   `lay=` (who lays the dabs; default numpy). Colour jitter (`colorsys` per dab) and dab boxes are computed over arrays,
   step for step the same numbers; it was most of the plan's time.
2. `native.py` (new): loads the library, packs the plan, `lay` with `dabs`'s signature; fails loudly if asked for
   and not built.
3. `canvas.py` `stamp`, the one place: `lay=LAY`, where `LAY = native.lay if native.available() else None`;
   `canvas.STAMPER` says `"native"` or `"numpy"`.
4. `tests/test_native.py` (new, ~1 s): every tip in every mode, wet, grain, mask, edges: native and numpy give the same
   bytes (skipped where the library isn't built).

Pixels are identical, so cache keys need no change; `ENGINE_VERSION` still hashes `brush.py` (the split changes the
hash once, so old cached states are restamped once).

**Files.** `judge.py` (the identity check and the timings), `painting-kit.patch`.
Results: `C:\Users\Sam\.rostrum\waves\results\stage2\2d-engine\native-stamp-vs-numpy-h8.json`.

**Verdict.** Pass. Not yet: the plan's path resampling is still a Python loop (about a quarter of native time on long
strokes); the kit's look (compositing, PNG, look image, ~0.45 s at 1080p) is now the bigger cost of a stroke.
