# The curve editor

The curve editor shows how a value changes over time, as a line you can drag. Use it when the named eases (Linear, Ease in, Smooth ...) are not enough.

## 1. Open it

1. Select a layer that has animated settings (a setting with keys on it).
2. In the timeline's header row, over the layer names, click **Curves** in the **Keys | Curves** switch. The bars area turns into the curve view. The layer list stays on the left, and the ruler stays above, so the time scale and the playhead are the same.
3. Click **Keys** to go back.

The **Keys | Curves** switch is there only while the picked layer has an animated number. Pick a layer with nothing animated (or delete its last keys) and the timeline shows the keys again; pick an animated one and the curves come back.

## 2. Read it

- Each animated setting is a line in its own colour. The left side lists them with their lowest and highest value. Click a name to hide its line or show it again (faded name = hidden). Hide all but one to see it clearly. With one line, its highest and lowest value show at the right edge.
- Time goes left to right. Value goes bottom to top.
- A diamond is a key. A key that sits on a marker shows the marker's name above it.
- Before the first key and after the last, the line is faint: the value holds there.
- Round dots joined to a key by a thin line are **handles**. They show only for the keys you have selected, and only where the ease has them.

## 3. Change it

- **Move a key:** drag its diamond. Left and right change its time, up and down change its value. The time snaps to nearby things; hold **Ctrl** to move freely.
- **Change the ease:** click a key, then drag a round handle. The handles shape how the move leaves one key and arrives at the next. A named ease (such as Smooth) becomes **Custom** once you drag it.
- **Move the playhead:** click or drag on an empty part of the curve view.
- Each drag is one step. **Ctrl+Z** takes it back.

## 4. Change the ease without the curve

Pick a key (or the stretch between two keys; **Ctrl+Alt+A** picks every key of the picked layers) and open **Ease**: each ease shows its curve, and hovering one plays it on the canvas. The common ones have keys: **F9** Smooth, **Shift+F9** Ease in, **Ctrl+Shift+F9** Ease out, **Ctrl+Alt+J** Hold. **More** has the rest. Drag the small curve, or use the Curves tab, for your own.

**Ease** is the same button and list in three places: the **Key** block at the top of the settings panel (keys picked in **Keys** or in the curve view), a key's right-click, and the **Move** view (click the **bar between two keys**, not a diamond; **‹** or **Esc** goes back; see [first-animation.md](first-animation.md), section 6). The button shows the current ease and its curve: **Mixed** when the picked keys differ, **Custom** after its curve was dragged. With **Spring**, **Bounce** and **Speed** sliders appear under it. The Key block's **⋯** has **After the last key** (Stay, Repeat, Back and forth, Carry on) and whether the canvas plays an ease once when you pick it.
