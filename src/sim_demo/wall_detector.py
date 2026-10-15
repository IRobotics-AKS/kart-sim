"""
wall_detector.py -- find walls in a camera image and decide how to drive.

Pure numpy, no ROS and no MuJoCo, so the same code can run in the ROS 2 node
(Docker), on a Jetson, or in a quick offline test.

How "seeing a wall" works
-------------------------
1. Walls are red, so every pixel that is clearly red counts as wall
   (works for both brightly lit and shaded wall faces).
2. The camera is mounted level at a known height. The place where a wall
   meets the floor shows up lower in the image the closer the wall is, so the
   row of that wall/floor edge gives the distance to the wall:
        distance = camera_height * focal_length_px / (row - image_center_row)
3. The image is split into LEFT / CENTER / RIGHT strips and a distance is
   measured for each one.

How it drives (WallAvoider)
---------------------------
  DRIVE : go forward, slowing down as the wall ahead gets closer.
          If a wall ahead is closer than STOP_DIST (or one just off a
          front corner is closer than SIDE_STOP_DIST) -> TURN.
  TURN  : spin in place toward whichever side looks more open, and keep
          turning (same direction) until the view ahead is clear past
          CLEAR_DIST, then go back to DRIVE. Each turn lasts a slightly
          random minimum time, so the robot explores the room instead of
          circling the same loop forever.
"""
import math
import random

import numpy as np

# Must match the camera in robot_world.xml
CAMERA_HEIGHT = 0.14   # metres above the floor
CAMERA_FOVY = 60.0     # vertical field of view, degrees

FAR = float("inf")


def wall_mask(rgb):
    """Boolean HxW mask of 'red wall' pixels in an HxWx3 uint8 image."""
    img = rgb.astype(np.int16)
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    return (r > 40) & (r > g * 1.6) & (r > b * 1.6)


def wall_distances(rgb, cam_height=CAMERA_HEIGHT, fovy_deg=CAMERA_FOVY):
    """
    Returns (left, center, right) distances to the nearest wall in metres,
    measured along the floor from the camera. FAR (inf) = no wall seen.
    """
    mask = wall_mask(rgb)
    h, w = mask.shape
    cy = (h - 1) / 2.0
    focal = (h / 2.0) / math.tan(math.radians(fovy_deg) / 2.0)

    # Lowest wall pixel in each column = where the wall meets the floor.
    rows = np.arange(h)[:, None]
    bottom = np.where(mask, rows, -1).max(axis=0)          # shape (w,)

    with np.errstate(divide="ignore"):
        below = bottom - cy
        col_dist = np.where(below > 0.5, cam_height * focal / np.maximum(below, 1e-6), FAR)
    col_dist[bottom < 0] = FAR                               # no wall in this column

    # Strips: left 25% | center 50% | right 25% (center ~ the robot's width ahead)
    q = w // 4
    strips = (col_dist[:q], col_dist[q:w - q], col_dist[w - q:])
    out = []
    for s in strips:
        seen = s[np.isfinite(s)]
        # Need the wall in a decent share of the strip, then take a low
        # percentile so the nearest part of the wall counts.
        out.append(float(np.percentile(seen, 20)) if seen.size >= 0.25 * s.size else FAR)
    return tuple(out)


class WallAvoider:
    """Turns wall distances into (forward speed m/s, turn rate rad/s)."""

    FORWARD_SPEED = 0.30   # m/s
    TURN_RATE = 1.6        # rad/s while turning away from a wall
    STOP_DIST = 0.65       # wall ahead closer than this -> start turning
    CLEAR_DIST = 1.10      # keep turning until the way ahead is this clear
    SIDE_DIST = 0.40       # nudge away from walls this close on either side
    SIDE_STOP_DIST = 0.30  # ...and turn in place if one is closer than this
    MIN_TURN_TIME = 0.4    # seconds -- avoids flickering between states
    EXTRA_TURN_TIME = 1.0  # up to this many extra seconds, chosen at random

    def __init__(self):
        self.state = "DRIVE"
        self.turn_dir = 1.0          # +1 = left (counter-clockwise), -1 = right
        self.turn_started = 0.0
        self.turn_time = self.MIN_TURN_TIME

    def update(self, left, center, right, now):
        if self.state == "DRIVE":
            if center < self.STOP_DIST or min(left, right) < self.SIDE_STOP_DIST:
                self.state = "TURN"
                self.turn_started = now
                self.turn_time = self.MIN_TURN_TIME + random.uniform(0.0, self.EXTRA_TURN_TIME)
                # Turn toward the more open side (left wins a tie).
                self.turn_dir = 1.0 if left >= right else -1.0
            else:
                # Slow down as the wall ahead gets closer.
                span = self.CLEAR_DIST - self.STOP_DIST
                scale = min(1.0, max(0.35, (center - self.STOP_DIST) / span))
                steer = 0.0
                if left < self.SIDE_DIST and left < right:
                    steer = -0.8               # wall close on the left -> veer right
                elif right < self.SIDE_DIST:
                    steer = 0.8                # wall close on the right -> veer left
                return self.FORWARD_SPEED * scale, steer

        # TURN
        turned_long_enough = (now - self.turn_started) >= self.turn_time
        if turned_long_enough and center > self.CLEAR_DIST and min(left, right) > self.SIDE_STOP_DIST:
            self.state = "DRIVE"
            return self.FORWARD_SPEED * 0.5, 0.0
        return 0.0, self.turn_dir * self.TURN_RATE


def fmt(d):
    return " far " if math.isinf(d) else f"{d:4.2f}m"
