.pragma library
// A note's pitch move: "+3 semitones", "−1 semitone", "" for none
function semitones(n) {
    if (!n) return ""
    return (n < 0 ? "−" : "+") + Math.abs(n) + " semitone" + (Math.abs(n) !== 1 ? "s" : "")
}
