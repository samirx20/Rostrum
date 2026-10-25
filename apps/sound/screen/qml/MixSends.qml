import QtQuick
import RostrumKit
import "MixFormat.js" as F

// A track's sends: its send to the master's reverb (the track's own "reverb" field), then one row per bus it feeds ("Reverb send" and its level, the slider under it), then "+ Send" while there is a
// bus it doesn't feed yet. Dragging selects the send first, so the drag is one change on it.
Column {
    id: c
    property string ownerId: ""
    property var sends: []
    property var targets: []              // [{id, name}]: the buses it could still send to
    property var reverb: null             // the track's send to the master's reverb, 0..1 (null: a bus, no such send)
    signal pick()                         // select the strip's track first, so the drag is one change on it
    visible: reverb !== null || sends.length > 0 || targets.length > 0
    spacing: Theme.grid
    Column {
        visible: c.reverb !== null
        width: c.width; spacing: 0
        Row {
            width: parent.width
            Text { width: parent.width - verbAmount.width; text: "Reverb send"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            Text { id: verbAmount; text: Math.round((c.reverb || 0) * 100) + " %"; color: Theme.fg2; font.family: uiFont
                   font.pixelSize: Theme.label; font.features: { "tnum": 1 } }
        }
        Slider {
            width: parent.width; implicitWidth: 10; height: 18
            from: 0; to: 1; step: 0.01; value: c.reverb || 0; defaultValue: 0
            onScrubStarted: { c.pick(); backend.beginScrub("reverb") }
            onScrubbed: (v) => backend.scrub("reverb", v)
            onScrubEnded: backend.endScrub()
            onEdited: (v) => { c.pick(); backend.beginScrub("reverb"); backend.scrub("reverb", v); backend.endScrub() }
        }
    }
    Repeater {
        model: c.sends.length             // a number, so a live drag's new values never rebuild the row under the pointer
        delegate: Column {
            required property int index
            readonly property var modelData: c.sends[index] || ({ id: "", name: "", level: 0 })
            width: c.width; spacing: 0
            Row {
                width: parent.width
                NameLabel { width: parent.width - amount.width; text: modelData.name + " send"; color: Theme.fg3
                            font.pixelSize: Theme.label }
                Text { id: amount; text: F.faderText(modelData.level); color: Theme.fg2; font.family: uiFont
                       font.pixelSize: Theme.label; font.features: { "tnum": 1 } }
            }
            Slider {
                width: parent.width; implicitWidth: 10; height: 18
                from: 0; to: 2; step: 0.01; value: modelData.level; defaultValue: 0.3      // a new send's own level (send.add)
                onScrubStarted: backend.beginScrubOn(modelData.id, "level")      // the send at once, the panel after the release
                onScrubbed: (v) => backend.scrub("level", v)
                onScrubEnded: backend.endScrubOn()
                onEdited: (v) => { backend.select(modelData.id); backend.beginScrub("level"); backend.scrub("level", v); backend.endScrub() }
            }
        }
    }
    MixPick {
        visible: c.targets.length > 0
        width: parent.width; height: 22
        row: true; flat: true; text: "+ Send"; tip: "Send part of this track to a group (a shared reverb, say)"; choices: c.targets.map(t => ({ id: t.id, label: t.name }))
        onPicked: (id) => mixer.addSend(c.ownerId, id)
    }
}
