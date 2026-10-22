# Kart simulation architecture

Recorded: 2026-10-21. This document captures the project discussion; it does not
claim the proposed system has been implemented.

## Project and current state

The project is an autonomous Top Kart Dreamer with a Jetson running autonomy and
controls. Planned sensors are an IMU, GNSS, and three cameras: two described as
OpenCV AI cameras and one as an OAK camera. Exact models, outputs, synchronization,
mounting, and calibration are not yet known. The team plans to use JetPack 7.x
and TRAMPA VESC 75/300 MkIV motor controllers.

MuJoCo is the selected simulation engine. At the time of writing, this repository
contains a minimal Python scaffold (`main.py`, `pyproject.toml`), with Python
3.12 selected and no declared dependencies. It has no MuJoCo model, ROS adapter,
controller, Docker deployment, or validated integration yet.

## Repository boundaries

The user requires multiple repositories and separate control code. The following
five-repository split is the proposed implementation of that requirement:

| Repository | Owns |
| --- | --- |
| `kart-sim` | MuJoCo models, worlds, sensor simulation, actuator dynamics, scenarios, ROS adapter, simulator image |
| `kart-autonomy` | Perception, state estimation, planning, trajectory tracking, controls |
| `kart-hardware` | Physical driver integration, MCU bridge, initially MCU firmware |
| `kart-common` | Shared interfaces, nominal vehicle geometry, sensor mounting frames, interface documentation |
| `kart-bringup` | Workspace manifests, full-system launch/configuration, image selection, Compose deployments, boot setup |

These names do not establish that the repositories already exist. Controls can
initially be a package within `kart-autonomy`; a separate controls repository is
an option if team ownership later warrants it.

Keep nominal physical geometry and sensor mounting data in one shared source.
Keep MuJoCo-specific contact, solver, noise, and actuator-model parameters here.
Avoid independently maintained, conflicting sensor transforms.

## Required operating modes

| Mode | Measurements originate from | Autonomy/controls run on | Commands terminate at |
| --- | --- | --- | --- |
| Workstation simulation | MuJoCo on workstation | Workstation | MuJoCo actuators |
| Jetson simulation testing | MuJoCo on workstation | Jetson on the kart | MuJoCo actuators on workstation |
| Real driving | Physical kart sensors | Jetson on the kart | MCU supervisor and physical actuators |

Jetson simulation testing means running the same autonomy code on the real
computer using simulated inputs. The real motors remain disarmed. Testing actual
MCU firmware against a simulated vehicle is a separate future hardware-in-the-loop
mode and is not implemented or implicitly enabled by this design.

```text
Simulation:
MuJoCo -> simulated measurements -> ROS adapter -> autonomy -> commands
   ^                                                           |
   +------------- simulated actuator dynamics <----------------+

Real kart:
Physical sensors -> ROS drivers -> autonomy -> MCU bridge
                                           -> MCU -> VESCs/actuators
```

Autonomy must not import MuJoCo or read its internal state. The deployment chooses
the measurement source and actuator destination. The control algorithms should
not branch on whether they run on a workstation or Jetson.

## Simulation implementation boundary

Proposed layout, to be created as implementation proceeds:

```text
src/kart_sim/                 Standalone Python simulation library
  simulation.py              Load, step, reset, inspect
  actuators.py               Steering, drive, brake response
  sensors/                   IMU, GNSS, camera simulation
  scenarios.py               Scenario setup and fault injection
models/dreamer/              MJCF and simulation assets
worlds/                     Tracks, surfaces, obstacles
config/                     Rates, noise, latency, scenario parameters
ros/kart_sim_ros/            Installable ROS 2 adapter package
tests/                      Model, sensor, actuator, adapter verification
docker/                     Simulator image definition
docs/                       Architecture, decisions, modeling assumptions
```

The ROS package must explicitly install or depend on the Python core and install
model assets. The root Python project alone does not constitute a ROS package.
Simulator-only launch belongs here; launch of the complete autonomy system belongs
in `kart-bringup`.

## Shared ROS contract

The following are proposed message choices, not finalized topic names:

| Data | Starting point |
| --- | --- |
| IMU | `sensor_msgs/msg/Imu` |
| GNSS | `sensor_msgs/msg/NavSatFix` |
| Camera stream | `sensor_msgs/msg/Image` plus `CameraInfo` |
| Estimated motion | `nav_msgs/msg/Odometry` from state estimation |
| Actuator request and feedback | Shared definitions after the actuator boundary is agreed |
| Simulator truth | Separate `/sim/ground_truth/...` namespace for evaluation |

Define units, frames, TF ownership, timestamps, rates, QoS, covariance, command
validity, and reset semantics in the shared interface contract. GNSS simulation
needs a geographic reference and conversion from local coordinates. IMU behavior
must respect the sensor frame and acceleration convention. Unknown values must
remain configurable and clearly labeled assumptions.

Do not assume whether the command is target speed, motor current, throttle/brake,
or torque. Target speed requires a lower-level speed controller somewhere. The
real hardware and simulator must place that responsibility at the same boundary.

The simulator publishes `/clock`; participating nodes use `use_sim_time=true`.
Real operation uses real time. Define reset handling for estimators, controllers,
queues, and time jumps. Functional tests may run slower than real time; Jetson
deadline tests also require wall-clock latency and missed-deadline measurements.
Distributed ROS execution alone does not guarantee deterministic lockstep tests.

## Docker and deployment

Proposed services are `sim`, `autonomy`, `hardware`, and optional `recorder`.
Container boundaries need not follow repository boundaries. Start with autonomy
nodes together; optimize camera/perception placement after measuring performance.

Compose manages services on each host. ROS launch manages nodes within services.
For Jetson simulation testing, run simulator Compose on the workstation and
autonomy Compose on the Jetson, preferably over wired Ethernet. Both use the same
ROS distribution and compatible middleware configuration.

Use platform-specific images built from the same source revisions. Jetson GPU
support depends on compatible host JetPack/drivers/runtime as well as container
libraries. Docker does not supply a replacement Jetson kernel. macOS can be used
for native MuJoCo development; full Isaac ROS GPU integration needs a supported
NVIDIA environment.

Only a physical-hardware deployment receives actuator-device access. Simulation
deployments must not start the physical actuator bridge. Keep test ROS domains
separate from a live kart; a domain ID is not a security or hardware safety barrier.

## Supervisor and fault modeling

A microcontroller between Jetson and VESCs is recommended but not yet selected.
Its proposed responsibilities are command freshness, arming, limits, feedback
monitoring, watchdogs, and fault handling. It must not indefinitely replay stale
commands while keeping the VESC communication timeout alive.

Simulate the agreed supervisor behavior and actuator dynamics, including delays,
saturation, dropped commands, and faults. VESC electrical braking is not a complete
independent stopping system. Mechanical brake actuation and the independent stop
path remain open design questions; do not prescribe a final stop sequence yet.

## Initial milestone

Implement a simple kart model and actuator interface, simulated IMU/GNSS output,
and the ROS adapter. Close the loop with control code maintained outside this
repository on a workstation. Then run that same autonomy revision on the Jetson
against the simulator. Add camera/perception fidelity and further fault scenarios
incrementally.

See [decisions.md](decisions.md) for status, version proposals, and open questions.
Starter documents for a separate bringup repository are in
[`handoff/kart-bringup/`](../handoff/kart-bringup/).
