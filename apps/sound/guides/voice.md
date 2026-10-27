# Voice lines: speaking with a voice track

**On the screen:** open the Library (Ctrl+L), press **Add** on a voice ("Ryan"; a voice row has no preview, because it is made from a line you type), and the Editor opens with
**Type a line** beside it. Type the line and press Enter: it is placed at the playhead and spoken at once (the
first time, the voice model may ask to be downloaded). Select a line and click **Speak again** at the top of the settings panel for
another reading. The lines are listed beside the Editor; click one to change its words, time or level on the right.

**For agents:**

*Words: a **voice line** is a spoken sentence on a **voice track** (`instrument: "voice"`). A **chord voicing** is how a chord's notes are spread (the script helper `voice(...)`, also written `chord_voicing(...)`; `inspect_guide 'writing-music-tools'`). This guide is only about spoken voice lines.*

**A worked call: a voice track with two lines.** A script can make the voice track, but spoken lines are written with the
operation `line.add`: `v.line(...)` in a script is not a thing (the error says so). Two steps:

1. `run_script`: `{"name": "song", "source": "tempo(96); length(bar(9))\nn = track('narrator', instrument='voice', voice='ryan', language='english', style='calm')"}`
   (or in `edit_document`: `{"op": "track.add", "args": {"id": "narrator", "instrument": "voice", "voice": "ryan"}}`).
2. `edit_document`: `{"ops": [{"op": "line.add", "target": ["narrator"], "args": {"text": "Welcome to the show.", "at": 1.0}}, {"op": "line.add", "target": ["narrator"], "args": {"text": "Here is how it works.", "at": 4.5}}]}`.

Then `render_voice` (each line's made `start` / `end`), and move the second line with `line.set` (`at` = the first line's `end`
+ the gap you want) if the estimate was off. **The gap between lines:** leave at least 0.3 s of silence after a line ends
(0.5 to 0.8 s when the picture needs the mouth to close, a gesture or a cut between the lines); lines placed edge to edge
run together and give lip sync nowhere to rest. Placing a line on a marker (`"at": "#drop+0.5"`) keeps it tied to the picture's shared markers.
**Music under the voice:** `duck.add` on the music track with `under: ["narrator"]` dips it for the whole line (short attack
and release; `voice` mode turns on by itself under a voice track); `inspect_guide 'mixing-to-delivery'`.

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
(about 670 MB). The program that runs it (sherpa-onnx, Apache-2.0, about 19 MB) installs itself the first time.

**On a busy computer** voice making, word listening and lip sync wait their turn: one model job runs at a time on the
computer, and each starts only when enough memory is free (voice about 2.5 GB). A job waits up to 5 minutes, saying
"waiting for memory" or "waiting for its turn", then fails plainly with what was free; ask again when other work is done
(`ROSTRUM_MODEL_WAIT_S` sets the wait).
