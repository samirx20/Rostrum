import QtQuick
import RostrumKit

// The song's key in one field ("A minor"), set in one click (production round 1, hand #5: a tonic field then a mode
// field wrote "A major" first and needed a second click for Minor). Click (or Space / Return) opens a grid: one row
// per pitch C … B, a Major column and a Minor column, each spelled the usual way for its mode (Db major, C# minor);
// the key playing now is filled. One click sets tonic and mode together and closes. ↑ ↓ ← → move, Return picks, Esc
// closes. The other modes (Dorian … Locrian) are one more click away: "Other modes" at the bottom turns the grid to
// their five columns ("Major and minor" turns it back). "No key" is the first row while the song has none.
FieldFrame {
    id: f
    property string key: ""                // "A minor", "" for none
    property bool compact: false           // a short field: "A min"
    signal picked(string tonic, string mode)
    readonly property string tonic: key.split(" ")[0]
    readonly property string mode: key.split(" ")[1] || ""
    readonly property var majors: ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    readonly property var minors: ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]
    readonly property var plain: ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    readonly property var others: ["dorian", "phrygian", "lydian", "mixolydian", "locrian"]
    function cap(m) { return m.charAt(0).toUpperCase() + m.slice(1) }
    function pc(t) {                       // the pitch class of a tonic ("C#" 1, "Bb" 10), -1 for none
        if (!t) return -1
        const base = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }[t.charAt(0).toUpperCase()]
        if (base === undefined) return -1
        return (base + (t.slice(1) === "#" ? 1 : t.slice(1) === "b" ? -1 : 0) + 12) % 12
    }
    readonly property int nowPc: pc(tonic)
    readonly property bool otherNow: others.indexOf(mode) >= 0
    text: key === "" ? songPanel.noKey : compact ? tonic + " " + cap(mode).slice(0, 3) : tonic + " " + mode
    engaged: pop.opened
    activeFocusOnTab: true
    Keys.onSpacePressed: open()
    Keys.onReturnPressed: open()
    trailing: Chevron { open: pop.opened }
    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { f.forceActiveFocus(); f.open() } }

    function open() {
        pop.other = otherNow
        pop.row = nowPc >= 0 ? nowPc : (key === "" ? -1 : 0)
        pop.col = otherNow ? others.indexOf(mode) : mode === "minor" ? 1 : 0
        pop.open()
    }
    function pick(row, col) {
        pop.close()
        if (pop.other) f.picked(plain[row], others[col])
        else f.picked(col === 1 ? minors[row] : majors[row], col === 1 ? "minor" : "major")
    }

    SmallPopup {
        id: pop
        objectName: "keyPicker"
        ownKeys: ["Up", "Down", "Left", "Right", "Enter"]
        property bool other: false         // the grid shows the other modes' five columns
        property int row: 0                // the cell ↑ ↓ ← → stand on: a pitch 0 … 11; -1 "No key"; 12 the bottom row
        property int col: 0
        readonly property int cols: other ? 5 : 2
        readonly property real cellW: other ? 208 / 5 : 104      // the same width either way: the popup never moves under the pointer
        readonly property real cellH: 22
        y: f.height + 2
        padding: Theme.grid; margins: Theme.gap
        focus: true
        background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
        onOpened: grid.forceActiveFocus()
        contentItem: Column {
            id: grid
            focus: true
            spacing: 0
            Keys.onUpPressed: pop.row = pop.row === 12 ? 11 : Math.max(f.key === "" && !pop.other ? -1 : 0, pop.row - 1)
            Keys.onDownPressed: pop.row = Math.min(12, pop.row + 1)
            Keys.onLeftPressed: pop.col = Math.max(0, pop.col - 1)
            Keys.onRightPressed: pop.col = Math.min(pop.cols - 1, pop.col + 1)
            Keys.onReturnPressed: grid.enter()
            Keys.onEnterPressed: grid.enter()
            function enter() {
                if (pop.row === 12) { pop.other = !pop.other; pop.col = Math.min(pop.col, pop.cols - 1) }
                else if (pop.row >= 0) f.pick(pop.row, pop.col)
                else pop.close()           // "No key": nothing to set (a key, once chosen, is changed, never removed here)
            }
            Row {   // the column heads, once
                height: 20
                Repeater {
                    model: pop.other ? f.others.map(m => f.cap(m).slice(0, 3)) : ["Major", "Minor"]
                    Text { width: pop.cellW; height: 20; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                           text: modelData; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
                }
            }
            Rectangle {   // "No key": the first row while the song has none (where the grid's ↑ ends)
                visible: f.key === "" && !pop.other
                width: pop.cols * pop.cellW; height: pop.cellH; radius: Theme.radiusCtl
                color: pop.row === -1 || noneHover.containsMouse ? Theme.hover : Theme.accentSoft
                Text { anchors.centerIn: parent; text: songPanel.noKey; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
                MouseArea { id: noneHover; anchors.fill: parent; hoverEnabled: true; onClicked: pop.close() }
            }
            Repeater {
                model: 12
                Row {
                    id: line
                    required property int index
                    Repeater {
                        model: pop.cols
                        Rectangle {
                            id: cell
                            required property int index
                            readonly property string word: pop.other ? f.plain[line.index] : index === 1 ? f.minors[line.index] : f.majors[line.index]
                            readonly property bool now: f.nowPc === line.index && (pop.other ? f.mode === f.others[index]
                                                                                              : f.mode === (index === 1 ? "minor" : "major"))
                            readonly property bool aimed: pop.row === line.index && pop.col === index
                            objectName: "key_" + word + "_" + (pop.other ? f.others[index] : index === 1 ? "minor" : "major")
                            width: pop.cellW; height: pop.cellH; radius: Theme.radiusCtl
                            color: now ? Theme.accent : hover.containsMouse || aimed ? Theme.hover : "transparent"
                            border.width: aimed && !hover.containsMouse ? 1 : 0; border.color: Theme.lineHover
                            Text { anchors.centerIn: parent; text: cell.word; font.family: uiFont; font.pixelSize: Theme.body
                                   color: cell.now ? Theme.app : Theme.fg }
                            MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: f.pick(line.index, cell.index) }
                        }
                    }
                }
            }
            Rectangle { width: pop.cols * pop.cellW; height: 1; color: Theme.line }
            Rectangle {   // the other modes, one click away (and back)
                objectName: "keyOtherModes"
                width: pop.cols * pop.cellW; height: pop.cellH + 2; radius: Theme.radiusCtl
                color: pop.row === 12 || otherHover.containsMouse ? Theme.hover : "transparent"
                Text { x: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                       text: pop.other ? "Major and minor" : "Other modes"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
                MouseArea { id: otherHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: { pop.other = !pop.other; pop.col = Math.min(pop.col, pop.cols - 1) } }
            }
        }
    }
}
