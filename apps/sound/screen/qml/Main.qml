import QtQuick
import RostrumKit

// RostrumSound: one workspace (apps/sound/DESIGN.md §2, shared/gui-kit/INTERACTION.md §1.1). Top bar: project-wide
// things only — ≡ (the menu), the song's name, the message and change count, the Loudness chip and Export once the
// song makes a sound, Search, Help. Centre: the arrangement, always, with its header strip (+ Add, ⏮ ▶, Record while
// armed, position, tempo · beats · key, zoom); under it the dock (Editor E / Mixer X; folds away). Left: the Library
// (Ctrl+L), pushing the arrangement on a wide window and floating over it below 1500 px. Right: the settings panel —
// the selection's settings, or the song while nothing is selected — or the Export sheet in its place (Ctrl+E).
// Saving is automatic: there is no Save and no question on closing.
AppShell {
    id: shell
    bridge: backend
    appName: "RostrumSound"
    documentName: backend.docName
    helpEntries: guides
    readonly property bool wide: width >= 1500                       // the Library pushes instead of floating
    readonly property bool hasTracks: backend.tracks.some(r => !r.mix)
    readonly property bool hasSound: backend.tracks.some(r => !r.mix && r.blocks.length > 0)
    leftWidth: wide && workspace.library ? (width >= 1920 ? 280 : 260) : 0
    rightWidth: width >= 1920 ? 320 : width >= 1646 ? 296 : width >= 1366 ? 264 : 256
    bottomHeight: -Theme.gap        // no full-width bottom panel: the dock sits under the arrangement only (kit request)

    function openFileMenu() { fileMenu.openMenu() }      // (the scripted `file-menu` step)
    function openSettings() { settingsPanel.open() }     // (`settings`: Preferences)
    function openSong() { arrangement.readout.open() }   // (`song-open`: the tempo / key popover)
    function openLibrary() { workspace.setLibrary(true) }   // (`library`)
    function openPicturePick() { backend.setPictureOpen(true); arrangement.picture.openItems() }     // (`picture-pick`)
    function openExport() { if (shell.hasSound) mixer.export.setDialogOpen(true) }
    function exportAgain() { if (shell.hasSound && !mixer.export.busy) mixer.export.start() }   // the last settings
    function used() { if (!shell.wide) workspace.setLibrary(false) }   // a narrow window's Library closes after use
    Shortcut { sequence: "Ctrl+N"; onActivated: fileMenu.newNow() }
    Shortcut { sequence: "Ctrl+O"; onActivated: fileMenu.openNow() }
    Shortcut { sequence: "Ctrl+S"; onActivated: fileMenu.saveNow() }
    Shortcut { sequence: "Ctrl+Shift+S"; onActivated: fileMenu.duplicateNow() }
    Shortcut { sequence: "Ctrl+I"; onActivated: arrangement.addFromFile() }
    Shortcut { sequence: "Ctrl+,"; onActivated: settingsPanel.open() }
    Shortcut { sequence: "Ctrl+Q"; onActivated: Qt.quit() }
    Shortcut { sequence: "Ctrl+E"; onActivated: shell.openExport() }
    Shortcut { sequence: "Ctrl+Shift+E"; onActivated: shell.exportAgain() }
    Shortcut { sequence: "Space"; onActivated: backend.togglePlay() }
    Shortcut { sequence: "Home"; onActivated: backend.setTime(0) }
    Shortcut { sequence: "Ctrl+L"; onActivated: workspace.toggleLibrary() }
    Shortcut { sequence: "E"; enabled: shell.hasTracks; onActivated: workspace.toggleDock("editor") }
    Shortcut { sequence: "X"; enabled: shell.hasTracks; onActivated: workspace.toggleDock("mixer") }
    Shortcut { sequence: "R"; enabled: recorder.armed !== ""; onActivated: recorder.toggleRecord() }
    Shortcut { sequences: [StandardKey.Delete, "Backspace"]; onActivated: backend.removeSelected() }
    Shortcut { sequences: ["Ctrl+=", "Ctrl++"]; onActivated: backend.zoomStep(1.25) }      // timeline zoom (screen state)
    Shortcut { sequence: "Ctrl+-"; onActivated: backend.zoomStep(0.8) }
    Shortcut { sequences: ["Ctrl+0", "Ctrl+9"]; onActivated: backend.fitView() }                  // show the whole song

    SoundKeys {}                    // the editing keys on the selection (nudge, pitch, copy / paste, Q, M …)
    leading: FileMenu { id: fileMenu; settingsPanel: settingsPanel; anchors.verticalCenter: parent.verticalCenter }
    SettingsPanel { id: settingsPanel }
    actions: [          // the top bar's chips, then Export (kit TopBar: its `actions` slot sits before Search)
        LoudnessReadout { visible: shell.hasSound; compact: shell.width < 1366; anchors.verticalCenter: parent.verticalCenter },
        Button { visible: shell.hasSound; text: "Export"; kind: "primary"; down: mixer.export.dialogOpen
                 anchors.verticalCenter: parent.verticalCenter
                 onClicked: mixer.export.setDialogOpen(!mixer.export.dialogOpen)
                 HoverTip { text: "Export the song (Ctrl+E). Ctrl+Shift+E exports again with the last settings"; hovered: parent.hovered } }
    ]
    left: Library { anchors.fill: parent; visible: shell.wide && workspace.library; onUsed: shell.used() }
    centre: [
        Arrangement {
            id: arrangement
            anchors { left: parent.left; right: parent.right; top: parent.top; bottom: dock.visible ? dock.top : parent.bottom
                      bottomMargin: dock.visible ? Theme.gap : 0 }
            headerWidth: shell.width >= 1920 ? 200 : shell.width >= 1646 ? 180 : shell.width >= 1366 ? 160 : 140
            compact: shell.width < 1366
            onAddTrack: workspace.setLibrary(true)
        },
        Dock {
            id: dock
            visible: shell.hasTracks
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            room: parent.height - 160 - Theme.gap        // the arrangement keeps the ruler and two tracks
            preferred: shell.width >= 1920 ? 460 : shell.width >= 1646 ? 380 : shell.width >= 1366 ? 320 : 300
        },
        Library {   // a narrow window: floats over the arrangement, closes after use
            visible: !shell.wide && workspace.library
            width: 260; z: 10
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
            onUsed: shell.used()
        }
    ]
    right: Item {
        anchors.fill: parent
        readonly property bool exporting: mixer.export.dialogOpen
        Inspector { visible: !parent.exporting && backend.selected !== ""; bridge: backend
                    anchors { left: parent.left; right: parent.right; top: parent.top; bottom: clean.top
                              bottomMargin: clean.visible ? Theme.gap : 0 } }
        SongSettings { visible: !parent.exporting && backend.selected === ""
                       anchors { left: parent.left; right: parent.right; top: parent.top; bottom: parent.bottom } }
        CleanTakeBar { id: clean; visible: !parent.exporting && mixer.cleaning.clip !== ""
                       anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: implicitHeight }
        ExportSheet { visible: parent.exporting; anchors.fill: parent }
    }
}
