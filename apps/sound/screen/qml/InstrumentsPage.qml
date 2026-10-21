import QtQuick
import RostrumKit

// The Instruments page: a card per track that has an instrument, laid out in as many columns as fit.
Panel {
    id: page
    title: "Instruments"
    readonly property int cardMin: 320
    readonly property int columns: Math.max(1, Math.floor((width - 2 * bodyPad + Theme.gap) / (cardMin + Theme.gap)))

    Flickable {
        anchors.fill: parent
        contentHeight: flow.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Flow {
            id: flow
            width: parent.width
            spacing: Theme.gap
            Repeater {
                model: instruments.cards
                delegate: InstrumentCard { width: (flow.width - (page.columns - 1) * Theme.gap) / page.columns }
            }
        }
    }
    Text {
        visible: instruments.empty
        anchors.centerIn: parent
        text: "No instruments yet — add a track with Ctrl+K"
        color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.title
    }
}
