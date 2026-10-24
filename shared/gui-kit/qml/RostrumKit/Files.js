.pragma library

// A picture's path (C:\…\a.png, /c/…) or url as a url an Image can load ("" stays "").
function url(path) {
    const p = String(path || "")
    if (p === "") return ""
    return /^[a-z]{2,}:/i.test(p) ? p : "file:///" + p.replace(/\\/g, "/").replace(/^\//, "")
}
