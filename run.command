#!/bin/bash
# =========================================================================
#  run.command -- start the whole MuJoCo + ROS 2 simulation in one go.
#
#  Double-click it in Finder, or from Terminal:
#      ./run.command            camera robot in the walled room (default)
#      ./run.command --arm      the original two-link arm demo instead
#      ./run.command --no-demo  skip the ROS 2 brain node (e.g. a Jetson drives it)
#      ./run.command --web      arm demo in the browser (http://localhost:8080)
#
#  What it does (replaces the three manual terminal tabs in the README):
#    1. makes sure Docker Desktop is running
#    2. starts the container (rebuilds the image only if the Dockerfile
#       changed). Your .py / .xml edits show up every run, no build needed.
#    3. starts rosbridge inside the container and waits until it's ready
#    4. starts the ROS 2 node inside the container (log -> logs/):
#       robot: wall_avoider_node.py (camera -> turn at walls -> /cmd_vel)
#       arm:   ros2_demo_node.py   (oscillating torques)
#    5. opens the native MuJoCo viewer on the Mac (mjpython)
#  Closing the MuJoCo window (or Ctrl+C) stops rosbridge + the demo node.
#  The container itself keeps running so the next start is fast;
#  stop it with:  docker compose stop
# =========================================================================
set -u

cd "$(dirname "$0")" || exit 1
ROOT="$(pwd)"
CONTAINER="mujoco_ros2_sim"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

# Finder-launched scripts get a minimal PATH -- add the usual install spots.
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/.docker/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
for d in "$HOME"/Library/Python/*/bin; do [ -d "$d" ] && PATH="$d:$PATH"; done

MODE="native"; SCENE="robot"; RUN_DEMO=1
for arg in "$@"; do
  case "$arg" in
    --web)     MODE="web" ;;
    --arm)     SCENE="arm" ;;
    --no-demo) RUN_DEMO=0 ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg  (try --help)"; exit 1 ;;
  esac
done

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*"; echo; read -r -p "Press Return to close..." _; exit 1; }

# Runs a command inside the container with ROS 2 + workspace sourced.
in_ros() {
  docker exec "$CONTAINER" bash -c "source /opt/ros/jazzy/setup.bash; \
    [ -f /root/ros2_ws/install/setup.bash ] && source /root/ros2_ws/install/setup.bash; $1"
}

stop_ros_procs() {
  docker exec "$CONTAINER" bash -c '
    for f in /tmp/demo_node.pid /tmp/rosbridge.pid; do
      [ -f "$f" ] && kill -INT "$(cat "$f")" 2>/dev/null; rm -f "$f"
    done' >/dev/null 2>&1
}

# --- 1. Docker Desktop ----------------------------------------------------
command -v docker >/dev/null 2>&1 || fail "docker not found. Install Docker Desktop and open it once."
if ! docker info >/dev/null 2>&1; then
  say "Starting Docker Desktop..."
  open -a Docker 2>/dev/null || fail "Couldn't open Docker Desktop."
  for _ in $(seq 1 90); do docker info >/dev/null 2>&1 && break; sleep 2; done
  docker info >/dev/null 2>&1 || fail "Docker Desktop didn't come up within 3 minutes."
fi

# --- 2. Container -----------------------------------------------------------
# --build rebuilds the image only if Dockerfile / entrypoint.sh changed
# (otherwise Docker's cache makes it instant). .py / .xml edits in src/ and
# native/ need no build -- they're read fresh every run.
say "Starting container (rebuilds only if the Docker setup changed)..."
docker compose up -d --build || fail "docker compose up failed (see above)."

# --- Web-viewer mode: no rosbridge / native side needed ---------------------
if [ "$MODE" = "web" ]; then
  say "Starting browser viewer -> http://localhost:8080   (Ctrl+C to stop)"
  ( sleep 4; open "http://localhost:8080" ) &
  docker exec -it "$CONTAINER" python3 /root/ros2_ws/src/sim_demo/view_sim_web.py
  exit 0
fi

# --- Native-mode prerequisites (check before starting anything) ------------
MJPYTHON="$(command -v mjpython 2>/dev/null || true)"
if [ -z "$MJPYTHON" ]; then
  CAND="$(python3 -c 'import os,sys;print(os.path.join(os.path.dirname(sys.executable),"mjpython"))' 2>/dev/null)"
  [ -x "$CAND" ] && MJPYTHON="$CAND"
fi
if [ -z "$MJPYTHON" ] || ! "$MJPYTHON" -c "import roslibpy" 2>/dev/null; then
  say "Installing Mac-side Python packages (mujoco, roslibpy) -- one time only..."
  python3 -m pip install --user mujoco roslibpy \
    || python3 -m pip install --user --break-system-packages mujoco roslibpy \
    || fail "pip install mujoco roslibpy failed."
  for d in "$HOME"/Library/Python/*/bin; do [ -d "$d" ] && PATH="$d:$PATH"; done
  MJPYTHON="$(command -v mjpython 2>/dev/null || true)"
  if [ -z "$MJPYTHON" ]; then
    CAND="$(python3 -c 'import os,sys;print(os.path.join(os.path.dirname(sys.executable),"mjpython"))' 2>/dev/null)"
    [ -x "$CAND" ] && MJPYTHON="$CAND"
  fi
  [ -n "$MJPYTHON" ] || fail "Installed mujoco, but couldn't find mjpython."
  "$MJPYTHON" -c "import roslibpy" 2>/dev/null || fail "roslibpy isn't visible to mjpython."
