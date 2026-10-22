import QtQuick
import RostrumKit

// The Before | After switch of a clip with a clean-up set (DESIGN.md §3.10 step 5): flips `useCleaned` on the selected
// clips (mixer.cleaning.flip = the Before / After action, H), one undo step, playback keeps going. Absent when the
// selection has no clean-up set (or its cleaned take isn't made yet and the original is the one playing).
Row {
    id: sw
    readonly property var state: mixer.cleaning.audition
    visible: state.show
    spacing: 2
    Repeater {
        model: [{ after: false, label: "Before" }, { after: true, label: "After" }]
        delegate: Rectangle {
            required property var modelData
            readonly property bool on: sw.state.after === modelData.after
            width: t.implicitWidth + 2 * Theme.gap; height: 22; radius: 4
            color: on ? Theme.accentSoft : ma.containsMouse ? Theme.hover : Theme.raised
            border.color: on ? Theme.accent : Theme.popupEdge
            Text { id: t; anchors.centerIn: parent; text: parent.modelData.label; color: parent.on ? Theme.fg : Theme.fg2
                   font.family: uiFont; font.pixelSize: Theme.label }
            MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: if (!parent.on) mixer.cleaning.flip() }
            HoverTip { text: "Hear the clip " + parent.modelData.label.toLowerCase() + " clean-up  H"; hovered: ma.containsMouse; pressed: ma.pressed }
        }
    }
}
