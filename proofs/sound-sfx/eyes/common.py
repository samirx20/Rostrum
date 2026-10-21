"""Shared helpers: video reading, JSON output, errors."""
import json
import sys
import cv2


def out(obj):
    print(json.dumps(obj, separators=(",", ":")))


def fail(msg):
    print(f"eyes: error: {msg}", file=sys.stderr)
    sys.exit(2)


def open_video(path):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        fail(f"cannot open video {path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not fps or n <= 0:
        fail("video has no fps or frame count")
    return cap, fps, n


def read_frame(cap, idx):
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, fr = cap.read()
    if not ok:
        fail(f"cannot read frame {idx}")
    return fr
