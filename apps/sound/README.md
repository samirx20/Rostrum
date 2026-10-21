# RostrumSound

Music, sound effects, voice, recording and mixing. The one audio engine: every sound in every app renders through it.

- **Engine:** Rust (`native/`), the experiment's sound engine carried over (Firewheel for output, fundsp, our DSP, CLAP / VST3 hosting).
- **Script layer and API:** Python (`python/`), on `rostrum_core` (`shared/core/`): the sound document, its operations, the MCP server `rostrum-sound`. Rewritten from the experiment's TypeScript, not copied.
- **Screens:** Qt Quick, from `shared/gui-kit/`.
- **Hands over:** WAV stems (see `shared/HANDOFFS.md`).

Nothing is built here yet. See `docs/PLAN.md` › RostrumSound.
