# MuJoCo (native) + ROS 2 Jazzy (Docker) simulation setup

A simulation environment split across two sides, bridged over a WebSocket:

- **ROS 2 Jazzy** runs inside a Docker container (matches JetPack 7 on a
  Jetson Orin Nano, if this is headed toward real hardware later).
- **MuJoCo** runs natively on your Mac, with its normal interactive 3D
  viewer window -- no X11/display forwarding required.
- The two talk over **rosbridge**, a WebSocket gateway into ROS 2 topics.
  `roslibpy`, a pure-Python library, lets the Mac side act like a ROS 2
  node without a real ROS 2 install.

```
MuJoCo (native, Mac)  <-- WebSocket :9090 -->  rosbridge (Docker)  <-->  ROS 2 Jazzy nodes (Docker)
```

## What's in this folder

| Path | Runs where | Purpose |
| --- | --- | --- |
| `Dockerfile` | -- | Builds the ROS 2 Jazzy + MuJoCo + rosbridge image |
| `docker-compose.yml` | -- | Starts the container with the right ports/env |
| `entrypoint.sh` | in Docker | Sources ROS 2 on container start |
| `src/sim_demo/test_scene.xml` | in Docker | MuJoCo model: a two-link motor-driven arm |
| `src/sim_demo/ros2_demo_node.py` | in Docker | Demo ROS 2 node: sends torque commands, prints joint states |
| `src/sim_demo/view_sim_web.py` | in Docker | Optional: browser-based MJPEG viewer at `localhost:8080`, no Mac-side script needed |
| `native/mujoco_ros_bridge.py` | **on the Mac**, not Docker | Opens MuJoCo's native viewer, bridges it to ROS 2 via rosbridge |

## One-time setup

1. **Docker Desktop** (Apple Silicon build) -- https://www.docker.com/products/docker-desktop/.
   Install it, then open it once and wait for it to fully start (steady
   whale icon in the menu bar) so its CLI registers.
2. **Python packages on the Mac** (outside Docker):
   ```
   pip install mujoco roslibpy
   ```

## Build and start the container

```
cd <this folder>
docker compose build
docker compose up -d
```

`docker compose build` only needs to be re-run after a Dockerfile change.

## Run the full bridged simulation

Three terminal tabs, started in this order:

**1. Start rosbridge** (inside the container):
```
docker exec -it mujoco_ros2_sim bash
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```
Leave this running.

**2. Start the ROS 2 demo node** (inside the container, second tab):
```
docker exec -it mujoco_ros2_sim bash
python3 /root/ros2_ws/src/sim_demo/ros2_demo_node.py
```
Sends oscillating torque commands and prints back joint states.

**3. Start the native bridge** (directly on the Mac, third tab -- NOT in Docker):
```
cd native
mjpython mujoco_ros_bridge.py
```
Use `mjpython`, not plain `python3` -- macOS requires it for MuJoCo's GUI
window (installed automatically alongside the `mujoco` pip package).

A MuJoCo window opens on your Mac. The arm should move, driven by torque
commands from the ROS 2 node in Docker; the demo node's terminal should
print live joint states streaming back from the Mac.

## Everyday restart (after the first full setup)

```
docker compose up -d
```
then repeat the three steps above -- no rebuild needed unless the
Dockerfile changed.

## Optional: browser-based viewer (no native Mac script)

If you just want to see the sim without the rosbridge round trip, run
this inside the container instead of the native bridge:
```
docker exec -it mujoco_ros2_sim bash
python3 /root/ros2_ws/src/sim_demo/view_sim_web.py
```
Then open `http://localhost:8080` in a browser on your Mac.

## Connecting a Jetson Orin Nano later

Both settings below must match between the Nano and `docker-compose.yml`:

| Setting | Value |
| --- | --- |
| ROS 2 distro | Jazzy (JetPack 7 on the Nano, matches the container) |
| `ROS_DOMAIN_ID` | Same value on both (currently `0`) |
| `RMW_IMPLEMENTATION` | Same value on both (currently `rmw_fastrtps_cpp`) |
| Discovery | Plain multicast, or a Fast DDS discovery server (`ROS_DISCOVERY_SERVER=<ip>:11811`) if multicast doesn't reach across the network |

## Troubleshooting

| Issue | Fix |
| --- | --- |
| `docker: command not found` | Open Docker Desktop at least once -- it registers its CLI on first launch. |
| `docker compose build` fails: `docker-credential-desktop` not found | Remove the `credsStore` line from `~/.docker/config.json`. |
| pip install fails uninstalling `numpy` (no RECORD file) | Already handled in the Dockerfile via `--ignore-installed`. |
| `rosdep install`: "Unable to locate package" | Already handled -- the Dockerfile runs `apt-get update` right before `rosdep install`. |
| `ros2: command not found` in a `docker exec` shell | Already handled -- ROS 2 is auto-sourced via `.bashrc`. |
| `launch_passive requires mjpython on macOS` | Run the native script with `mjpython`, not `python3`. |
| MuJoCo viewer can't connect / arm doesn't move | Confirm step 1 (rosbridge) is actually running before step 3 (native bridge) connects to it. |
