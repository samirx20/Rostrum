import QtQuick
import RostrumKit

// "Clean up…" on clips (DESIGN.md §3.10, flow C): the Cleanup group opens in the panel and these three one-click presets
// sit in it: Dialogue only · Less noise · Less echo. A click turns that step on (or off) on every selected clip
// (backend.cleanSelected: one change) and starts the cleaned takes (mixer.cleaning.makeFor, the "Make cleaned take" job);
// the bar under them shows its progress and what the models need. Shown only after Clean up… (the fields below say the same).
Row {
    id: presets
    property bool wanted: false
    property var now: backend.cleanState()
    visible: wanted
    height: visible ? implicitHeight + Theme.gap : 0
    spacing: Theme.grid
    function toggle(which) {
        const s = backend.cleanState()
        const voice = which === "voice" ? !s.voice : s.voice, noise = which === "noise" ? !s.noise : s.noise,
              echo = which === "echo" ? !s.echo : s.echo
        if (backend.cleanSelected(voice, noise, echo)) mixer.cleaning.makeFor(backend.selectedIds)
    }
    Connections { target: backend; function onSelectionChanged() { presets.wanted = false } }
    Connections { target: backend; function onDocChanged() { presets.now = backend.cleanState() } }
    Button { text: "Dialogue only"; kind: "ghost"; down: presets.now.voice; onClicked: presets.toggle("voice") }
    Button { text: "Less noise"; kind: "ghost"; down: presets.now.noise; onClicked: presets.toggle("noise") }
    Button { text: "Less echo"; kind: "ghost"; down: presets.now.echo; onClicked: presets.toggle("echo") }
}
