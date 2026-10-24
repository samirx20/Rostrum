import QtQuick
import RostrumKit

// One duck's panel: which tracks it dips under (a chip each; "+ Track" adds one) and its settings, the generic rows of
// the duck.set params (depth, attack, release, ...). Every change is a duck operation; a drag on a number is one step.
Column {
    id: d
    readonly property var panel: mixer.ducks.panel
    width: parent ? parent.width : 0
    spacing: Theme.gap
    QtObject {   // what an InspectorRow calls on its "bridge": this duck
        id: proxy
        readonly property bool moreOpen: mixer.ducks.moreOpen
        function setValue(p, v) { return mixer.ducks.setValue(p, v) }
        function beginScrub(p) { mixer.ducks.beginScrub(p) }
        function scrub(p, v) { mixer.ducks.scrub(p, v) }
        function endScrub() { mixer.ducks.endScrub() }
        function toggleMore() { mixer.ducks.toggleMore() }
    }
    Text {
        width: parent.width; elide: Text.ElideRight
        text: "Dips: " + (d.panel.trackName || ""); color: Theme.fg; font.family: uiFont
        font.pixelSize: Theme.title; font.weight: Font.DemiBold
    }
    Text { text: "Dips while these sound"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
    Flow {
        width: parent.width; spacing: Theme.grid
        Repeater {
            model: d.panel.under || []
            delegate: MixChip {
                required property var modelData
                readonly property bool removable: (d.panel.under || []).length > 1
                text: modelData.label + (removable ? "  ×" : ""); maxWidth: d.width
                onClicked: if (removable) mixer.ducks.removeUnder(modelData.id)
            }
        }
        MixPick {
            visible: (d.panel.addable || []).length > 0
            text: "+ Track"; choices: d.panel.addable || []
            onPicked: (id) => mixer.ducks.addUnder(id)
        }
    }
    Column {
        width: parent.width
        Repeater { model: mixer.ducks.controls; delegate: InspectorRow { bridge: proxy } }
    }
    Button { text: "Stop dipping"; kind: "ghost"; onClicked: mixer.ducks.remove() }
}
