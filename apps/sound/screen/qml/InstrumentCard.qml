import QtQuick
import RostrumKit

// One instrument card: the track's name, what it is in plain words, and the generic inspector rows of its
// Instrument group (valid ones only; secondary behind the card's own More). Editing a control selects the
// card's track first, so the inspector shows the same item and the edit is one change on it.
Rectangle {
    id: card
    required property var model          // roles: id, name, what, controls, moreOpen
    readonly property bool selected: backend.selected === model.id
    implicitHeight: head.height + list.height + (voice.visible ? voice.height + Theme.gap : 0) + Theme.pad
    color: Theme.app
    radius: Theme.radiusPanel
    border.width: selected ? 1 : 0; border.color: Theme.accent

    function pick() { if (backend.selected !== model.id) backend.select(model.id) }

    MouseArea { id: headArea; x: 0; y: 0; width: parent.width; height: head.height; onPressed: card.pick() }
    Column {
        id: head
        x: Theme.pad; y: Theme.pad; width: parent.width - 2 * Theme.pad
        bottomPadding: Theme.gap
        spacing: 2
        Text { width: parent.width; text: card.model.name; elide: Text.ElideRight; color: Theme.fg
               font.family: uiFont; font.pixelSize: Theme.heading; font.weight: Font.DemiBold }
        Text { width: parent.width; text: card.model.what; elide: Text.ElideRight; color: Theme.fg3
               font.family: uiFont; font.pixelSize: Theme.body }
    }
    QtObject {   // what an InspectorRow calls on its "bridge": the card's track, not whatever is selected
        id: proxy
        readonly property bool moreOpen: card.model.moreOpen
        function setValue(p, v) { card.pick(); return backend.setValue(p, v) }
        function beginScrub(p) { card.pick(); backend.beginScrub(p) }
        function scrub(p, v) { card.pick(); backend.scrub(p, v) }
        function endScrub() { backend.endScrub() }
        function toggleMore() { instruments.toggleMore(card.model.id) }
    }
    Column {
        id: list
        x: Theme.pad; y: head.height + Theme.pad / 2; width: parent.width - 2 * Theme.pad
        Repeater {
            model: card.model.controls
            delegate: InspectorRow { bridge: proxy }
        }
    }
    VoiceLines {
        id: voice
        visible: card.model.isVoice
        x: Theme.pad; y: head.height + list.height + Theme.pad; width: parent.width - 2 * Theme.pad
        trackId: card.model.id; lines: card.model.lines; missing: card.model.missing
        status: card.model.voiceStatus; busy: card.model.voiceBusy; failed: card.model.voiceFailed
    }
}
