# Rostrum2D

Motion design, type, UI animation, drawing, frame-by-frame and 2D characters.

- **Engine:** Rust (`native/`): the Blitz + Skia renderer carried over from the experiment, plus the per-frame animation work. Moved in only once the Blitz vs Chromium proof (P-2D) says keep.
- **Script layer and API:** Python (`python/`), on the shared core `rostrum_core` (`shared/core/`): the 2D document, its operations, the MCP server `rostrum-2d`.
- **Screens:** Qt Quick, built from `shared/gui-kit/`.
- **Guides:** `skills/`, how-to guides for people and agents (techniques, not styles).

Nothing is built here yet (Stage 1 is proofs). See `docs/PLAN.md` › Rostrum2D and `docs/CARRY_OVER.md` for what moves in.
