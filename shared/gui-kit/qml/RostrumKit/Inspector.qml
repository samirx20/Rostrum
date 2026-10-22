import QtQuick
import "."

// The selected item's settings: ONE generic list of InspectorRow built from the item kind's field operation
// (bridge.rows). Nothing in here knows about cameras or lights.
Panel {
    id: panel
    property var bridge
    property bool keyMarks: false        // an app with keys: rows show key marks (see InspectorRow)
    title: "Inspector"

    Text { id: name; text: panel.bridge.selectedItem.label; color: Theme.fg; font.family: uiFont
           font.pixelSize: Theme.heading; font.weight: Font.DemiBold
           anchors.left: parent.left; anchors.right: parent.right; elide: Text.ElideRight }
    Text { id: kind; text: Theme.sentence(panel.bridge.selectedItem.kind); color: Theme.fg3; font.family: uiFont
           font.pixelSize: Theme.body
           anchors.top: name.bottom; anchors.topMargin: 2 }
    Flickable {      // a long inspector scrolls (wheel or touch, thin bar in the panel's margin); a short one never moves
        id: scroller
        objectName: "inspectorScroll"    // scripted steps scroll it (an app's `inspectorscroll` step)
        anchors { left: parent.left; right: parent.right; top: kind.bottom; bottom: parent.bottom; topMargin: Theme.gap }   // scrolled rows stop short of the subtitle
        contentHeight: list.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: list
            width: parent.width
            Repeater {
                model: panel.bridge.rows
                delegate: InspectorRow { bridge: panel.bridge; keyMarks: panel.keyMarks }
            }
        }
    }
    VScrollBar { flick: scroller }
}
