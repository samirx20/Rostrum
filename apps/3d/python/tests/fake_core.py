"""A stand-in for `rostrum3d-core serve`: JSON lines in, JSON lines out. camera "nocam" is refused; frame 7 kills the process; camera "slow" takes 10 s;
with FAKE_SLOW=1 in its environment every render takes 60 s (a render to cancel)."""
import base64
import json
import os
import sys
import time

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==")

for line in sys.stdin:
    name, req = next(iter(json.loads(line).items()))
    if name == "render" and req["camera"] == "nocam":
        out = {"ok": False, "error": 'render: no camera "nocam". Accepted: cam'}
    elif name == "render" and os.environ.get("FAKE_SLOW"):
        time.sleep(60)
        out = {"ok": False, "error": "render: the slow stand-in was not cancelled in time"}
    elif name == "render" and req["frame"] == 7:
        sys.exit(3)
    elif name == "render":
        if req["camera"] == "slow":
            time.sleep(10)
        open(req["png"], "wb").write(PNG)
        out = {"ok": True, "frames": [{"frame": req["frame"], "png": req["png"], "ms": 5}], "renderer": req["renderer"], "timing": {}}
    elif name == "geometry":  # a unit cube: 8 points, 6 quads, counter-clockwise seen from outside
        out = {"ok": True, "item": req["item"],
               "points": [[x, y, z] for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)],
               "faceCounts": [4] * 6,
               "faceIndices": [0, 1, 3, 2, 4, 6, 7, 5, 0, 4, 5, 1, 2, 3, 7, 6, 0, 2, 6, 4, 1, 5, 7, 3]}
    else:
        out = {"ok": True}
    print(json.dumps(out), flush=True)
