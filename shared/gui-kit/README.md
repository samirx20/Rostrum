# shared/gui-kit

The one Qt Quick UI kit all four apps use, so they look and behave alike and stay Figma-simple: colours, type, spacing, panels (project, inspector, history, AI), the timeline strip, the Ctrl+K command bar, Fast / Final viewers, and the slot where each app's native viewport (Hydra, the 2D renderer, video) sits.

Qt is LGPL, dynamically linked; no GPL-only Qt add-ons. The kit is shaped by the GUI proof (`proofs/gui-qt/`) and the experiment's design (`experiment-final:docs/GUI_DESIGN.md`). No code yet.
