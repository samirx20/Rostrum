import QtQuick
import RostrumKit

// The frame-by-frame buttons for the selected drawing layer. Only what applies at the playhead is there
// (painter.now: no "next" on the last drawing, no "new drawing" where one already starts). Each is one change;
// Alt+Left / Alt+Right / Alt+N / Alt+Up / Alt+Down / Alt+O are the same actions (Main.qml).
Row {
    id: tools
    readonly property var now: painter.now
    visible: painter.drawingId !== ""
    spacing: 2
    Button { kind: "ghost"; text: "Previous"; visible: tools.now.prev != null; onClicked: painter.goFrame(-1) }
    Button { kind: "ghost"; text: "Next"; visible: tools.now.next != null; onClicked: painter.goFrame(1) }
    Button { text: "New drawing"; visible: tools.now.exact === false; onClicked: painter.newFrame(false) }
    Button { kind: "ghost"; text: "New from this"; visible: tools.now.has === true && tools.now.exact === false
             onClicked: painter.newFrame(true) }
    Button { kind: "ghost"; text: "Clear"; visible: tools.now.has === true; onClicked: painter.clearDrawing() }
    Button { kind: "ghost"; text: "Hold longer"; visible: tools.now.canHold === true; onClicked: painter.holdBy(1) }
    Button { kind: "ghost"; text: "Hold shorter"; visible: tools.now.canShorten === true; onClicked: painter.holdBy(-1) }
    Button { kind: "ghost"; text: "Onion skin"; down: painter.onionOn; onClicked: painter.setOnion(!painter.onionOn) }
}
