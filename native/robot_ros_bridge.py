#!/usr/bin/env python3
"""
Runs NATIVELY on your Mac (NOT inside Docker) -- run.command starts it.

Simulates the camera robot in robot_world.xml with MuJoCo's viewer window and
bridges it to ROS 2 (Docker) through rosbridge on localhost:9090:

  publishes   /camera/image_raw  sensor_msgs/Image, 160x120 rgb8, 10 Hz
  subscribes  /cmd_vel           geometry_msgs/Twist -> left/right wheel speeds

The ROS 2 node wall_avoider_node.py (in Docker) watches the camera and sends
/cmd_vel, so the robot drives around and turns when it sees a wall.

The viewer follows the robot, and the robot's own camera view is shown in the
top-right corner of the window.

Run manually with (Docker container + rosbridge already running):
    mjpython native/robot_ros_bridge.py
"""
import base64
import pathlib
import time

import mujoco
import mujoco.viewer
import numpy as np
import roslibpy

SCENE = pathlib.Path(__file__).resolve().parent.parent / "src" / "sim_demo" / "robot_world.xml"

CAM_W, CAM_H = 160, 120     # camera resolution sent to ROS
CAM_PERIOD = 0.1            # seconds between camera frames (10 Hz)
WHEEL_RADIUS = 0.05         # m   (must match robot_world.xml)
HALF_TRACK = 0.115          # m   (wheel distance from centre line)
CMD_TIMEOUT = 0.5           # s   stop the wheels if /cmd_vel goes quiet
PIP_SCALE = 2               # camera picture-in-picture size multiplier

model = mujoco.MjModel.from_xml_path(str(SCENE))
data = mujoco.MjData(model)
mujoco.mj_forward(model, data)

left_motor = model.actuator("left_motor").id
right_motor = model.actuator("right_motor").id
robot_body = model.body("robot").id

camera = mujoco.Renderer(model, height=CAM_H, width=CAM_W)

# ---- ROS connection ---------------------------------------------------------
print("Connecting to rosbridge at ws://localhost:9090 ...")
ros = roslibpy.Ros(host="localhost", port=9090)
try:
    ros.run(timeout=15)
except Exception:
    raise SystemExit("Could not connect to rosbridge -- is it running in the container?")
print("Connected.")

image_pub = roslibpy.Topic(ros, "/camera/image_raw", "sensor_msgs/Image", queue_size=1)
cmd_sub = roslibpy.Topic(ros, "/cmd_vel", "geometry_msgs/Twist")

_cmd = {"v": 0.0, "w": 0.0, "t": 0.0}


def _on_cmd_vel(msg):
    _cmd["v"] = float(msg.get("linear", {}).get("x", 0.0))
    _cmd["w"] = float(msg.get("angular", {}).get("z", 0.0))
    _cmd["t"] = time.time()


cmd_sub.subscribe(_on_cmd_vel)


def publish_camera(rgb):
    image_pub.publish(roslibpy.Message({
        "header": {"frame_id": "front_cam"},
        "height": CAM_H,
        "width": CAM_W,
        "encoding": "rgb8",
        "is_bigendian": 0,
        "step": CAM_W * 3,
        "data": base64.b64encode(rgb.tobytes()).decode("ascii"),
    }))


def show_overlay(viewer, rgb, v, w):
    """Robot camera view in the top-right corner + a status line."""
    vp = viewer.viewport
    if vp is None:
        return
    pip = np.repeat(np.repeat(rgb, PIP_SCALE, axis=0), PIP_SCALE, axis=1)
    ph, pw = pip.shape[:2]
    rect = mujoco.MjrRect(vp.width - pw - 10, vp.height - ph - 10, pw, ph)
    viewer.set_images((rect, pip))
    viewer.set_texts((
        mujoco.mjtFontScale.mjFONTSCALE_150,
        mujoco.mjtGridPos.mjGRID_BOTTOMLEFT,
        "Robot cmd",
        f"v={v:+.2f} m/s   w={w:+.2f} rad/s",
    ))


print(f"Loaded {SCENE.name} -- opening viewer window...")
print("The robot's camera view is in the top-right corner of the window.")

with mujoco.viewer.launch_passive(model, data) as viewer:
    with viewer.lock():
        viewer.cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
        viewer.cam.trackbodyid = robot_body
        viewer.cam.distance = 2.2
        viewer.cam.elevation = -35
        viewer.cam.azimuth = 200

    overlay_ok = hasattr(viewer, "set_images")
    wall_start = time.time()
    sim_start = data.time
    next_cam = data.time

    while viewer.is_running() and ros.is_connected:
        frame_start = time.time()

        # Twist -> wheel speeds (stop if commands go stale)
        if time.time() - _cmd["t"] > CMD_TIMEOUT:
            v, w = 0.0, 0.0
        else:
            v, w = _cmd["v"], _cmd["w"]

        with viewer.lock():
            data.ctrl[left_motor] = (v - w * HALF_TRACK) / WHEEL_RADIUS
            data.ctrl[right_motor] = (v + w * HALF_TRACK) / WHEEL_RADIUS

            # Step physics to keep pace with the wall clock (real time).
            target = sim_start + (time.time() - wall_start)
            steps = 0
            while data.time < target and steps < 200:
                mujoco.mj_step(model, data)
                steps += 1
            if steps == 200:              # fell behind (e.g. window dragged): resync
                wall_start, sim_start = time.time(), data.time

            grab = data.time >= next_cam
            if grab:
                next_cam = data.time + CAM_PERIOD
                camera.update_scene(data, camera="front_cam")
                rgb = camera.render().copy()

        if grab:
            publish_camera(rgb)
            if overlay_ok:
                try:
                    show_overlay(viewer, rgb, v, w)
                except Exception as e:     # older MuJoCo / unexpected viewer
                    print(f"(camera overlay disabled: {e})")
                    overlay_ok = False

        viewer.sync()
        time.sleep(max(0.0, 1 / 60 - (time.time() - frame_start)))

if not ros.is_connected:
    print("Lost connection to rosbridge.")
ros.terminate()
