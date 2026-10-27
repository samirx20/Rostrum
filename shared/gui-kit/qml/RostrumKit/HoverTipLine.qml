import QtQuick
import QtQuick.Controls as QQC
import "."

// The line a HoverTip shows (HoverTip.qml makes it at the first rest on its control): the name, the help sentence and
// the key, under the control or, when it wraps, beside it; kept inside the window.
QQC.Popup {
    id: pop
    required property Item owner     // the HoverTip: its words, its control
    readonly property var win: parent ? parent.Window.window : null
    readonly property int most: win ? Math.min(560, win.width - 16) : 560
    readonly property int oneLine: 420        // a tip longer than this wraps and stands beside its control
    readonly property int wrapW: 300
    readonly property bool wraps: whole.advanceWidth > oneLine
    TextMetrics { id: nameBold; font.family: uiFont; font.pixelSize: Theme.label; font.bold: true; text: owner.text }
    readonly property real lineW: nameBold.advanceWidth + (owner.help ? whole.advanceWidth - nameBold.advanceWidth + 4 : 0)   // one line's width, measured: the Text's own implicitWidth would make its width depend on itself
    TextMetrics { id: whole; font.family: uiFont; font.pixelSize: Theme.label; text: owner.help ? owner.text + "  " + owner.help : owner.text }
    readonly property int side: {      // -1 left of the control, 1 right of it, 0 under it
        if (!wraps || !parent || !win || !visible) return 0
        const at = parent.mapToItem(null, 0, 0).x
        return at - width - 8 >= 8 ? -1 : at + parent.width + 8 + width <= win.width - 8 ? 1 : 0
    }
    y: {
        if (!isNaN(owner.atY)) return owner.atY
        if (!parent) return 0
        if (side === 0) return parent.height + 4
        const top = parent.mapToItem(null, 0, 0).y + (parent.height - height) / 2      // centred on the control, inside the window
        return Math.max(8, Math.min(win.height - 8 - height, top)) - parent.mapToItem(null, 0, 0).y
    }
    x: {
        if (!isNaN(owner.atX)) return owner.atX
        if (!parent) return 0
        if (side !== 0) return side < 0 ? -width - 8 : parent.width + 8
        const want = (parent.width - width) / 2
        if (!win || !visible) return want
        const at = parent.mapToItem(null, want, 0).x                  // keep the whole line inside the window
        return want + Math.max(8 - at, Math.min(0, win.width - 8 - (at + width)))
    }
    padding: 0
    focus: false
    closePolicy: QQC.Popup.NoAutoClose
    background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
    contentItem: Row {
        spacing: Theme.grid
        leftPadding: Theme.grid + 2; rightPadding: Theme.grid + 2; topPadding: 3; bottomPadding: 3
        Text {
            anchors.verticalCenter: parent.verticalCenter
            width: pop.wraps ? pop.wrapW : Math.min(Math.ceil(pop.lineW) + 2, pop.most - (keyHint.visible ? keyHint.width + Theme.grid : 0) - 2 * Theme.grid - 4)
            wrapMode: pop.wraps ? Text.WordWrap : Text.NoWrap
            elide: pop.wraps ? Text.ElideNone : Text.ElideRight; textFormat: Text.StyledText
            text: owner.help ? "<b>" + pop.esc(owner.text) + "</b>  " + pop.esc(owner.help) : pop.esc(owner.text)
            color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label
        }
        KeyHint { id: keyHint; visible: owner.key !== ""; text: owner.key.replace(/\+/g, " ")
                  anchors.verticalCenter: parent.verticalCenter }
    }
    // A line to read, never a target: a popup takes every press inside its own box, so a tip still up over the row
    // below (a number box's "Type a number" line, shown without a hover) ate the click meant for that row's box. Its
    // box holds no point (an empty mask), so the press goes through to what is under the line.
    readonly property Item noPoint: Item { width: 0; height: 0 }   // kept out of the line's Row
    Component.onCompleted: background.parent.containmentMask = pop.noPoint
    function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;") }
}
