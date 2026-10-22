import QtQuick
import "."

// A list: one chip per element (× removes it, while more than `minItems` remain) and "+ Add", a pick from the
// `choices` not already in it (absent when nothing is left to add or the list is full). Every change sends the
// whole new list (edited), so it is one operation. Chips wrap onto more lines; implicitHeight follows.
Flow {
    id: f
    property var values: []               // the list's elements (values)
    property var choices: []              // [{value, label}]: what may be added, and each element's words
    property int minItems: 0
    property var maxItems: null           // null = no limit
    signal edited(var values)
    spacing: Theme.grid

    function labelOf(v) { for (const c of choices) if (String(c.value) === String(v)) return c.label; return String(v) }
    readonly property var addable: choices.filter(c => !values.some(v => String(v) === String(c.value)))
    readonly property bool full: maxItems !== null && maxItems !== undefined && values.length >= maxItems

    Repeater {
        model: f.values
        delegate: Rectangle {
            required property var modelData
            required property int index
            readonly property bool removable: f.values.length > f.minItems
            height: Theme.field; radius: Theme.radiusCtl
            width: Math.min(f.width, chipText.implicitWidth + 2 * Theme.gap + (removable ? cross.width + Theme.grid : 0))
            color: chipArea.containsMouse && removable ? Theme.accentSoft : Theme.raised
            Text { id: chipText; x: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                   width: Math.min(implicitWidth, f.width - 2 * Theme.gap - 16); elide: Text.ElideRight
                   text: f.labelOf(modelData); color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont }
            Text { id: cross; visible: removable; anchors.right: parent.right; anchors.rightMargin: Theme.gap
                   anchors.verticalCenter: parent.verticalCenter; text: "×"; font.pixelSize: Theme.body
                   color: chipArea.containsMouse ? Theme.fg : Theme.fg3 }
            MouseArea { id: chipArea; anchors.fill: parent; hoverEnabled: true
                        cursorShape: removable ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: if (removable) f.edited(f.values.filter((_, i) => i !== index)) }
        }
    }
    ChoiceField {
        visible: f.addable.length > 0 && !f.full
        width: 96
        options: f.addable
        text: "+ Add"
        onPicked: (v) => f.edited(f.values.concat([v]))
    }
}
