#!/usr/bin/env python3
"""
Render the MuJoCo sim in software (no display/GPU needed) and stream it
as an MJPEG feed over HTTP, so you can watch it in a regular browser tab
on your Mac instead of fighting X11/XQuartz.

Run this INSIDE the container:
    docker exec -it mujoco_ros2_sim bash
    python3 /root/ros2_ws/src/sim_demo/view_sim_web.py

Then on your Mac, open a browser to:
    http://localhost:8080
"""
import os
# MUST be set before `import mujoco` -- tells MuJoCo to use software
# (CPU) rendering instead of trying to talk to a GPU/X server at all.
os.environ["MUJOCO_GL"] = "osmesa"

import io
import pathlib
import threading
import time

import mujoco
import numpy as np
from flask import Flask, Response
from PIL import Image

MODEL_PATH = pathlib.Path(__file__).parent / "test_scene.xml"
WIDTH, HEIGHT = 640, 480

model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
data = mujoco.MjData(model)
renderer = mujoco.Renderer(model, height=HEIGHT, width=WIDTH)

# Nudge it out of its resting (straight-down) position so gravity actually
# makes it swing, instead of sitting still at equilibrium from frame 1.
data.qpos[0] = 1.2   # joint1 -- displaced ~69 degrees
data.qpos[1] = -0.6  # joint2 -- bent at the elbow
mujoco.mj_forward(model, data)

print(f"Loaded {MODEL_PATH.name} -- {model.nbody} bodies, {model.njnt} joints")

_lock = threading.Lock()
_latest_jpeg = None


def _sim_loop():
    global _latest_jpeg
    while True:
        with _lock:
            mujoco.mj_step(model, data)
            renderer.update_scene(data)
            frame = renderer.render()  # HxWx3 uint8 numpy array
        img = Image.fromarray(frame)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        _latest_jpeg = buf.getvalue()
        time.sleep(1 / 60)  # ~60 Hz sim/render loop


app = Flask(__name__)


def _mjpeg_generator():
    while True:
        if _latest_jpeg is not None:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + _latest_jpeg + b"\r\n"
            )
        time.sleep(1 / 30)  # ~30 Hz stream to the browser


@app.route("/")
def index():
    return (
        "<html><body style='margin:0;background:#111'>"
        "<img src='/stream' style='display:block;margin:auto'/>"
        "</body></html>"
    )


@app.route("/stream")
def stream():
    return Response(
        _mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


if __name__ == "__main__":
    threading.Thread(target=_sim_loop, daemon=True).start()
    print("Open http://localhost:8080 in a browser on your Mac")
    app.run(host="0.0.0.0", port=8080)
