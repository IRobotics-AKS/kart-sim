#!/bin/bash
set -e

# Source ROS 2 and the workspace overlay
source /opt/ros/jazzy/setup.bash
if [ -f /root/ros2_ws/install/setup.bash ]; then
    source /root/ros2_ws/install/setup.bash
fi

# --- Cross-machine discovery -------------------------------------------
# Docker Desktop on Mac does NOT support true host networking, so DDS
# multicast discovery across the Mac <-> Jetson boundary is unreliable.
# Point both machines at a discovery server instead of relying on multicast.
#
# Uncomment and set this to the IP:port of whichever machine is running
# the discovery server (see README for how to start one):
# export ROS_DISCOVERY_SERVER=192.168.1.50:11811

# Keep RMW implementation explicit and identical on both machines
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

exec "$@"
