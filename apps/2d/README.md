# Rostrum2D

Motion design, type, UI animation, drawing, frame-by-frame and 2D characters.

- **Engine:** Rust (`engine/`): the Blitz + Skia renderer carried over from the experiment (moved in Stage 2, `engine/README.md`), plus the per-frame animation work to come.
- **Script layer and API:** Python (`python/`), on the shared core `rostrum_core` (`shared/core/`): the 2D document, its operations, the MCP server `rostrum-2d`.
- **Screens:** Qt Quick, built from `shared/gui-kit/`.
- **Guides:** `skills/`, how-to guides for people and agents (techniques, not styles).

The engine is in; the Python layer is next. See `docs/PLAN.md` › Rostrum2D and `docs/CARRY_OVER.md` for what moves in.
