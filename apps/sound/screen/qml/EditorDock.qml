import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The Editor in the bottom dock: the selection's track up close (PianoRoll: notes, drum rows or clip waveforms) and,
// beside it, what the roll can't show for that track (editorSide): a voice track's lines and Make voice, a plug-in
// instrument's settings and its choice. These were the Instruments page's cards; they follow the Editor's track.
Item {
    id: e
    property Item barSlot: null          // the dock's tab row (Dock.qml): where the Editor's context bar sits
    readonly property var side: editorSide.track
    readonly property bool hasSide: side.isVoice || side.isPlugin
    PianoRoll {
        barSlot: e.barSlot
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom; right: e.hasSide ? panel.left : parent.right
                  rightMargin: e.hasSide ? Theme.gap : 0 }
    }
    Panel {
        id: panel
        visible: e.hasSide
        title: e.side.isVoice ? "Lines" : "Plug-in"
        width: Math.min(320, e.width * 0.35)
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
        Flickable {
            anchors.fill: parent; contentHeight: col.height; clip: true; boundsBehavior: Flickable.StopAtBounds
            Column {
                id: col
                width: parent.width; spacing: Theme.gap
                VoiceLines {
                    visible: e.side.isVoice; width: parent.width
                    trackId: e.side.id; lines: e.side.lines; missing: e.side.missing
                    status: e.side.voiceStatus; busy: e.side.voiceBusy; failed: e.side.voiceFailed
                }
                Loader {   // a plug-in track: its settings once one is chosen
                    id: plug
                    active: e.side.isPlugin; width: parent.width
                    readonly property bool chosen: !!item && item.info.chosen
                    sourceComponent: PluginSettings { ownerId: e.side.id; visible: info.chosen; height: visible ? implicitHeight : 0 }
                }
                Button {
                    id: choose
                    visible: e.side.isPlugin
                    text: plug.chosen ? "Change plug-in…" : "Choose plug-in…"; kind: "ghost"
                    onClicked: { mixer.plugins.scan(); instMenu.open() }
                    QQC.Popup {
                        id: instMenu
                        y: choose.height + 2; width: 220; padding: Theme.grid
                        background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
                        contentItem: PluginList {
                            width: instMenu.width - 2 * Theme.grid
                            choices: mixer.plugins.instruments
                            onPicked: (key) => { instMenu.close(); mixer.plugins.setInstrument(e.side.id, key) }
                        }
                    }
                }
            }
        }
    }
}
