# Styled words inside one text

One line of type, a few words of it in another colour, weight, size or opacity, each keyable. The words stay **one text
layer**: they flow, wrap, centre and type on as one line, and a person edits one text. Never split a sentence into
several texts placed side by side with `measure_text`: the spacing breaks the moment a font, size or word changes.

## Make runs

Give `body` as a list: plain strings, and `("words", {style})` pairs.

```python
line = text("line", body=["Ship it ", ("today", {"color": "#ffb020", "weight": 800}), ", not next week"],
            size=72, color="#f2f2f2")
```

A run's style takes `color`, `weight` (0 = the text's own), `scale` (the word grows on its baseline and takes the room it
needs: the words after it move along, and a centred line re-centres; a wrapped text, `boxWidth` set, draws its runs at
scale 1) and `opacity`. A run with no colour takes the text's. Up to 4 runs per text; more than
that is usually two lines, so make two texts in a `column`.

## Key a run

`text.run(words)` (or `text.run(1)`, by number) gives the run; key it like a layer, with the run's own field names.

```python
reveal = marker("reveal", 3)
word = line.run("today")
word.key("color", {reveal: "#f2f2f2", reveal + 0.3: "#ffb020"})              # colour lands on the marker
word.key("scale", {reveal: 1, reveal + 0.15: 1.15, reveal + 0.4: 1}, ease="easeOut")
```

Common moves, all plain keys:

- **Colour change on a cue**: key `color` from the text's colour to the new one at a marker.
- **Emphasis**: a short `scale` bump, or `weight` from 400 to 800 on a variable font. Both change the word's width, so
  the line re-flows: the words after it (and, on a centred line, the whole line) shift to make room.
- **Fade one word in last**: key the run's `opacity` from 0 while the rest is already there.

## Typing on with a styled word

Runs work with letter-by-letter animation (`letterDelay`): each letter plays the layer's keys later than the one before,
while a run's own keys play at the layer's time, so a colour keyed on a marker changes on the marker for the whole word.

```python
t = text("type", body=["Make it ", ("move", {})], size=80, letterDelay=0.05)
t.key("opacity", {0: (0, "hold"), 0.01: 1})                 # each letter pops on in turn: typing
t.run("move").key("color", {"#reveal": "#ffffff", "#reveal+0.25": "#38bdf8"})
```

`letterSplit="words"` makes it type word by word instead.

## In the document

A run is plain fields on the text, shown under "Styled words 1…4" in the inspector: `run1From` ≤ letter < `run1To`
(letters counted from 0 in `body`, line breaks included), `run1Color`, `run1Weight`, `run1Scale`, `run1Opacity`. A
person changing the body by hand keeps the letter numbers, so check the run still covers the right word (a script
re-run sets them again from the list).

## Check

`run_script` with `look: true`, then `look_frame` at the cue time at full width: is the right word styled, does the
line still sit where it should, is the coloured word readable on its background?
