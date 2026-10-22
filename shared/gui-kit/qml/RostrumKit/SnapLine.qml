import QtQuick
import "."

// What a drag snapped to (INTERACTION.md 1.11): a thin magenta line across the view, with the caught thing's name
// ("logo lands", "playhead") in a small chip at the line's top or left end. The one snap look in every app. Put it
// over the view and bind it to a DragView (rostrum_gui/drag.py): `at` = view.lineAt, `name` = view.lineName,
// `vertical` = view.vertical, visible = view.caught. A vertical line runs top to bottom of the parent at x = `at`;
// otherwise left to right at y = `at`. `from` / `to` limit its span (px along it; both 0 = the parent's whole side).
Item {
    id: line
    property real at: 0
    property string name: ""
    property bool vertical: true
    property real from: 0
    property real to: 0
    readonly property color magenta: "#ff2fd0"     // 1.11's snap colour (Theme has no token for it yet)
    readonly property real span: to > from ? to - from : (vertical ? parent.height : parent.width)
    z: 999
    x: vertical ? Math.round(at) : (to > from ? from : 0)
    y: vertical ? (to > from ? from : 0) : Math.round(at)
    width: vertical ? 1 : span
    height: vertical ? span : 1

    Rectangle { anchors.fill: parent; color: line.magenta }

    Rectangle {                                    // the name, kept inside the parent
        id: chip
        visible: line.name !== ""
        width: Math.min(words.implicitWidth + 2 * Theme.grid, 200); height: words.implicitHeight + 2
        radius: 3
        color: line.magenta
        x: line.vertical ? Math.min(2, line.parent.width - line.x - width) : 2
        y: line.vertical ? 2 : (line.y > height + 2 ? -height - 1 : 2)
        Text {
            id: words
            anchors.centerIn: parent
            width: parent.width - 2 * Theme.grid
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            text: line.name
            color: "#ffffff"; font.family: uiFont; font.pixelSize: Theme.label
        }
    }
}
