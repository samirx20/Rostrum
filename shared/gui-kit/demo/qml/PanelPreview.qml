import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Look harness for the S36 panel pieces: the Inspector with its Effects row and right-click Reset, and two Popovers
// (one under a button, one at the window's corner). See panel_preview.py. Nothing here is an app.
QQC.ApplicationWindow {
    id: win
    visible: true; width: 1280; height: 720
    color: Theme.app
    property int escapes: 0
    property int closes: 0
    function popover(which) { (which === "edge" ? edge : under).openAt(which === "edge" ? edgeButton : underButton) }

    Inspector { x: Theme.gap; y: Theme.gap; width: Theme.sidePanel; height: parent.height - 2 * Theme.gap; bridge: backend; effects: true }

    Button { id: underButton; objectName: "underButton"; x: 400; y: 120; text: "Stagger…"; kind: "primary"; onClicked: under.openAt(underButton) }
    Button { id: edgeButton; objectName: "edgeButton"; anchors.right: parent.right; anchors.bottom: parent.bottom
             anchors.margins: Theme.gap; text: "Land a bar…"; kind: "primary"; onClicked: edge.openAt(edgeButton) }

    Popover {
        id: under
        title: "Stagger 3 layers with a rather long name that has to be shortened"
        focusItem: byField
        onEscaped: win.escapes++
        onClosed: win.closes++       // the app's handler runs beside the Popover's own (focus goes back)
        Row {
            spacing: Theme.grid
            Text { anchors.verticalCenter: parent.verticalCenter; text: "Each starts"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            NumberField { id: byField; width: 64; value: 2; from: 0; to: 600; step: 1; unit: " f" }
            Text { anchors.verticalCenter: parent.verticalCenter; text: "after the one before"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
        }
        Row {
            spacing: Theme.grid
            Text { anchors.verticalCenter: parent.verticalCenter; text: "Order"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            ChoiceField { width: 160; options: ["Top to bottom", "Bottom to top", "Random"]; current: "Top to bottom" }
        }
    }
    Popover {
        id: edge
        focusItem: bar
        Row {
            spacing: Theme.gap
            Text { anchors.verticalCenter: parent.verticalCenter; text: "Land which bar?"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            NumberField { id: bar; width: 64; value: 9; from: 1; to: 999; step: 1 }
            Button { text: "Land"; kind: "primary"; onClicked: edge.close() }
        }
    }
}
