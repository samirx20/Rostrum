import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Every kit control, in its states, on one page (for looking, not for the app). Local values only.
// demo/main.py --sheet calls stage() (opens one list) and hovers "hovered" before the screenshot. The third column
// is `engaged` (the look a field has while focused, scrubbed or open: the same `active` path).
QQC.ApplicationWindow {
    id: win
    visible: true
    width: 1040; height: 600
    color: Theme.app
    title: "RostrumKit — controls"
    readonly property int colW: 220
    function stage() { openChoice.open() }

    component Head: Text { color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold
                           font.capitalization: Font.AllUppercase; font.letterSpacing: 0.4; width: win.colW }
    component Name: Text { color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; width: 120; height: Theme.row
                           verticalAlignment: Text.AlignVCenter }

    Panel {
        anchors.fill: parent; anchors.margins: Theme.gap
        title: "Controls"
        Column {
            spacing: Theme.gap
            Row { spacing: Theme.groupGap; Item { width: 120; height: 1 } Head { text: "At rest" } Head { text: "Hover" } Head { text: "Focused / in use" } }
            Row { spacing: Theme.groupGap
                Name { text: "Number" }
                NumberField { width: win.colW; value: 50; from: 12; to: 200; unit: "mm"; onEdited: (v) => value = v; onScrubbed: (v) => value = v }
                NumberField { objectName: "hovered"; width: win.colW; value: 2.8; step: 0.1; unit: "f/" }
                NumberField { width: win.colW; value: 180; to: 360; unit: "°"; engaged: true } }
            Row { spacing: Theme.groupGap
                Name { text: "Text" }
                TextField { width: win.colW; value: "Hello"; onEdited: (v) => value = v }
                TextField { width: win.colW; value: ""; placeholder: "Layer name" }
                TextField { width: win.colW; value: "Launch film"; engaged: true } }
            Row { spacing: Theme.groupGap
                Name { text: "Choice" }
                ChoiceField { width: win.colW; options: ["Point", "Spot", "Area", "Sun"]; current: "Spot"; onPicked: (v) => current = v }
                ChoiceField { width: win.colW; options: ["Round", "Blades"]; current: "Round" }
                ChoiceField { id: openChoice; width: win.colW; options: ["Forward", "Backward", "Random"]; current: "Backward" } }
            Row { spacing: Theme.groupGap
                Name { text: "Colour" }
                ColorField { width: win.colW; hex: "#ffe2c4"; onEdited: (v) => hex = v }
                ColorField { width: win.colW; hex: "#4c8dff" }
                ColorField { width: win.colW; hex: "#ececec"; engaged: true } }
            Item { width: 1; height: 112 }   // room for the open list
            Row { spacing: Theme.groupGap
                Name { text: "Toggle" }
                Row { width: win.colW; spacing: Theme.groupGap
                    Toggle { checked: false; onToggled: (v) => checked = v }
                    Toggle { checked: true; onToggled: (v) => checked = v } } }
            Row { spacing: Theme.groupGap
                Name { text: "Slider" }
                Slider { width: win.colW; value: 0.35; onScrubbed: (v) => value = v; onEdited: (v) => value = v }
                Slider { width: win.colW; value: 0.7 } }
            Row { spacing: Theme.groupGap
                Name { text: "Button" }
                Row { spacing: Theme.gap
                    Button { text: "Render"; kind: "primary" }
                    Button { text: "Add layer" }
                    Button { text: "Cancel"; kind: "ghost" }
                    Button { text: "Commands"; hint: "Ctrl K" } } }
        }
    }
}
