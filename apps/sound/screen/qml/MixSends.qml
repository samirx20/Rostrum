import QtQuick
import RostrumKit
import "MixFormat.js" as F

// A track's sends: one small level slider per bus it feeds (labelled by the bus), then "+ Send" while there is a
// bus it doesn't feed yet. Dragging selects the send first, so the drag is one change on it.
Column {
    id: c
    property string ownerId: ""
    property var sends: []
    property var targets: []              // [{id, name}]: the buses it could still send to
    visible: sends.length > 0 || targets.length > 0
    spacing: Theme.grid
    Repeater {
        model: c.sends
        delegate: Column {
            required property var modelData
            width: c.width; spacing: 0
            Row {
                width: parent.width
                Text { width: parent.width - amount.width; text: modelData.name; elide: Text.ElideRight; color: Theme.fg3
                       font.family: uiFont; font.pixelSize: Theme.label }
                Text { id: amount; text: F.faderText(modelData.level); color: Theme.fg2; font.family: uiFont
                       font.pixelSize: Theme.label; font.features: { "tnum": 1 } }
            }
            Slider {
                width: parent.width; implicitWidth: 10; height: 18
                from: 0; to: 2; step: 0.01; value: modelData.level
                onScrubStarted: { backend.select(modelData.id); backend.beginScrub("level") }
                onScrubbed: (v) => backend.scrub("level", v)
                onScrubEnded: backend.endScrub()
            }
        }
    }
    MixPick {
        visible: c.targets.length > 0
        width: parent.width; height: 22
        text: "+ Send"; tip: "Send part of this track to a bus (a shared reverb, say)"; choices: c.targets.map(t => ({ id: t.id, label: t.name }))
        onPicked: (id) => mixer.addSend(c.ownerId, id)
    }
}
