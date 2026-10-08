#!/usr/bin/env python3
"""
Runs NATIVELY on your Mac (NOT inside Docker).

Simulates test_scene.xml with MuJoCo's normal interactive viewer window
(no XQuartz/X11 needed, since this isn't running inside a container), and
bridges to the ROS 2 Jazzy node running inside Docker via rosbridge's
WebSocket on localhost:9090.

  - Publishes /joint_states (current joint angles) so ROS 2 can see them.
  - Subscribes to /cmd_torque (a 2-element array) and applies it as the
    torque on joint1/joint2 -- so the Docker-side ROS 2 node can drive
    this native simulation.

One-time setup on your Mac:
    pip install mujoco roslibpy

Run (with the Docker container already up, rosbridge running inside it):
    python3 native/mujoco_ros_bridge.py
"""
import pathlib
import time

import mujoco
import mujoco.viewer
import roslibpy

MODEL_PATH = pathlib.Path(__file__).parent.parent / "src" / "sim_demo" / "test_scene.xml"

model = mujoco.MjModel.from_xml_path(str(MODEL_PATH))
data = mujoco.MjData(model)

# Start displaced so it's not just sitting at rest
data.qpos[0] = 1.2
data.qpos[1] = -0.6
mujoco.mj_forward(model, data)

JOINT_NAMES = ["joint1", "joint2", "axle"]

print("Connecting to rosbridge at ws://localhost:9090 ...")
ros = roslibpy.Ros(host="localhost", port=9090)
ros.run()
print("Connected." if ros.is_connected else "Could not connect -- is the container's rosbridge running?")

joint_state_pub = roslibpy.Topic(ros, "/joint_states", "sensor_msgs/JointState")
cmd_torque_sub = roslibpy.Topic(ros, "/cmd_torque", "std_msgs/Float64MultiArray")

_latest_cmd = [0.0, 0.0]


def _on_cmd_torque(message):
    data_field = message.get("data", [0.0, 0.0])
    _latest_cmd[0] = data_field[0] if len(data_field) > 0 else 0.0
    _latest_cmd[1] = data_field[1] if len(data_field) > 1 else 0.0


cmd_torque_sub.subscribe(_on_cmd_torque)

print(f"Loaded {MODEL_PATH.name} -- opening viewer window...")

with mujoco.viewer.launch_passive(model, data) as viewer:
    last_publish = 0.0
    while viewer.is_running() and ros.is_connected:
        # Apply the latest torque command from ROS 2
        data.ctrl[0] = _latest_cmd[0]
        data.ctrl[1] = _latest_cmd[1]

        mujoco.mj_step(model, data)
        viewer.sync()

        # Publish joint states at ~20 Hz (not every physics step)
        now = time.time()
        if now - last_publish > 0.05:
            joint_state_pub.publish(
                roslibpy.Message(
                    {
                        "name": JOINT_NAMES,
                        "position": list(data.qpos[: len(JOINT_NAMES)]),
                        "velocity": list(data.qvel[: len(JOINT_NAMES)]),
                        "effort": [],
                    }
                )
            )
            last_publish = now

ros.terminate()
