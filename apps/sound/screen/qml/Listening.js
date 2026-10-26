.pragma library
// Solo and mute in plain words, one place for the top bar's "Solo on" chip and the Export sheet's warning
// (backend.listening: {solo: [names], mute: [names]}).
function names(list) {    // "Strings", "Strings and Piano", "Strings, Piano and Bass", "5 tracks"
    if (list.length <= 3) return list.length < 3 ? list.join(" and ") : list.slice(0, 2).join(", ") + " and " + list[2]
    return list.length + " tracks"
}
function chip(l) { return l.solo.length ? "Solo on: " + names(l.solo) : "" }
function soloLine(l) {
    return !l.solo.length ? "" : names(l.solo) + (l.solo.length === 1 ? " is soloed" : " are soloed") + ": the export holds only "
        + (l.solo.length === 1 ? names(l.solo) : "those")
}
function muteLine(l) {
    return !l.mute.length ? "" : names(l.mute) + (l.mute.length === 1 ? " is muted" : " are muted") + ": "
        + (l.mute.length === 1 ? "it is" : "they are") + " left out of the export"
}
