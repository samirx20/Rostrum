# gui-mock-web — the P-GUI-MOCK screen in web tech

The same screen as `../gui-mock-qt/`, built from `../gui-mock/controls.json` and `demo.json` only. Rules: `../gui-mock/README.md`. Vite + React + TypeScript, plain CSS, no UI library.

## Run

```
cd C:\Users\Sam\.t3\worktrees\Rostrum\team-sam\proofs\gui-mock-web
npm install
npm run dev            # http://localhost:5173
npm run shoot          # builds, serves, shoots the 3 moments, checks them, records the video
```

`npm run shoot` writes `web-camera-dof-off.png`, `web-camera-dof-on.png`, `web-text-animate-on.png` and `web-reveal.mp4` to `C:\Users\Sam\.rostrum\waves\results\stage1\p-gui-mock\`. It compares what is visible (the `window.mock.visible()` list and the real on-screen rows in the page) with `../gui-mock/expected.json` and **fails with a message and exit code 1** if they differ. It starts `vite preview` and ends it by PID.

Keys: click or ↑ ↓ selects an item; Ctrl K opens the command bar (type to filter, ↑ ↓, Enter, Esc). Number fields: drag sideways, ↑ ↓ (Shift = ten steps), or click to type.
In the browser console: `mock.select("cam1")`, `mock.setValue("cam1", "dof", true)`, `mock.visible()`. Clicks, keys, the command bar and the demo script all go through those same two functions (`src/store.ts`).

## How conditional showing is done

- `src/logic.ts` has the condition evaluator (`is`, `not`, `all`, `any`, `fact`, 10 lines) and the ordering (groups as first seen, primary → secondary → data order). Validity is **not** used when ordering, so the list never reshuffles.
- `src/Inspector.tsx` is one generic list. Every control of the kind is **always mounted**; each sits in a `Collapse` wrapper. Wrapper = `display: grid; grid-template-rows: 0fr → 1fr` plus `opacity 0 → 1`, both 160 ms ease-out. A group is one wrapper around its header and rows, so an empty group's header collapses too. The row's widget comes from `type` through one lookup table (`WIDGETS` in `src/widgets.tsx`).
- A collapsed wrapper gets `inert`, so it is out of the tab order and invisible to screen readers.
- Selection changes: `<Inspector key={item.id}>` remounts the list, so rows appear in their final state at once, no animation (rule 5). Values live per item in the store, so nothing is lost when you select away and back.

**What was easy:** animating height with `grid-template-rows` needs no measuring and no JS; rows below slide by themselves, nothing jumps. React's re-render on a store change is all the "validWhen" wiring there is. Both the hiding and the ordering come from the data, so there is no per-control code.
**What fought:** CSS cannot animate `height: auto`, so the rows have to stay mounted (and be made `inert`) — that is the one non-obvious trick. `overflow: hidden` on the wrapper clips focus rings (fixed with a 2 px inner margin). Native `<select>` is used for dropdowns (4+ options): its open list is the system's, not styled to match; a custom one would be more code. Playwright's own video recorder needed a download (see below), so the video is recorded from Chromium's screencast instead.

## Lines of code

| File | Lines |
|---|---|
| **Inspector (counted separately)** | |
| `src/Inspector.tsx` (generic list, collapse, row) | 52 |
| `src/widgets.tsx` (toggle, number, choice, colour, text) | 87 |
| `src/inspector.css` | 50 |
| *Inspector total* | *189* |
| **Rest of the screen** | |
| `src/App.tsx` (top bar, panels, project list, stand-ins, keys) | 81 |
| `src/CommandBar.tsx` | 51 |
| `src/logic.ts` (conditions + ordering) | 34 |
| `src/store.ts` (select / setValue / window.mock) | 36 |
| `src/types.ts`, `src/main.tsx`, `src/vite-env.d.ts` | 24 |
| `src/app.css` (tokens + shell look) | 74 |
| *Rest total* | *300* |
| `scripts/shoot.mjs` (build, serve, shoot, check, record) | 120 |

## npm packages

| Package | Version | Licence | Used for |
|---|---|---|---|
| react, react-dom | 19.3.1 | MIT | UI |
| vite | 8.3.5 | MIT | dev server and build |
| @vitejs/plugin-react | 6.1.2 | MIT | JSX in Vite |
| typescript | 7.0.2 | Apache-2.0 | type check (`tsc --noEmit`) |
| @types/react, @types/react-dom | 19.3.x | MIT | types |
| playwright | 1.64.1 | Apache-2.0 | headless Chromium for the shots |

`node_modules` is 94 MB with everything (Playwright 14 MB, Vite's bundler 21 MB, React 8 MB); the built app is 241 KB (73 KB JS gzipped). Nothing is downloaded at run time: Playwright's browser download was skipped (`PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` during install) and `shoot.mjs` points at the Chromium already on the machine (`ms-playwright\chromium-1243`; the package expects 1248, which worked fine). The package's video recorder needs `ffmpeg-1013` (a small download) and rejects the installed older one, so the video is made from Chromium's screencast frames at their real timestamps and joined with the `ffmpeg` on PATH.

## Attribution rows

| Component | Version | Licence | Source | Used in | Linking | Notes | Added |
|---|---|---|---|---|---|---|---|
| React / React DOM | 19.3.1 | MIT | https://github.com/facebook/react | proofs/gui-mock-web | bundled (proof only) | UI for the web mockup | 2026-10-21 |
| Vite, @vitejs/plugin-react | 8.3.5 / 6.1.2 | MIT | https://github.com/vitejs/vite | proofs/gui-mock-web | dev tool | build only | 2026-10-21 |
| TypeScript | 7.0.2 | Apache-2.0 | https://github.com/microsoft/typescript-go | proofs/gui-mock-web | dev tool | type check only | 2026-10-21 |
| Playwright | 1.64.1 | Apache-2.0 | https://github.com/microsoft/playwright | proofs/gui-mock-web | dev tool | screenshots / recording only | 2026-10-21 |

(The proof ships nothing; these are dev tools and a throw-away mockup. Their own dependencies were not audited one by one.)
