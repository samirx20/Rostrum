import QtQuick
import "."

// A name (layer, track, clip, item, title): one line, shortened with "…" when it doesn't fit, and the whole name in a
// hover tip (INTERACTION.md Part 5). Used wherever a name is shown, so no screen has its own elide. A Text: set
// `text`, `width` (or anchors), and `color` / `font` as for any Text; `elide` is the end by default (a path: ElideMiddle).
Text {
    id: n
    property string tip: ""          // the tip's words when they differ from the name (default: the name itself)
    property string help: ""         // one plain sentence under the name in the tip
    color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
    elide: Text.ElideRight; maximumLineCount: 1
    HoverHandler { id: over }
    HoverTip { text: n.truncated || n.help ? (n.tip || n.text) : ""; help: n.help; hovered: over.hovered }
}
