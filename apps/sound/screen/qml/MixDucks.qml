import QtQuick
import RostrumKit

// A track's ducks on its strip: a chip per duck ("under melody", it opens that duck's panel) and "+ Duck" to dip this
// track under another one. Adding is duck.add; nothing here is a hand-made field.
Column {
    id: c
    property string ownerId: ""
    property var ducks: []
    property var targets: []              // [{id, name}]: the other tracks it could dip under
    property bool offer: true             // "+ Duck" shows (the strip's selected): ducks are rarer than effects and sends
    visible: ducks.length > 0 || (offer && targets.length > 0)
    spacing: Theme.grid
    Repeater {
        model: c.ducks
        delegate: MixChip {
            required property var modelData
            width: c.width; maxWidth: c.width; row: true
            text: modelData.label
            selected: mixer.ducks.panel.id === modelData.id
            onClicked: selected ? mixer.ducks.close() : mixer.ducks.select(modelData.id)
        }
    }
    MixPick {
        visible: c.offer && c.targets.length > 0
        width: parent.width; height: 22
        row: true; flat: true; text: "+ Dip under…"; tip: "Make this track dip whenever another one plays (a voice under music)"; choices: c.targets.map(t => ({ id: t.id, label: t.name }))
        onPicked: (id) => mixer.ducks.add(c.ownerId, id)
    }
}
