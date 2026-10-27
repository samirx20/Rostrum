import QtQuick
import "."

// Minimise, maximise / restore and close, drawn by us at the right of the merged top bar (SHELL.md › Window frame),
// in Windows' own icon font and colours so they read as the system's. Minimise and close are plain clicks. Maximise,
// in a person's window (windowChrome.native), is Windows' own maximise button as far as the pointer goes (HTMAXBUTTON:
// the snap layouts show when the pointer rests on it): Qt gets no mouse events there, so its hover and press come from
// windowChrome. Offscreen and in a check's window it is a plain click too. Not in the Tab order (Windows' are not).
Row {
    id: wb
    readonly property Item minButton: minB
    readonly property Item maxButton: maxB
    readonly property Item closeButton: closeB
    readonly property rect maxRect: Qt.rect(maxB.x, maxB.y, maxB.width, maxB.height)   // in its own coordinates
    readonly property string iconFont: Qt.fontFamilies().indexOf("Segoe Fluent Icons") >= 0 ? "Segoe Fluent Icons"
                                                                                           : "Segoe MDL2 Assets"

    component WinButton: Item {
        id: btn
        property string glyph
        property string name
        property bool danger: false              // close: red under the pointer, white glyph
        property bool byWindows: false          // the pointer here belongs to Windows (HTMAXBUTTON): windowChrome says
        readonly property bool hovered: byWindows ? windowChrome.maxHovered : area.containsMouse
        readonly property bool pressed: byWindows ? windowChrome.maxPressed : area.pressed
        signal clicked()
        width: 46; height: wb.height
        Accessible.role: Accessible.Button; Accessible.name: btn.name
        Rectangle {
            anchors.fill: parent
            color: btn.danger ? (btn.pressed ? "#b0271a" : btn.hovered ? "#c42b1c" : "transparent")
                              : (btn.pressed ? "#292929" : btn.hovered ? "#2d2d2d" : "transparent")
        }
        Text {
            anchors.centerIn: parent
            text: btn.glyph; font.family: wb.iconFont; font.pixelSize: 10
            color: btn.danger && (btn.hovered || btn.pressed) ? "#ffffff" : windowChrome.active ? Theme.fg : Theme.fg4
        }
        MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; onClicked: btn.clicked() }
    }

    WinButton { id: minB; objectName: "windowMinimise"; name: "Minimise"; glyph: "\uE921"; onClicked: windowChrome.minimise() }
    WinButton {
        id: maxB; objectName: "windowMaximise"
        name: windowChrome.maximised ? "Restore" : "Maximise"
        glyph: windowChrome.maximised ? "\uE923" : "\uE922"
        byWindows: windowChrome.native
        onClicked: windowChrome.toggleMaximise()
    }
    WinButton { id: closeB; objectName: "windowClose"; name: "Close"; glyph: "\uE8BB"; danger: true; onClicked: windowChrome.close() }
}
