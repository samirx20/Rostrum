import QtQuick
import "."

// The view control, bottom-right of the main view (INTERACTION.md 1.1 and 1.12): "Fit · 50 % ▾". The label is the
// view's own words (CanvasView.label: "Fit · 50 %" right after a fit, else "50 %"); click opens the same steps as the
// keys: Fit, 50 %, 100 %, 200 %, Zoom in, Zoom out, each with its key from the key map. A step already on is absent.
// `view`: the screen's CanvasView (rostrum_gui/canvasview.py). Anchor it yourself:
//     ViewControl { view: canvas; anchors { right: parent.right; bottom: parent.bottom; margins: Theme.gap } }
// Screen state only: nothing here is a change or an undo step.
Item {
    id: vc
    property var view: null
    readonly property string words: (view ? view.label : "") + " ▾"
    implicitHeight: Theme.button
    implicitWidth: label.implicitWidth + 2 * Theme.pad
    visible: !!view

    function openMenu() {
        menu.entries = view.menu()
        const p = vc.mapToItem(null, vc.width, 0)
        menu.openAt(p.x, p.y - 2)       // the control is at the bottom right: the menu flips up and left, its edge on the control's
    }

    Rectangle {
        anchors.fill: parent; radius: Theme.radiusCtl
        color: hover.hovered || menu.visible ? Theme.hover : Theme.raised
        border.color: Theme.popupEdge
    }
    Text {
        id: label
        anchors.centerIn: parent
        text: vc.words; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
        font.features: { "tnum": 1 }
    }
    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { onTapped: menu.visible ? menu.close() : vc.openMenu() }
    HoverTip { text: "View"; help: "Fit the whole picture, or pick a zoom."; hovered: hover.hovered && !menu.visible }
    ActionMenu {
        id: menu
        onPicked: (v) => vc.view.pick(v)
    }
}
