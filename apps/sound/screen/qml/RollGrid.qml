import QtQuick
import RostrumKit

// The piano roll's drawing (clicks on the notes are PianoRoll's): rows (one per key, darker for black keys, or one per
// drum), at the left a real keyboard (white and black keys, a C label on every octave; press a key to hear it, drag
// across to play each one: backend.playKey) or the drum names, the beat grid, and the track's notes, hits or clips
// (RollNotes.qml, painted).
// rowAt(y) is the one mapping from height to a key (MIDI number), a drum row, or 0 for clips. frame(n): rows high
// enough that n keys (the track's notes) fit the view, at least 7 px (PianoRoll calls it when it opens on a track).
Item {
    id: g
    property var roll
    property var blocks: []     // the roll's notes / hits / clips (sent apart from its layout)
    property var ruler
    property int keysWidth: 52
    property real viewHeight: 400
    property real scrollY: 0               // how far the view is scrolled: a row name shows only while its row is whole
    readonly property bool notes: roll.kind === "notes"
    readonly property int count: notes ? roll.hi - roll.lo + 1 : roll.kind === "drums" ? Math.max(1, roll.drums.length) : 1
    property int fitRows: 0
    function frame(n) { fitRows = n }
    readonly property real rowH: notes ? Math.max(viewHeight / count, fitRows > 0 ? Math.max(9, Math.min(16, viewHeight / (fitRows + 2))) : 12)
                               : roll.kind === "drums" ? Math.min(56, viewHeight / count) : viewHeight
    // a drum's stored name ("openHat", "kick") in words for the row: "Open hat", "Kick"
    function drumName(d) {
        if (!d) return ""
        var s = String(d).replace(/_/g, " ").replace(/([a-z])([A-Z0-9])/g, "$1 $2").toLowerCase()
        return s.charAt(0).toUpperCase() + s.slice(1)
    }
    function rowAt(y) { var i = Math.floor(y / rowH); return notes ? roll.hi - i : roll.kind === "drums" ? i : 0 }
    // The row names follow the key in force at the view's left edge: scrolling past a key change renames the keys.
    readonly property var rowKey: {
        var list = roll.rowNames, at = ruler.start + 1e-6, hit = list.length ? list[0] : ({ names: [], inKey: [] })
        for (var i = 0; i < list.length; i++) if (list[i].t <= at) hit = list[i]
        return hit
    }
    readonly property bool keyed: rowKey.inKey.indexOf(false) >= 0     // a key is in force (with none, every row is equal)
    readonly property var rowNames: rowKey.names
    readonly property int keyRoot: rowKey.root !== undefined ? rowKey.root : -1     // the key's root note (0 … 11), -1 with no key
    readonly property var rowInKey: rowKey.inKey       // false: outside the song's key there, the row is shaded darker
    function black(k) { return [1, 3, 6, 8, 10].indexOf(k % 12) >= 0 }
    height: count * rowH

    Repeater {   // rows and their names
        model: g.roll.kind === "audio" ? 0 : g.count
        delegate: Item {
            required property int index
            readonly property int key: g.roll.hi - index
            y: index * g.rowH; width: g.width; height: g.rowH
            Rectangle { x: g.keysWidth; width: parent.width - x; height: parent.height
                        color: g.notes && g.black(parent.key) ? Theme.app : "transparent" }
            Rectangle { x: g.keysWidth; width: parent.width - x; height: parent.height     // in the key: lighter; out: darker
                        visible: g.notes && g.keyed; color: g.rowInKey[parent.index] ? Theme.raised : "black"
                        opacity: g.rowInKey[parent.index] ? 1 : 0.75 }   // a clear step between the two
            Rectangle { x: g.keysWidth; width: parent.width - x; height: 1; y: parent.height - 1
                        visible: g.notes ? parent.key % 12 === 0 : true; color: Theme.border }
            Item {   // the keyboard: a white key, or a black one over the white behind it
                visible: g.notes; width: g.keysWidth - 2; height: parent.height
                readonly property bool down: g.downKey === parent.key
                readonly property bool lit: down || g.hoverKey === parent.key
                Rectangle { anchors.fill: parent; color: !g.black(parent.parent.key) && parent.down ? Theme.accent
                                                        : !g.black(parent.parent.key) && parent.lit ? "#f2f2f2" : "#d6d6d6" }
                Rectangle {   // the line between two white keys that touch: B | C and E | F
                    visible: [0, 5].indexOf(parent.parent.key % 12) >= 0
                    width: parent.width; height: 1; y: parent.height - 1; color: "#8a8a8a" }
                Rectangle {   // behind a black key, the line between its two white keys
                    visible: g.black(parent.parent.key)
                    width: parent.width; height: 1; y: Math.floor(parent.height / 2); color: "#8a8a8a" }
                Rectangle {   // a black key: shorter, over the line between its two white keys
                    visible: g.black(parent.parent.key)
                    width: Math.round(parent.width * 0.6); height: parent.height; radius: 2
                    color: parent.down ? Theme.accent : parent.lit ? "#3a3a3a" : "#161616" }
                Text {   // C on every octave (C4 = middle C); the key under the pointer says its name
                    readonly property int k: parent.parent.key
                    z: 1
                    visible: (k % 12 === 0 || parent.lit) && g.rowH >= 7
                             && parent.parent.y >= g.scrollY - 1 && parent.parent.y + parent.parent.height <= g.scrollY + g.viewHeight + 1
                    anchors { right: parent.right; rightMargin: 4; verticalCenter: parent.verticalCenter }
                    text: k % 12 === 0 ? "C" + (Math.floor(k / 12) - 1) : (g.rowNames[parent.parent.index] || "")
                    color: g.black(k) ? "#e6e6e6" : "#3c3c3c"
                    font.family: uiFont; font.pixelSize: Math.min(Theme.label - 1, Math.max(9, g.rowH)); font.features: { "tnum": 1 }
                    font.weight: k % 12 === 0 ? Font.DemiBold : Font.Normal
                }
                Rectangle {   // the key's root (the song's key there): an accent tick at the keys' inner edge
                    visible: g.keyRoot === parent.parent.key % 12
                    x: parent.width - 3; width: 3; height: parent.height; color: Theme.accent }
            }
            Rectangle { visible: !g.notes; width: g.keysWidth - 6; height: parent.height - 1; color: Theme.panel }
            Text {   // a drum's name
                visible: !g.notes && parent.y >= g.scrollY - 1 && parent.y + parent.height <= g.scrollY + g.viewHeight + 1
                x: Theme.gap; width: g.keysWidth - Theme.gap - 6; height: parent.height     // fits its row: a short row
                verticalAlignment: Text.AlignVCenter; fontSizeMode: Text.Fit; minimumPixelSize: 7  // shrinks the name
                elide: Text.ElideRight
                text: g.drumName(g.roll.drums[parent.index]); color: Theme.fg3
                font.family: uiFont; font.pixelSize: Theme.label
            }
        }
    }
    property int hoverKey: -1
    property int downKey: -1
    MouseArea {   // the keyboard plays: press a key, or drag across the keys
        visible: g.notes; width: g.keysWidth - 2; height: g.height
        hoverEnabled: true; preventStealing: true; cursorShape: Qt.PointingHandCursor
        onPositionChanged: (m) => {
            g.hoverKey = g.rowAt(m.y)
            if (pressed && g.hoverKey !== g.downKey) { g.downKey = g.hoverKey; backend.playKey(g.downKey) }
        }
        onExited: g.hoverKey = -1
        onPressed: (m) => { g.downKey = g.rowAt(m.y); backend.playKey(g.downKey) }
        onReleased: g.downKey = -1
        onCanceled: g.downKey = -1
    }
    BeatGrid { x: g.keysWidth; width: g.width - x; height: g.height; ruler: g.ruler; opacity: 0.8 }

    RollNotes { grid: g; x: g.keysWidth; width: g.width - x; height: g.height }   // the notes, hits and clips (painted)
}
