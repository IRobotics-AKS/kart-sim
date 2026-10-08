#!/usr/bin/env python3
"""
Runs INSIDE the Docker container (needs rclpy / ROS 2 Jazzy).

Sends a slowly oscillating torque command to /cmd_torque, and prints
whatever joint states come back on /joint_states -- those are being
published by MuJoCo running NATIVELY on your Mac, bridged in over
rosbridge. This proves the full loop: ROS 2 (Docker) <-> MuJoCo (Mac).

Run with:
    docker exec -it mujoco_ros2_sim bash
    python3 /root/ros2_ws/src/sim_demo/ros2_demo_node.py
"""
import math
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
from sensor_msgs.msg import JointState


class DemoBridgeNode(Node):
    def __init__(self):
        super().__init__("demo_bridge_node")
        self.pub = self.create_publisher(Float64MultiArray, "/cmd_torque", 10)
        self.sub = self.create_subscription(
            JointState, "/joint_states", self._on_joint_states, 10
        )
        self.start_time = time.time()
        self.timer = self.create_timer(0.05, self._on_timer)  # 20 Hz

    def _on_timer(self):
        t = time.time() - self.start_time
        # Gentle oscillating torque on each joint -- enough to see it move
        msg = Float64MultiArray()
        msg.data = [10.5 * math.sin(t), 1.0 * math.cos(0.7 * t)]
        self.pub.publish(msg)

    def _on_joint_states(self, msg: JointState):
        names = ", ".join(
            f"{n}={p:.2f}" for n, p in zip(msg.name, msg.position)
        )
        self.get_logger().info(f"joint_states: {names}")


def main():
    rclpy.init()
    node = DemoBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
