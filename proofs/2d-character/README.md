# Proof: a 2D character walk through MCP only (Team Hem, H10, 2026-10-21)

**Question.** Can an agent, using only the `rostrum-2d` MCP server, rig a simple character of its own (bones, IK legs,
pinned feet), animate a 2-second walk, and can a person's later edit survive the agent re-running its script?

**Verdict: pass with conditions.** Everything below went through MCP (`run_script`, `edit_document`, `look_frame`,
`look_sheet`, `look_rig`, `inspect_rig_motion`, `look_motion`, `render_video`). The walk reads as a walk, the planted feet
do not slide (0.0 px), the IK always reaches (gap 0), and a person's key edits stay after a re-run. Conditions: the
character is a plain flat figure (not film level) and one thing was missing from the environment (PySide6, below).

## Setup

- `mcp_session.py` starts `python -m rostrum2d.mcp --project … --item walk` over stdio (Python
  `C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\.venv\Scripts\python.exe`, project
  `C:\Users\Sam\.rostrum\waves\scratch\hem-H10-proof\project`), sends a list of tool calls and waits for jobs. A call can
  say `"source_file": "film.py"`, which the driver reads into the script text.
- `film.py` is the one script the agent ran (and re-ran): 1920 × 1080, 30 fps, 2 s.
  - **Character:** side view, ~580 px tall: head (face, hair), neck, torso, two arms, two legs (thigh, shin, foot). All from
    rounded rectangles (capsules, so joints overlap cleanly) and ellipses. Far-side arm and leg are darker and sit behind
    the torso in the layer order.
  - **Rig:** one rig layer (1920 × 1080, x 0, y 0, anchor 0 0, so rig px = comp px). 13 bones: hip (root), spine, neck,
    two arms (upper + lower), two legs (thigh, shin, foot). A bind for every picture. Rigid binds everywhere, **except the near
    arm: one picture with a bend bind** (`bone` upper arm, `bone2` forearm, `soft 34`).
  - **Walk:** IK on both shins (`bend clockwise`: knees fold forward). Foot targets keyed at lift, mid-swing and landing;
    `pin` keyed 1 / 0 with `hold`; hips travel with `moveX` (380 px/s, across 760 px) and bob with `moveY`; arms swing
    against the legs (FK keys, elbow bends more going forward); spine leans and the neck counter-rotates so the head stays level;
    the foot bone is keyed to stay flat on the floor, toe-down at lift, toe-up at landing (computed in the script from
    the same two-bone maths the engine uses). A soft shadow follows the body; floor marks show the travel.
