#!/usr/bin/env python3
"""
Runs INSIDE the Docker container (needs rclpy / ROS 2 Jazzy).

The robot's "brain": looks at the front camera image and drives the robot,
turning whenever it sees a wall getting close.

  subscribes  /camera/image_raw   sensor_msgs/Image (rgb8)  <- MuJoCo on the Mac
  publishes   /cmd_vel            geometry_msgs/Twist       -> robot wheels

The vision + driving logic lives in wall_detector.py (plain numpy), so this
file only does the ROS plumbing. The same node would work unchanged on a
Jetson with a real camera publishing /camera/image_raw.

Run with (run.command does this for you):
    python3 /root/ros2_ws/src/sim_demo/wall_avoider_node.py
"""
import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import Image

from wall_detector import WallAvoider, fmt, wall_distances


class WallAvoiderNode(Node):
    def __init__(self):
        super().__init__("wall_avoider")
        self.avoider = WallAvoider()
        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(Image, "/camera/image_raw", self._on_image, 10)
        self.last_image_time = None
        self.last_log = 0.0
        self.create_timer(0.25, self._watchdog)
        self.get_logger().info("Waiting for camera images on /camera/image_raw ...")

    def _now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def _on_image(self, msg: Image):
        if msg.encoding not in ("rgb8", "bgr8"):
            self.get_logger().warn(f"Unsupported image encoding {msg.encoding}", once=True)
            return
        buf = np.frombuffer(bytes(msg.data), dtype=np.uint8)
        rgb = buf.reshape(msg.height, msg.step)[:, : msg.width * 3].reshape(msg.height, msg.width, 3)
        if msg.encoding == "bgr8":
            rgb = rgb[..., ::-1]

        now = self._now()
        if self.last_image_time is None:
            self.get_logger().info(f"Camera connected ({msg.width}x{msg.height}). Driving!")
        self.last_image_time = now

        left, center, right = wall_distances(rgb)
        v, w = self.avoider.update(left, center, right, now)

        cmd = Twist()
        cmd.linear.x = float(v)
        cmd.angular.z = float(w)
        self.cmd_pub.publish(cmd)

        if now - self.last_log > 0.5:
            self.last_log = now
            turn = "" if self.avoider.state == "DRIVE" else (" left" if self.avoider.turn_dir > 0 else " right")
            self.get_logger().info(
                f"{self.avoider.state + turn:<11} wall  L {fmt(left)}  C {fmt(center)}  R {fmt(right)}"
                f"   cmd v={v:.2f} m/s w={w:+.2f} rad/s"
            )

    def _watchdog(self):
        # No camera for a while -> stop the robot rather than drive blind.
        if self.last_image_time is not None and self._now() - self.last_image_time > 1.0:
            self.cmd_pub.publish(Twist())
            self.get_logger().warn("Camera images stopped -- robot halted.", throttle_duration_sec=5.0)


def main():
    rclpy.init()
    node = WallAvoiderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.cmd_pub.publish(Twist())   # stop on exit
        except Exception:
            pass
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
