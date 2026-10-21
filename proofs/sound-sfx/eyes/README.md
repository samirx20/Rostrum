# eyes — what a sound agent needs to know about a picture

A small command-line tool that lets a sound agent *see* the video before it
picks sounds. Every command prints one JSON line; errors go to stderr with exit code 2.
Run from `proofs/sound-sfx/` with the worktree venv:

```
python -m eyes motion <video> --outdir <dir>
python -m eyes frames <video> --at 1.4,5.6 [--window 2] [--step 2] [--motion <dir>/motion.json] --outdir <dir>
python -m eyes sheet  <video> --every 0.5 [--start 3 --end 6] [--cols 6] --out sheet.png
python -m eyes events <video> --events door_events.json --out event-sheet.png
```

| Command | Answers |
|---|---|
| `motion` | When does something move, how fast, where (box + centre, 4x8 grid), when does it stop or start suddenly (contact candidates, 1-frame precise), and when does the whole picture jump (`cuts`). Writes `motion.json` + `motion.png` (energy, speed, speed change, frame numbers). Farneback flow on 320-px grey frames, speeds in source px/frame. |
| `frames` | "What is actually touching what at this moment?" A strip of frames around each time (labelled frame + seconds), plus a zoom on the moving region when `--motion` is given. |
| `sheet` | The whole clip (or a part) as one contact sheet with time labels. |
| `events` | Checks a hand-written event sheet (required fields, force word, frame matches time) and draws it as one picture: a frame strip + the sound words per event. |

Libraries: OpenCV (Apache-2.0), numpy (BSD), scipy (BSD), matplotlib (PSF-style), Pillow not used.

## What the tool does NOT do
It finds *when* things move and shows frames. It cannot tell iron from brass or skin
from wood: the agent (or person) has to look at the frames and write the event sheet
(`door_events.json`: frame, time, objects, material, action, force, distance, what sound it implies, how sure).

## How the clip's times were checked
1. `motion` over the whole clip (510 frames, 25 fps) gave a speed trace and 94 stop/start candidates.
   They are noisy: the fast foreground arm and sleeve dominate the flow, so a small ring swing or a
   fingertip tap often produces no candidate. Candidates that matched a real contact:
   padlock release (f34-35), palm landing (f141-148), arm entering (f6-8), hand pulling away (f403-405).
   A palm landing at f237 and fingertip tap at f128 are **not** in the candidate list; they were found by eye.
   So: motion candidates are a pointer, not the answer.
2. Contact sheet every 0.12 s over seven 3-second segments, then 5-frame strips (2-frame step, 400 px tiles)
   around every candidate and every event, read by eye. Event frames are good to about +-1 frame
   where marked "high"; "medium" ones say why.
3. Each of the 27 events in `door_events.json` is drawn with 3-4 of its own frames in
   `event-sheet.png` so the sheet can be re-checked against the picture.

## Old event list (`proofs/sound/LIBRARIES.md` 4.1, 20 rows) vs the frames
- **Agreed within about 0.2 s (11 rows):** 1, 2, 4 (release and swing, but not "yanked"), 6 (resting, tiny), 7, 10, 12, 13, 14, 17, 19.
- **Wrong or materially off (8 rows):**
  - 3: the hand reaches the ring at 0.6 s, not 1.0 s.
  - 5: no palm landing at 2.0 s; the palm is already resting at 1.8 s, touchdown hidden behind the sleeve.
  - 8: "pushes hard, door flex" at 5.6 s: it is a soft flat palm landing (f140), and the door never flexes.
  - 9: "low wood groan": the door does not move; only cloth moves.
  - 11: hand takes the ring at 7.92 s, not 8.3-8.8.
  - 15: "steady wood creak 11.8-13.8": nothing happens, hands rest, padlock hangs nearly still.
  - 18: "hand hits ring, clank at 16.0": no hard hit; the big motion there is the framing change at f404 and the sleeve.
  - 20: ring and padlock are still by about 17.6 s, not slowly settling until 20.4 s.
- Row 16 (stillness at 14.0) is not still: hands resting, small shifts. Partly right.

## What is NOT happening on screen
The door never moves, flexes or opens (so no pitched creak); there is no heavy impact; the fast motions
are hands and sleeves very near the lens, which means soft cloth and skin sounds, not whooshes.
Details and per-event wording: `door_events.json`.

## Attribution rows
No new dependencies beyond libraries already in the worktree venv: OpenCV (opencv-python-headless, Apache-2.0), numpy (BSD-3), scipy (BSD-3), matplotlib (PSF-style). The test clip is private (Mixkit free licence) and stays out of the repo.
