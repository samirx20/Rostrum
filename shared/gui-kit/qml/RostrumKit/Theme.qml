pragma Singleton
import QtQuick

// Every look token of the kit, in one file: colours, type, spacing, sizes, radii, motion.
// Carried from the S1 proof (proofs/gui-qt/qml/Theme.qml): dark, Figma-simple, panels separated by
// background steps (not lines), one accent, a 4 px grid. Controls read only from here; nothing hard-codes a look.
QtObject {
    // colours: background steps, text, accent
    readonly property color app: "#141414"
    readonly property color panel: "#1c1c1c"
    readonly property color raised: "#262626"
    readonly property color hover: "#303030"
    readonly property color active: "#333333"
    readonly property color sunken: "#101010"       // viewer and timeline track wells
    readonly property color border: "#2e2e2e"
    readonly property color line: "#3a3a3a"         // field underline at rest
    readonly property color lineHover: "#5a5a5a"
    readonly property color fg: "#ececec"
    readonly property color fg2: "#a3a3a3"
    readonly property color fg3: "#8a8a8a"
    readonly property color fg4: "#5c5c5c"          // hints on dark wells
    readonly property color accent: "#4c8dff"
    readonly property color accentHover: "#6aa0ff"
    readonly property color accentSoft: Qt.rgba(76 / 255, 141 / 255, 1, 0.16)
    readonly property color danger: "#ff6b6b"
    readonly property color ok: "#4cc38a"
    readonly property color warn: "#f2b33d"
    readonly property color agent: "#a594f9"        // an agent's work: its chip dot, the 1 s outline on what it changed
    readonly property color agentSoft: Qt.rgba(165 / 255, 148 / 255, 249 / 255, 0.14)
    readonly property color snap: "#ff2fd0"         // what a drag snapped to (INTERACTION 1.11): the snap line and its name chip
    readonly property color snapText: "#ffffff"     // the name on the snap chip
    readonly property color scrim: Qt.rgba(0, 0, 0, 0.4)
    readonly property color popupEdge: Qt.rgba(1, 1, 1, 0.08)

    // type (pixel sizes); font families come from Python (uiFont / monoFont), picked from what the system has
    readonly property int label: 11
    readonly property int body: 12
    readonly property int title: 13
    readonly property int heading: 16

    // spacing on a 4 px grid
    // letter spacing in whole pixels only: Windows snaps each letter to a pixel, so a fractional spacing piles up and
    // opens a visible gap inside a word ("Trans form", "EXP ORT")
    readonly property int capsSpacing: 1  // headings in capitals (panel titles, dialog sections)
    readonly property int grid: 4
    readonly property int gap: 8          // between panels, inside fields
    readonly property int pad: 12         // inside panels
    readonly property int groupGap: 16

    // sizes
    readonly property int topBar: 40
    readonly property int header: 32      // panel header
    readonly property int row: 28         // inspector row
    readonly property int rowDense: 24    // lists
    readonly property int field: 24       // every field box (number, text, choice, colour)
    readonly property int button: 28
    readonly property int curveBox: 132     // the inspector's curve control (CurveField), a square
    readonly property int labelColumn: 104  // the label column's least width ("Shadow softness" fits)
    readonly property int keyGutter: 22     // the key-mark column at a settings row's right (an app with keys)
    readonly property int amountField: 64   // an amount's value box beside its slider ("−60.0 dB", "100 %")
    // a settings row's label column at this row width: 45 % (a 296 px panel fits "Keep inside the outline" on one line)
    function labelColumnFor(w) { return Math.max(labelColumn, Math.round(w * 0.45)) }
    readonly property int sidePanel: 280
    readonly property int timeline: 184
    readonly property int popupRow: 26
    readonly property int scrollWidth: 4  // the thin scroll bar

    // radii
    readonly property int radiusCtl: 6
    readonly property int radiusPanel: 8

    // motion
    readonly property int fast: 120       // hover and colour changes
    readonly property int reveal: 160     // a control appearing or leaving (height + opacity)
    readonly property int revealEasing: Easing.OutCubic
    readonly property real scrubPixels: 4 // mouse pixels per step when dragging a number

    // words as a person reads them: first letter up, the rest as written ("next stroke" → "Next stroke", never
    // "Next Stroke"; Font.Capitalize upper-cases every word)
    function sentence(t) { return t ? t.charAt(0).toUpperCase() + t.slice(1) : "" }
}
