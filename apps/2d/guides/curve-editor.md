# The curve editor

The curve editor shows how a value changes over time, as a line you can drag. Use it when the named eases (Linear, Ease in, Smooth ...) are not enough.

## 1. Open it

1. Select a layer that has animated settings (a setting with keys on it).
2. In the timeline's header row, over the layer names, click **Curves** in the **Keys | Curves** switch. The bars area turns into the curve view. The layer list stays on the left, and the ruler stays above, so the time scale and the playhead are the same.
3. Click **Keys** to go back.

If the layer has nothing animated, the view says "Select a layer with animated fields to see its curves".

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

You don't need the curve editor for a named ease. Select keys (in **Keys**, or by clicking in the curve view) and the **Key** block appears at the top of the settings panel:

- **Ease** list: **Linear**, **Ease in**, **Ease out**, **Smooth**, **Spring**, **Jump**, **Custom**. Every selected key changes. Right-click a key for the same list.
- With **Spring** picked, **Bounce** and **Speed** sliders appear.
- A small curve you can drag, **Time** and **Value** for a single key.
- The **⋯** menu: **After the last key** (Stay, Repeat, Back and forth, Carry on), and whether the canvas plays an ease once when you pick it.

Keys: **F9** Smooth, **Shift+F9** Ease in, **Ctrl+Shift+F9** Ease out, **Ctrl+Alt+J** Jump.
