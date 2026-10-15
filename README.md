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

## Quick start

Double-click **`run.command`** in Finder (or run `./run.command` in Terminal).
It starts Docker, the container, rosbridge, the ROS 2 node, and the native
MuJoCo window; closing the window stops it all.

By default it runs the **camera robot**: a small two-wheeled robot in a
walled room (with one wall in the middle). Its front camera streams to a
ROS 2 node in Docker, which spots walls and turns the robot away from them.
The viewer follows the robot and shows its camera view in the top-right corner.

- Edits to `.py` / `.xml` files show up the next time you run it -- nothing to compile.
- If the `Dockerfile` or `entrypoint.sh` changed, it rebuilds the image automatically.
- First run installs `mujoco` + `roslibpy` on the Mac if they're missing.
- Options: `--arm` (the original arm demo), `--no-demo` (skip the ROS 2 node),
  `--web` (arm demo in the browser at `localhost:8080`).
- The ROS 2 node's output goes to `logs/wall_avoider.log` (robot) or `logs/demo_node.log` (arm).

### How the camera robot works

```
MuJoCo (Mac)                          rosbridge             ROS 2 (Docker)
robot_ros_bridge.py --/camera/image_raw (160x120, 10 Hz)--> wall_avoider_node.py
   wheels  <---------------- /cmd_vel (Twist) --------------  uses wall_detector.py
```

`wall_detector.py` finds the red wall pixels in each frame and estimates how
far away the wall is from where it meets the floor in the image (the camera is
level at a known height). Wall ahead closer than 0.65 m: stop and turn toward
the more open side until the way is clear. Tuning numbers (speed, turn rate,
distances) are at the top of the `WallAvoider` class.

## What's in this folder

| Path | Runs where | Purpose |
| --- | --- | --- |
| `Dockerfile` | -- | Builds the ROS 2 Jazzy + MuJoCo + rosbridge image |
| `docker-compose.yml` | -- | Starts the container with the right ports/env |
| `entrypoint.sh` | in Docker | Sources ROS 2 on container start |
| `src/sim_demo/robot_world.xml` | on the Mac | MuJoCo world: walled room + middle wall + two-wheeled robot with a front camera |
| `src/sim_demo/wall_detector.py` | in Docker | Finds walls in a camera image and decides how to drive (plain numpy) |
| `src/sim_demo/wall_avoider_node.py` | in Docker | ROS 2 node: `/camera/image_raw` in, `/cmd_vel` out |
| `native/robot_ros_bridge.py` | **on the Mac** | Runs the robot world in MuJoCo's viewer, streams the camera, drives the wheels |
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