- Calls: `build.json` (script + looks), `render.json` (mp4), `edit.json` / `edit2.json` (person's edit + re-runs). The
  full replies are kept as `build.out.txt`, `edit-run1.out.txt`, `edit2.out.txt`.

## Results (`C:\Users\Sam\.rostrum\waves\results\stage2\2d-character\`)

| File | What |
|---|---|
| `walk-2s.mp4` | the walk, 60 frames, H.264, 1920 × 1080 (copied from the project's `renders\walk\v001\walk_walk.mp4`: `C:\Users\Sam\.rostrum\waves\scratch\hem-H10-proof\project\renders\walk\v001\`) |
| `walk-2s.manifest.json` | that folder's `manifest.json` (frames 1001–1060, 30 fps, made by `agent:rostrum-2d`, history entry 1) |
| `walk-contact-sheet.png` | `look_sheet`: 12 frames over the 2 s |
| `walk-mp4-frames.png` | every 6th frame of the mp4 itself (checks the mp4 matches the look frames) |
| `walk-frame-0.0s.png`, `-0.5s.png`, `-1.0s.png`, `-1.5s.png` | `look_frame` stills |
| `walk-skeleton-0.5s.png` | `look_rig`: bones (yellow), IK targets (red cross; green square while pinned) over the art |
| `rig-motion-facts.json` | `inspect_rig_motion` on the finished walk (before the edit) |
| `edit-original-0.75s.png` | the walk at 0.75 s before the person's edit |
| `edit-before-rerun-0.75s.png` | after the person's edit, before the re-run: knee lifted higher |
| `edit-kept-after-rerun.png` | after re-running the script: same high knee, the edit is still there |
| `edit-kept-after-rerun-1.0s.png` | the landing frame after the re-run (foot lands where the person put it) |
| `rig-motion-facts-after-edit-rerun.json` | `inspect_rig_motion` after edit + re-run: no sliding, gap 0 |
| `rig-motion-facts-edit-too-big.json` | an earlier, larger edit that the tool flagged (see below) |

## The numbers (`inspect_rig_motion`, 60 frames)

| | near foot | far foot |
|---|---|---|
| largest IK gap | 0.0 px | 0.0 px |
| pinned spans (tip moved) | 0.0–0.467 s: 0.0 px; 1.0–1.467 s: 0.0 px | 0.5–0.967 s: 0.0 px; 1.5–1.967 s: 0.0 px |
| tip travelled | 786 px | 787 px |

Body travel is 760 px over the 2 s, while a planted foot stays at one comp-px spot: the pin works even though the
target keys and the hips both move during the span.

## The person's edit and the re-run

1. `edit_document` (as the GUI would): `value.set` on `near_foot_ik` — `targetY` at 0.75 s from 832 to 770 (knee lifts much
   higher) and `targetX` at 1.0 s from 1050 to 1030 (lands slightly shorter). Picture: `edit-before-rerun-0.75s.png`.
2. `run_script` with the same `film.py`: "0 changes", nothing held (the script itself had not changed since the keys were
   written). The edit is still there (`inspect_item near_foot_ik` shows `targetY` 770 and `targetX` 1030; `edit-kept-after-rerun.png`).
3. To prove the guard really works, the script was re-run with a *changed* lift (40 instead of 38, which changes the
   key the person edited): the reply says `31 change(s) applied, 1 held back to keep other people's work:
   near_foot_ik.targetY.k750.v: script says 830, kept 770 (agent:mcp, "Person: higher knee lift…")`. Running the original
   script again put the rest back, and the person's 770 / 1030 are still there; `inspect_rig_motion` still reports no slide.
4. A first, larger edit (landing at 1000 instead of 1050) made the tool report `near_foot_ik 1–1.4667 s (4.6 px)` sliding,
   gap 4.6: not a bug. Landing so close behind the hips means the foot, still planted, ends up farther behind the
   hips than the leg can reach (the leg is 260 px long), so the leg straightens and the tip falls short. The tool named it
   loudly; the smaller edit above stays reachable.

## What I saw (honest)

- **Reads well:** the stride and the stance/swing split. Planted feet stay put against the floor marks. Knees fold forward, no
  flips or gaps at knee, hip or ankle in any frame I looked at (0.0, 0.5, 0.75, 1.0, 1.5 s and the contact sheet). The head
  stays level with a small bob, the arms swing against the legs, the feet roll (toe-down at lift, heel first at landing).
- **The bend bind:** the near arm (one picture) bends smoothly at the elbow with a faint soft crease; no tearing. It reads a bit
  better than two rigid pieces would at the elbow because there is no overlap seam; the cost is one more setting (`soft`,
  `grid`) to think about. The far arm is rigid and hidden behind the torso, so I can't judge it.
- **Doesn't read as well:** the figure is stylised and simple (flat colours, no clothing folds, no hands). The near arm's
  top sits high at the neck, because the shoulder pivot is at the torso's top; moving the shoulder pivot (and torso shape) lower would look
  more natural. The walk is mechanical (the same cycle twice, the same arm angles): it is a rig proof, not a character piece.
- The mp4 matches the look frames (`walk-mp4-frames.png`).

## Timings (inside the MCP session, this laptop)

`run_script` 0.1 s (first build, 207 changes); `look_frame` 0.7–1.0 s; `look_rig` 0.7 s; `look_sheet` 1.3 s;
`inspect_rig_motion` (60 frames, 2 chains) 0.7–0.8 s; `render_video` 60 frames 2.6 s (inside the heavy lock, gpu slot 1).

## Bugs and gaps found

- **No bug in the rig code** (engine, binds, IK, pin, merge).
- **Environment gap, not a code bug:** `look_frame` and `look_sheet` failed in `team-hem\.venv` with
  `ModuleNotFoundError: No module named 'PySide6'` (`apps\2d\python\rostrum2d\mcp\sheet.py` imports it to scale and label
  pictures; `look_rig` doesn't use it). Fix I used: `uv pip install --python .venv\Scripts\python.exe PySide6-Essentials==6.12.0`
  (LGPL, in the worktree venv only, nothing in the repo changed). **Suggestion for Team Sam:** declare PySide6 in the 2D Python
  package's dependencies so a fresh venv has it.
- **Small wart:** after the person's edit the plain re-run says "0 changes, held: []", so a reader can't see that a person's
  keys are in the document; only a re-run that changes the same key names the held-back one. That is consistent (nothing
  conflicted), just quiet.
- `look_motion` ignores bone keys and reports `puppet: still (no keys)` for a rig that is fully animated. Misleading for
  an agent that relies on it after each script; `inspect_rig_motion` is the right tool for rigs.

## Not done

Nothing in the brief. Not tried: FK/IK `mix` blending, hands, an arm IK, a second rig. No tests were written (the brief is a proof, and
I did not check the rig module's own tests).

## Attribution rows

None: nothing new shipped. (PySide6-Essentials 6.12.0, LGPL, size not measured, was installed into the worktree venv for the look tools; it is
already the app's Qt binding.)