fi

# From here on, always clean up the ROS processes on exit.
cleanup() { say "Stopping rosbridge and demo node..."; stop_ros_procs; }
trap cleanup EXIT
trap 'exit 130' INT TERM

# --- 3. rosbridge -----------------------------------------------------------
stop_ros_procs   # clear anything left over from a previous run
say "Starting rosbridge (ws://localhost:9090)..."
docker exec -d "$CONTAINER" bash -c "source /opt/ros/jazzy/setup.bash; \
  [ -f /root/ros2_ws/install/setup.bash ] && source /root/ros2_ws/install/setup.bash; \
  echo \$\$ > /tmp/rosbridge.pid; \
  exec ros2 launch rosbridge_server rosbridge_websocket_launch.xml > /tmp/rosbridge.log 2>&1"

READY=0
for _ in $(seq 1 60); do
  if docker exec "$CONTAINER" python3 -c \
     "import socket; socket.create_connection(('127.0.0.1', 9090), 1)" >/dev/null 2>&1; then
    READY=1; break
  fi
  sleep 1
done
if [ "$READY" != 1 ]; then
  docker exec "$CONTAINER" tail -n 30 /tmp/rosbridge.log
  fail "rosbridge didn't start within 60 s (log above)."
fi
echo "rosbridge is up."

# --- 4. ROS 2 demo node -----------------------------------------------------
if [ "$SCENE" = "robot" ]; then
  NODE_SCRIPT="wall_avoider_node.py"; NATIVE_SCRIPT="native/robot_ros_bridge.py"; LOG_NAME="wall_avoider.log"
else
  NODE_SCRIPT="ros2_demo_node.py";    NATIVE_SCRIPT="native/mujoco_ros_bridge.py"; LOG_NAME="demo_node.log"
fi
if [ "$RUN_DEMO" = 1 ]; then
  say "Starting ROS 2 node $NODE_SCRIPT (output -> logs/$LOG_NAME)..."
  in_ros "export PYTHONUNBUFFERED=1; echo \$\$ > /tmp/demo_node.pid; \
          exec python3 /root/ros2_ws/src/sim_demo/$NODE_SCRIPT" \
    > "$LOG_DIR/$LOG_NAME" 2>&1 &
  echo "Watch it live in another tab:  tail -f \"$LOG_DIR/$LOG_NAME\""
fi

# --- 5. Native MuJoCo viewer ----------------------------------------------
say "Opening the MuJoCo viewer (close the window or press Ctrl+C to stop)..."
"$MJPYTHON" "$NATIVE_SCRIPT"
