import QtQuick
import "."

// The one Ease control (2D SPEC pro-workflows 3.7, mockup 3): the Key block, the Move view (and, through EaseList, a
// key's right-click) all show it. Closed: the current ease's small curve and its name ("Mixed" when the picked keys'
// eases differ, "Custom" after its curve was dragged). A click opens the one ease list (EaseList.qml): hovering a row
// plays it on the canvas (hovered), a click sets it (picked: one change). While the list is open the button and
// `shownEase` keep the ease from before the hover, so a hover moves nothing on the panel.
// `eases`: the rows (rostrum_gui/eases.py); `current`: the ease id ("" = Mixed).
FieldFrame {
    id: f
    objectName: "easePicker"
    property var eases: []
    property string current: ""
    property string held: ""                                    // the ease when the list opened
    readonly property bool opened: list.opened
    readonly property string shownEase: opened ? held : current
    readonly property var row: eases.find(e => e.id === shownEase) || null
    signal picked(string id)
    signal hovered(string id)
    function open() { held = current; list.current = current; list.open() }

    text: shownEase === "" ? "Mixed" : row ? row.label : shownEase === "custom" ? "Custom" : shownEase
    engaged: opened
    activeFocusOnTab: true
    Keys.onSpacePressed: open()
    Keys.onReturnPressed: open()
    leading: EaseIcon { visible: !!f.row; width: 22; height: 14; points: f.row ? f.row.curve : []; ink: Theme.fg }
    trailing: Chevron { open: f.opened }
    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { f.forceActiveFocus(); f.open() } }

    EaseList {
        id: list
        y: f.height + 2
        eases: f.eases
        onPicked: (id) => f.picked(id)
        onHovered: (id) => f.hovered(id)
    }
}
