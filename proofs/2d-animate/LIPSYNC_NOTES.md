# Lip sync proof — notes for the lead (draft, member "lipsync", H11)

**Question.** Can an agent, through MCP only, make the H10 character say a voice line with a mouth that reads, and can
a person then edit the mouth keys?

## What is here

- `lipsync_film.py`: the H10 character (copied from `proofs/2d-character/film.py`; legs, floor and walk left out), standing
  and talking: spine breathing, head nods, the near arm moves a little, two blinks. The rig is scaled 2.6× and framed
  waist-up (1920 × 1080, 30 fps, 6.5 s). Nine mouth shapes (`mouth_X` … `mouth_H`), each a group of 1–3 drawn paths
  (inside, teeth, tongue, lips), all bound to the neck bone so they follow the head. `lipsync(...)` keys them to line 1 of
  the voice-over: `vo.wav` 2.5–9.0 s (comp 0 = vo 2.5 s), words "Every city keeps one hour for itself.".
- `lipsync_calls.json`: `run_script` (this is the model run, once), `inspect_lipsync` (same clip: from the cache; the
  phone, word and mouth times), four `look_frame`s, a 24-frame `look_sheet` over 0.5–3.5 s, `render_video`.

## Run (the lead, under the GPU slot)

```
$env:ROSTRUM_ITEM = "talk"
pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: H11 lipsync proof" gpu C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\.venv\Scripts\python.exe C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\2d-animate\mcp_session.py C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\2d-animate\lipsync_calls.json
```

## Put the sound in (ffmpeg)

The render is silent. The clip is vo.wav from 2.5 s, 6.5 s long; the render's frame 0 is vo 2.5 s:

```
ffmpeg -y -i "C:\Users\Sam\.rostrum\waves\scratch\hem-H11-proof\project\renders\talk\v001\talk_talk.mp4" -ss 2.5 -t 6.5 -i "C:\Users\Sam\.rostrum\waves\results\stage2\sound-voice\voice-over-on-cue.stems\vo.wav" -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -shortest "C:\Users\Sam\.rostrum\waves\results\stage2\2d-animate\lipsync-talk.mp4"
```

(The render path is the project's `renders\<item>\v001\<item>_<comp>.mp4`, as in H10; check the `render_video` reply.)

## What to look at

- At 0.3 s: rest mouth (X), before the line (the voice starts at about vo 3.16 s = comp 0.66 s).
- The words, from the CPU check (vo time → comp time): "every" ɛ 3.16 → 0.66 s, "city" s 3.52 → 1.02 s, "keeps" k 4.14 →
  1.64 s (p, a closed mouth, at 4.44 → 1.94 s), "one" w 4.64 → 2.14 s, "hour" aʊ 5.02 → 2.52 s (wide). The rest of the
  line ("for itself.") is after 3 s of that check, so only the full run shows it.
- Watch the mp4 with sound: closed lips on the P of "keeps", wide on "hour", teeth on lip on the F of "for" and "itself",
  tongue up on its L, rest after the line.
- A person's edit: `edit_document` `key.set` on one mouth key (move its time), then re-run `run_script` with
  `lipsync_film.py`: the moved key stays (the merge holds it). Tested without the model in
  `apps/2d/python/tests/test_lipsync.py`.

## Checked by me

- The phone model ran on the CPU on vo.wav 2.5–5.5 s: 150 frames, 2.9–5.4 s. Free decoding heard
  `ɛ v ɹ i s ɪ ɾ i k iː p s w ʌ n aʊ ɚ`; forced alignment of "Every city keeps one hour" put the same sounds at the same
  frames (3.16 … 5.32 s).
- The script runs (with those phones stubbed in): 143 changes, keys on all nine mouths, the scene describes. **Not
  rendered, not looked at**: the mouth drawings and their size on screen are unchecked, as is the framing.

## Attribution rows

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| onnxruntime-directml | 1.24.4 | MIT | Rostrum2D lip sync (runs the phone model) | Python package, optional `lipsync` extra (68 MB) | yes | keep the licence notice | https://pypi.org/project/onnxruntime-directml/ |
| flatbuffers | 25.12.19 | Apache-2.0 | onnxruntime (dependency) | Python package (0.1 MB) | yes | keep the licence and NOTICE | https://pypi.org/project/flatbuffers/ |
| protobuf | 7.36.2 | BSD-3-Clause | onnxruntime (dependency) | Python package (2 MB) | yes | keep the licence notice | https://pypi.org/project/protobuf/ |
| sympy | 1.14.0 | BSD-3-Clause | onnxruntime (dependency) | Python package (29 MB) | yes | keep the licence notice | https://pypi.org/project/sympy/ |
| mpmath | 1.3.0 | BSD-3-Clause | sympy (dependency) | Python package (2 MB) | yes | keep the licence notice | https://pypi.org/project/mpmath/ |
| wav2vec2-lv-60-espeak-cv-ft (fp16 ONNX, onnx-community) | rev c69750f | Apache-2.0 | Rostrum2D lip sync (phone model) | model file loaded on demand, 632 MB | downloaded on demand | keep the licence notice | https://huggingface.co/onnx-community/wav2vec2-lv-60-espeak-cv-ft-ONNX |
| CMU Pronouncing Dictionary | 7479086 | BSD-2-Clause | Rostrum2D lip sync (English words → phones) | data file read at run time, 3.5 MB | downloaded on demand | keep the licence notice | https://github.com/cmusphinx/cmudict |

(The model and the dictionary were already on disk; whether they ship in the installer or download on first use is open.)
