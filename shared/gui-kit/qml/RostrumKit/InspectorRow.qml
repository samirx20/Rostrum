import QtQuick
import "."

// One generic inspector row: a group header, a param, or the More row — nothing placed per control.
// The widget comes from the param's `type` only. The row owns its reveal: when `valid` changes, height and
// opacity ease over Theme.reveal (160 ms); the Column below just follows. A new selection builds fresh rows
// at their final state (a Behavior does not animate the first value), so the list swaps at once.
// With `keyMarks` (an app with keys) every param row keeps a gutter at the right for its key mark (model.anim):
// a filled diamond = a key at the playhead, outlined = animated, faint on hover only = could be animated.
// Clicking the mark is bridge.toggleAnimate (the app decides what that does).
Item {
    id: row
    required property var model           // roles from rostrum_gui.rows.ROLES
    property var bridge
    property bool keyMarks: false
    readonly property int gutter: keyMarks ? 22 : 0
    readonly property int full: model.row === "group" ? Theme.groupGap + Theme.rowDense
                              : model.row === "more" ? Theme.row + Theme.grid : Theme.row
    property real reveal: model.valid ? 1 : 0
    Behavior on reveal { NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }
    width: parent ? parent.width : 0
    height: Math.round(full * reveal)
    opacity: reveal
    visible: reveal > 0
    clip: reveal < 1

    Text {  // group header
        visible: row.model.row === "group"
        anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.bottomMargin: Theme.grid + 2
        text: row.model.label; color: Theme.fg3; font.family: uiFont
        font.pixelSize: Theme.label; font.weight: Font.DemiBold; font.letterSpacing: 0.3
    }
    Item {  // the More row (deep params live behind it)
        visible: row.model.row === "more"
        anchors.fill: parent
        Chevron { id: moreChev; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                  rotation: row.bridge.moreOpen ? 0 : -90; color: moreArea.containsMouse ? Theme.fg : Theme.fg3 }
        Text { anchors.left: moreChev.right; anchors.leftMargin: Theme.grid + 2; anchors.verticalCenter: parent.verticalCenter
               text: "More"; color: moreArea.containsMouse ? Theme.fg : Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont }
        MouseArea { id: moreArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: row.bridge.toggleMore() }
    }
    Item {  // a param: label column, then the widget
        visible: row.model.row === "param"
        anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
        height: Theme.row
        Text { id: label; width: Theme.labelColumn - Theme.gap; anchors.verticalCenter: parent.verticalCenter
               text: row.model.label; color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont; elide: Text.ElideRight }
        Loader {
            id: widget
            x: Theme.labelColumn
            anchors.verticalCenter: parent.verticalCenter
            width: row.model.type === "toggle" ? (item ? item.implicitWidth : 0) : parent.width - Theme.labelColumn - row.gutter
            height: Theme.field
            active: row.model.row === "param"
            sourceComponent: ({ toggle: toggle, number: number, choice: choice, color: colour, text: text })[row.model.type] || text
        }
        HoverHandler { id: rowHover }
        Item {  // the key mark
            visible: row.keyMarks && !!row.model.anim && (row.model.anim !== "still" || rowHover.hovered)
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            width: row.gutter - 4; height: Theme.field
            KeyMark { anchors.centerIn: parent; filled: row.model.anim === "onkey"
                      color: row.model.anim === "still" ? (markArea.containsMouse ? Theme.fg2 : Theme.fg4)
                           : markArea.containsMouse ? Theme.accentHover : Theme.accent }
            MouseArea { id: markArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: row.bridge.toggleAnimate(row.model.id) }
        }
    }

    function set(v) { bridge.setValue(model.id, v) }
    Component { id: toggle; Toggle { checked: !!row.model.value; onToggled: (v) => row.set(v) } }
    Component { id: number; NumberField {
        value: row.model.value === null || row.model.value === undefined ? 0 : row.model.value
        from: row.model.min === null || row.model.min === undefined ? -1e9 : row.model.min
        to: row.model.max === null || row.model.max === undefined ? 1e9 : row.model.max
        step: row.model.step ? row.model.step : 1
        unit: row.model.unit || ""
        onEdited: (v) => row.set(v)
        onScrubStarted: row.bridge.beginScrub(row.model.id)
        onScrubbed: (v) => row.bridge.scrub(row.model.id, v)
        onScrubEnded: row.bridge.endScrub() } }
    Component { id: choice; ChoiceField { options: row.model.options; current: row.model.value || ""; onPicked: (v) => row.set(v) } }
    Component { id: colour; ColorField { hex: row.model.value || "#000000"; onEdited: (v) => row.set(v) } }
    Component { id: text; TextField { value: row.model.value || ""; onEdited: (v) => row.set(v) } }
}
