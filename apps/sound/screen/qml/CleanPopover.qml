import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// "Clean up…" on clips (DESIGN.md §3.10, flow C): Voice only · Less noise · Less echo, then Clean. Clean sets the steps
// on every selected clip (backend.cleanSelected: one change) and starts the cleaned takes in the background
// (mixer.cleaning.makeFor, the "Make cleaned take" job); its progress shows here and in the message line. When the
// chosen steps need models that aren't on this computer, one sentence says so (Clean then asks to download them).
QQC.Popup {
    id: pop
    property bool voice: true
    property bool noise: true
    property bool echo: false
    readonly property var job: mixer.cleaning
    readonly property string missing: job.missingWords(voice, noise, echo)
    width: 300
    padding: Theme.pad
    closePolicy: QQC.Popup.CloseOnEscape | QQC.Popup.CloseOnPressOutside
    background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
    contentItem: Column {
        spacing: Theme.gap
        Text { text: "Clean up " + backend.selectionWords; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.title }
        Row {
            spacing: Theme.grid
            Button { text: "Voice only"; kind: "ghost"; down: pop.voice; onClicked: pop.voice = !pop.voice }
            Button { text: "Less noise"; kind: "ghost"; down: pop.noise; onClicked: pop.noise = !pop.noise }
            Button { text: "Less echo"; kind: "ghost"; down: pop.echo; onClicked: pop.echo = !pop.echo }
        }
        Text { visible: pop.missing !== ""; width: pop.availableWidth; wrapMode: Text.WordWrap; text: pop.missing
               color: Theme.warn; font.family: uiFont; font.pixelSize: Theme.label }
        ModelDownload { width: pop.availableWidth; fetch: pop.job.download }
        Text { visible: text !== ""; width: pop.availableWidth; wrapMode: Text.WordWrap; text: pop.job.status
               color: text.indexOf("Error") === 0 ? Theme.danger : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
        Button {
            width: pop.availableWidth; kind: "primary"
            visible: !pop.job.busy && (pop.voice || pop.noise || pop.echo)
            text: "Clean"
            onClicked: if (backend.cleanSelected(pop.voice, pop.noise, pop.echo)) pop.job.makeFor(backend.selectedIds)
        }
        Button {
            width: pop.availableWidth; kind: "ghost"
            visible: pop.job.cancellable
            text: "Cancel the clean-up"
            onClicked: pop.job.cancel()
        }
    }
}
