import QtQuick
import RostrumKit

// Rostrum3D's part of the kit Export sheet (AppShell.exportSettings; the "What" list is This frame / The whole shot,
// screen3d/export3d.py): the file type.
Column {
    id: root
    readonly property var job: backend.exporter
    width: parent ? parent.width : 0
    spacing: Theme.grid
    Text { text: "File"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
    ChoiceField { width: parent.width; options: root.job.formats; current: root.job.format; onPicked: (v) => root.job.setFormat(v) }
}
