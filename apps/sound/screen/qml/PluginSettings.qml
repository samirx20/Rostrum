import QtQuick
import RostrumKit

// A plug-in's settings: the generic inspector rows of its scanned parameter list (the first few, the rest behind
// More), and "Open window" only when the plug-in has its own window. `ownerId` is the plug-in effect or the track.
// A slider drag is one change, written when it ends; the window's state is written when it closes.
Column {
    id: ps
    property string ownerId: ""
    readonly property var panel: mixer.plugins.panel(ownerId)
    readonly property var info: panel.info
    width: parent ? parent.width : 0
    spacing: Theme.gap
    Component.onCompleted: mixer.plugins.scan()      // the parameter list comes from the scan (once per session)

    QtObject {   // what an InspectorRow calls on its "bridge": this plug-in
        id: proxy
        property string dragged: ""
        property real draggedValue: 0
        readonly property bool moreOpen: ps.info.moreOpen
        function setValue(p, v) { return mixer.plugins.setParam(ps.ownerId, p, v) }
        function beginScrub(p) { dragged = p }
        function scrub(p, v) { dragged = p; draggedValue = v }
        function endScrub() { if (dragged !== "") mixer.plugins.setParam(ps.ownerId, dragged, draggedValue); dragged = "" }
        function toggleMore() { mixer.plugins.toggleMore(ps.ownerId) }
    }
    Text {
        width: parent.width; elide: Text.ElideRight
        text: ps.info.name + (ps.info.vendor ? "  ·  " + ps.info.vendor : "")
        color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
    }
    Text {
        visible: ps.info.missing; width: parent.width; wrapMode: Text.WordWrap
        text: "This plug-in isn't installed on this computer, so it is silent here. Its settings are kept."
        color: Theme.warn; font.family: uiFont; font.pixelSize: Theme.label
    }
    Button {
        visible: ps.info.hasWindow && !ps.info.windowOpen
        text: "Open window"; kind: "ghost"
        onClicked: mixer.plugins.openWindow(ps.ownerId)
    }
    Text {
        visible: ps.info.windowOpen; width: parent.width; wrapMode: Text.WordWrap
        text: "The plug-in's window is open. Close it to keep what you changed."
        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
    }
    Column {
        width: parent.width
        Repeater {
            model: ps.panel.controls
            delegate: InspectorRow { bridge: proxy }
        }
    }
}
