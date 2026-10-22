# Voice lines: speaking with a voice track

**On the screen:** open the Library (Ctrl+L), double-click a voice ("Voice: Ryan"), and the Editor opens with
**Type what she says** beside it. Type the line and press Enter: it is placed at the playhead and spoken at once (the
first time, the voice model may ask to be downloaded). Select a line and click **Speak again** on the context bar for
another reading. The lines are listed beside the Editor; click one to change its words, time or level on the right.

**For agents:**

A voice track (`instrument: "voice"`, with `voice`, `language`, `style`) holds `lines`: words and a start time. Add them
with `line.add` (`text`, `at` as seconds, `{"beat": n}` or a marker such as `"#drop+0.5"`; `seed` = another take of the
same words), change with `line.set`, delete with `line.remove`.

The audio is not made by editing: call the `render_voice` tool (optional `ids`). It makes each missing take, one at a time (a
job: ask `inspect_job` if it did not finish), and answers per line with `file`, `seconds`, `generated` or cached, and
`start` / `end` in seconds, so the next line can be placed after this one. Then `render_mix` and listen with the look
tools. Rendering with an unmade line fails and names the line. Words, voice, style, language or seed changed = make again.
