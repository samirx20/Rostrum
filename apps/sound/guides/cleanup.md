# Cleanup: dialogue, noise, reverb and stems

A clip keeps its original `media`; its cleanup fields describe a cleaned take it plays instead: `stem` (`none`,
`vocals`, `drums`, `bass`, `other`: play one stem), `isolate` (keep only the dialogue; absent while a stem is chosen),
`denoise` and `dereverb` (0..1, 0 = off), `useCleaned` (on by default; off plays the original; shown only while a step
is set). Set them with `clip.set`. Order: stem / isolate, then noise, then reverb.

The audio is not made by editing: call the `render_cleanup` tool (optional `ids`). It makes each missing take (a job: ask
`inspect_job` if it did not finish) and answers per clip with `media`, `file`, `generated` or cached and `steps`.
Rendering a clip whose take is not made fails and names the clip (`clip "<id>"'s cleaned take is not made yet`).

`clip.split_stems` on a clip adds four tracks (`<track> · vocals` … `other`), each with a copy of the clip playing one
stem, and sets the original clip's volume to 0; one undo step; a second split of the same clip fails. Then `render_cleanup`.

Hear it with `look_cleanup`: `clip` (its file vs its cleaned take, and its stems when made) or `before` + `after`
files, or `stems` (`{name: wav}`) with optional `reference` stems. It answers noise floor, speech level, their gap and
the reverb tail (dB fall in the 200 ms after the sound stops), the change after minus before, and for stems each
one's level, leakage between every pair and SDR against the references, with pictures. Full guide: apps/sound/CLEANUP.md.
