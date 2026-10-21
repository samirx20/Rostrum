import QtQuick
import "."

// One row of the inspector: a group header, a control, or the More row. The widget comes from `type` only.
// Each row owns its reveal: `valid` goes false/true -> height and opacity ease 160 ms; the Column below just follows.
Item {
    id: row
    required property var model         // the roles of RowsModel
    property var doc
    readonly property int full: model.row === "group" ? Theme.groupGap + 16 : model.row === "more" ? 36 : Theme.row
    property real reveal: model.valid ? 1 : 0      // the initial value never animates (selection swaps at once)
    Behavior on reveal { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
    width: parent ? parent.width : 0
    height: full * reveal
    opacity: reveal
    visible: reveal > 0
    clip: reveal < 1

    function set(v) { doc.setValue(doc.selected, model.id, v) }

    Text {  // group header
        visible: row.model.row === "group"
        anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.bottomMargin: Theme.grid
        text: row.model.label; color: Theme.fg3; font.pixelSize: Theme.label; font.weight: Font.DemiBold
    }
    Item {  // More row
        visible: row.model.row === "more"
        anchors.fill: parent
        Text { anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
               text: (row.doc.moreOpen ? "⌄  " : "›  ") + "More"; color: moreHover.containsMouse ? Theme.fg : Theme.fg2; font.pixelSize: Theme.body }
        MouseArea { id: moreHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: row.doc.toggleMore() }
    }
    Item {  // control
        visible: row.model.row === "ctl"
        anchors.left: parent.left; anchors.right: parent.right; height: Theme.row
        Text { id: label; width: 96; anchors.verticalCenter: parent.verticalCenter; text: row.model.label
               color: Theme.fg2; font.pixelSize: Theme.body; elide: Text.ElideRight }
        Loader {
            id: widget
            anchors.left: label.right; anchors.verticalCenter: parent.verticalCenter
            readonly property bool wide: row.model.type === "choice" || row.model.type === "text"
            width: wide ? parent.width - label.width : item ? item.implicitWidth : 0   // fields fill, small widgets keep their size
            onLoaded: if (wide) item.width = Qt.binding(function() { return widget.width })
            active: row.model.row === "ctl"
            sourceComponent: { switch (row.model.type) {
                case "toggle": return toggle; case "number": return number; case "choice": return choice
                case "color": return color; default: return text } }
        }
    }
    Component { id: toggle; ToggleField { checked: row.model.value; onToggled: (v) => row.set(v) } }
    Component { id: number; NumberField { value: row.model.value; from: row.model.min; to: row.model.max
                                          step: row.model.step; unit: row.model.unit; onEdited: (v) => row.set(v) } }
    Component { id: choice; ChoiceField { options: row.model.options; current: row.model.value; onPicked: (v) => row.set(v) } }
    Component { id: color; ColorField { hex: row.model.value } }
    Component { id: text; TextBox { text: row.model.value; onEdited: (v) => row.set(v) } }
}
