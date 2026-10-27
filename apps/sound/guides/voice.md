# Voice lines: speaking with a voice track

**On the screen:** open the Library (Ctrl+L), press **Add** on a voice ("Ryan"; a voice row has no preview, because it is made from a line you type), and the Editor opens with
**Type a line** beside it. Type the line and press Enter: it is placed at the playhead and spoken at once (the
first time, the voice model may ask to be downloaded). Select a line and click **Speak again** at the top of the settings panel for
another reading. The lines are listed beside the Editor; click one to change its words, time or level on the right.

**For agents:**

A voice track (`instrument: "voice"`, with `voice`, `language`, `style`) holds `lines`: words and a start time. Add them
with `line.add` (`text`, `at` as seconds, `{"beat": n}` or a marker such as `"#drop+0.5"`; `seed` = another take of the
same words), change with `line.set`, delete with `line.remove`.

The values, exactly as written (anything else is refused with this list):

- `voice`: `ryan` (English man, lively, rhythmic), `aiden` (English man, sunny, American), `vivian` (Chinese woman,
  bright), `serena` (Chinese woman, warm, gentle), `uncle_fu` (Chinese man, older, low), `dylan` (Chinese man, young,
  Beijing), `eric` (Chinese man, lively, Chengdu), `ono_anna` (Japanese woman, playful), `sohee` (Korean woman, warm).
  Every voice can speak every language; it sounds most natural in its own.
- `language`: `auto` (the default: from the words), `english`, `chinese`, `japanese`, `korean`, `german`, `french`,
  `russian`, `portuguese`, `spanish`, `italian`: whole words, not codes (`"en"` is refused).
- `style`: free words for how to say it ("calm, close to the mic", "excited"); empty = the voice's own way.

The audio is not made by editing: call the `render_voice` tool (optional `ids`). It makes each missing take, one at a time (a
job: ask `inspect_job` if it did not finish), and answers per line with `file`, `seconds`, `generated` or cached, and
`start` / `end` in seconds, so the next line can be placed after this one. Then `render_mix` and listen with the look
tools. **How long before it is made:** `render_voice` (`what: "estimate"`, optional `ids`, or just `text` and `language`) answers `estimated_seconds` with a range, e.g. "about 3.2 s (2.5-3.9)", and `ends_about`; a made line gives its exact `made_seconds`. Counted from syllables and pauses and measured on the real voice (17 takes: 13 % off on average): the same words come out 10-25 % faster or slower on another take, so leave that much room, then place the next line from the made `end`. Rendering with an unmade line fails and names the line. Words, voice, style, language or seed changed = make again.

The voice model is not installed with the app (about 1.9 GB). When it is missing, `render_voice` says so and names the
step: the `run_model_install` tool with model `voice` (a job; `inspect_job` shows how far it is). Two of its three files
are not published yet: until they are, the tool fails at once and names the files and the folder to copy them into. `render_voice` (`what: "words"`)
(each spoken word's start and end, for captions or placing a hit on a word) needs the speech model: model `speech`
(about 670 MB).
