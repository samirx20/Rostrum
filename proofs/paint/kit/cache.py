"""Pixel cache beside a painting document: `<doc>.cache.npz`, so commands don't replay the whole painting.

The JSON op list stays the truth; the cache is only a copy of what replaying it gives. It holds the state after the
last batch (layer pixels, masks, last-stroke map, every stroke's coverage) plus up to UNDO_KEEP earlier states for
instant undo. Earlier states store only the arrays that differ from a later state (most batches touch one or two
layers), so they cost little. The key is a hash of the document head + batch list + the kit's own source
(`brush.py`, `doc.py`, this file): any change to the ops *or* to the paint code makes the cache stale, and
`Doc.open` replays instead (and says so on stderr). A zip of .npy files, read with allow_pickle off.
"""
import hashlib, io, json, os, zipfile
import numpy as np

UNDO_KEEP = 3  # earlier states kept for undo (each costs only the layers its later batches changed)
_HERE = os.path.dirname(os.path.abspath(__file__))
KIT_VERSION = hashlib.sha256(b"".join(open(os.path.join(_HERE, f), "rb").read()
                                      for f in ("brush.py", "doc.py", "cache.py"))).hexdigest()[:16]


def path_for(docpath):
    return str(docpath) + ".cache.npz"


def key(head, batches):
    h = hashlib.sha256(KIT_VERSION.encode())
    h.update(json.dumps(head, sort_keys=True).encode())
    h.update(json.dumps(batches, sort_keys=True).encode())
    return h.hexdigest()


class _Writer:
    def __init__(self, zf):
        self.zf, self.n, self.seen = zf, 0, {}  # role -> [(array, member name)] already written

    def put(self, a, role=""):
        for b, name in self.seen.setdefault(role, []):  # an earlier state shares most arrays with a later one
            if b is a or (b.shape == a.shape and b.dtype == a.dtype and np.array_equal(b, a)):
                return name
        name, self.n = f"a{self.n}.npy", self.n + 1
        buf = io.BytesIO()
        np.lib.format.write_array(buf, np.ascontiguousarray(a), allow_pickle=False)
        self.zf.writestr(name, buf.getvalue())
        self.seen[role].append((a, name))
        return name


def _pack(s, w):
    return dict(next_id=s.next_id, last=w.put(s.last, "last"), masks={k: w.put(v, "m:" + k) for k, v in s.masks.items()},
                layers=[{**{k: l[k] for k in l if k != "px"}, "px": w.put(l["px"], "l:" + l["name"])} for l in s.layers],
                info={str(k): list(v) for k, v in s.info.items()}, covs=sorted(s.covs))


def save(docpath, k, states):
    """states: {batch count: _State}, newest first matters (it is written whole; older ones reuse its arrays)."""
    tmp = path_for(docpath) + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        w = _Writer(zf)
        order = sorted(states, reverse=True)
        newest = states[order[0]]
        sids = sorted(newest.covs)
        tab = np.array([[sid, *newest.covs[sid][0]] for sid in sids], np.int64).reshape(-1, 5)
        buf = np.concatenate([newest.covs[sid][1].ravel() for sid in sids]) if sids else np.zeros(0, np.uint8)
        meta = dict(key=k, cov_tab=w.put(tab), cov_buf=w.put(buf),
                    states={str(n): _pack(states[n], w) for n in order})
        zf.writestr("meta.json", json.dumps(meta))
    os.replace(tmp, path_for(docpath))


def load(docpath, k, blank):
    """{batch count: _State} if the cache matches key `k`, else None. `blank` is a fresh _State to fill in."""
    p = path_for(docpath)
    if not os.path.exists(p):
        return None
    with zipfile.ZipFile(p) as zf:
        meta = json.loads(zf.read("meta.json"))
        if meta.get("key") != k:
            return None
        arrs = {}

        def get(name):
            if name not in arrs:
                with zf.open(name) as f:
                    arrs[name] = np.lib.format.read_array(io.BytesIO(f.read()), allow_pickle=False)
            return arrs[name]

        tab, buf, covs, off = get(meta["cov_tab"]), get(meta["cov_buf"]), {}, 0
        for sid, x0, y0, x1, y1 in tab.tolist():
            n = (x1 - x0) * (y1 - y0)
            covs[sid] = ((x0, y0, x1, y1), buf[off:off + n].reshape(y1 - y0, x1 - x0))
            off += n
        out = {}
        for n, m in meta["states"].items():
            s = blank.copy()
            s.next_id, s.last = m["next_id"], get(m["last"])
            s.masks = {name: get(a) for name, a in m["masks"].items()}
            s.layers = [{**{kk: v for kk, v in l.items() if kk != "px"}, "px": get(l["px"])} for l in m["layers"]]
            s.info = {int(sid): tuple(v) for sid, v in m["info"].items()}
            s.covs = {sid: covs[sid] for sid in m["covs"]}
            out[int(n)] = s
        return out
