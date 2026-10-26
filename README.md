# Rostrum

Four desktop apps for making video, built so an AI agent can do the work and a person can do the same in a simple window.

| App | What it is for | Status |
|---|---|---|
| [Rostrum2D](apps/2d/README.md) | Motion design, type, UI animation, drawing, frame-by-frame, 2D characters | Working, in polish |
| [RostrumSound](apps/sound/README.md) | Music, sound effects, voice, recording, mixing | Working, in polish |
| [Rostrum3D](apps/3d/README.md) | Modelling, painting, materials, lighting, animation, rendering | In progress |
| [Rostrum Editor](apps/editor/README.md) | Edit, compositing, colour, final mix, delivery | Planned |

Every app has the same pieces:

- **One document per project.** People and agents edit the same file through the same operations, with one history (undo, versions, who changed what).
- **A Python layer and an MCP server**, so agents can drive everything a person can, and see or hear the result.
- **A Qt Quick window** built on one shared kit (`shared/gui-kit/`).
- **Engines:** Rust for 2D (Blitz + Skia) and Sound; C++ on OpenUSD, Hydra and Cycles for 3D.

## Layout

```
apps/2d/        Rostrum2D
apps/sound/     RostrumSound
apps/3d/        Rostrum3D
apps/editor/    Rostrum Editor
shared/         document core, project service, GUI kit, painting kit, MCP conventions
proofs/         early technical proofs the apps grew from
tools/          release and build tools
```

Each app's README says how it is built and run. Windows today; Mac is planned.

## Licence

MIT © 2026 HireMyLens Media. Third-party code and its licences: [ATTRIBUTIONS.md](ATTRIBUTIONS.md).
