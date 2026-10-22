# Kart bringup architecture

Recorded: 2026-10-21. Copy this document to `docs/architecture.md` in the future
`kart-bringup` repository, alongside `docs/decisions.md` and root `AGENTS.md`.
This is a design handoff, not an implemented deployment.

## Project context

The team is building an autonomous Top Kart Dreamer. A Jetson will run autonomy
and controls, using an IMU, GNSS, and three cameras. Two cameras were described as
OpenCV AI cameras and one as OAK; exact models and capabilities are unknown.
JetPack 7.x is planned, but the Jetson model and precise release are unknown.
TRAMPA VESC 75/300 MkIV controllers are planned. A microcontroller supervisor
between Jetson and VESCs is recommended; its hardware and the mechanical brake
and independent emergency-stop design are unresolved.

MuJoCo is the selected simulator. The user requires multiple repositories,
separate controls, and the ability to run the same control code on a workstation
or on the kart's Jetson using simulated data.

## Repository ownership

| Repository | Responsibility |
| --- | --- |
| `kart-sim` | MuJoCo core/models/worlds, simulated sensors and actuators, ROS adapter, simulator image |
| `kart-autonomy` | Perception, localization, planning, controls |
| `kart-hardware` | Physical drivers, Jetson-to-MCU bridge, initially MCU firmware |
| `kart-common` | Shared ROS contracts, nominal geometry and sensor mounting frames |
| `kart-bringup` | Compatible workspace assembly, images, full-system launch, deployment configuration |

The split is proposed. Verify actual repositories and URLs before assembling the
workspace. A repository may contain multiple ROS packages. Container boundaries
are deployment choices and do not need to match repository boundaries.

## Operating modes

| Mode | Workstation | Jetson | Actuator destination |
| --- | --- | --- | --- |
| Workstation simulation | MuJoCo and autonomy | Not required | MuJoCo |
| Jetson simulation testing | MuJoCo | Autonomy | MuJoCo on workstation |
| Real driving | Optional monitoring | Physical drivers and autonomy | MCU and physical actuators |

```text
Workstation simulation:
  [MuJoCo + ROS adapter] <--- ROS ---> [Autonomy]

Jetson simulation testing:
  Workstation [MuJoCo + ROS adapter]
      <-- measurements / commands over wired Ethernet -->
  Jetson [Autonomy]
  Physical actuator bridge absent; real kart disarmed.

Real driving:
  Sensors -> [Hardware drivers] -> [Autonomy] -> [MCU bridge]
          -> MCU supervisor -> VESCs / physical actuators
```

In simulation, commands close the loop through simulated actuator dynamics.
Actual MCU hardware-in-the-loop testing would require a separate deployment and
test plan. It is not part of the initial Jetson simulation mode.

Autonomy uses shared ROS interfaces, never MuJoCo internal state. The controller
normally consumes estimated motion and a trajectory. Localization consumes
measurements; simulation truth is reserved for explicit evaluation/test paths.

## Deployment layers

| Layer | Owns |
| --- | --- |
| Host OS / JetPack | Kernel, device drivers, network and device configuration, NVIDIA runtime |
| Docker images | Built ROS packages and compatible userspace dependencies |
| Compose | Per-host services, images, GPU/device access, networking, volumes, restart policy |
| ROS launch | Nodes, parameters, remapping, namespaces, component composition |
| Readiness logic and MCU supervisor | Readiness/arming contract, command freshness, faults |
| Independent stop hardware | Stop behavior that does not rely on Jetson/MCU software running |

Recommended initial services:

- `sim`: MuJoCo core, models, sensors, ROS adapter; workstation only initially.
- `autonomy`: perception, estimation, planning, controls, selected Isaac ROS nodes.
- `hardware`: sensor drivers and MCU bridge; physical deployment only.
- `recorder`: optional bag recording and diagnostics with persistent storage.

Keep autonomy together initially. Revisit placement of camera drivers and
accelerated perception after measuring image transport and resource usage.
Keep high-rate sensor recording bounded so storage or I/O cannot grow unchecked.

## Proposed directory layout

```text
AGENTS.md
docs/
  architecture.md
  decisions.md
manifests/
  kart.repos                      Compatible repository revisions
docker/
  autonomy.Dockerfile
  hardware.Dockerfile
compose/
  workstation-sim.yaml             Simulator + autonomy
  simulator-server.yaml            Simulator only on workstation
  jetson-sim.yaml                  Autonomy only on Jetson
  kart-live.yaml                   Physical drivers + autonomy
  development.yaml                 Development overrides/source mounts
config/
  simulation/
  kart/
ros/kart_bringup/                  Installable ROS bringup package
  package.xml
  launch/
systemd/
  kart.service                    Optional boot integration
```

Only the three handoff documents exist initially. The layout is a proposal, not
a set of available commands. `kart-sim` may own its own Dockerfile; bringup selects
a compatible published simulator image.

## Workspace, builds, and runtime

Use a `.repos` manifest to assemble source repositories as siblings under a ROS
workspace's `src/`; build ROS packages with `colcon`. Explicitly install non-ROS
Python libraries/assets needed by those packages. Do not make deployment depend
on untracked local source directories.

Build workstation and Jetson images from the same source revisions using the
appropriate architecture and NVIDIA base environment. An architecture label alone
does not establish GPU/library compatibility. Pin deployment images by digest
and record source revisions and configuration together as a tested release.

For development, mount source for iteration. For deployment, use prebuilt images;
do not compile or download dependencies during startup. Mount calibration and
configuration read-only and recordings persistently. Give only required services
device/GPU access. MCU firmware runs directly on the microcontroller, not Docker.

Compose operates on each host separately. A workstation/Jetson test needs two
deployments plus explicit ROS networking; no Kubernetes or multi-host scheduler
is proposed. systemd can start the physical deployment at boot, leaving it disarmed.

## ROS networking, timing, and readiness

Use the same ROS distribution and a consistent DDS configuration across hosts.
Native Linux host networking is the initial recommendation. Document interface,
discovery, firewall, and QoS settings; test actual connectivity rather than assuming
host networking solves every discovery or shared-memory issue. Prefer wired
Ethernet for simulation camera streams and latency measurements.

Assign separate ROS domain IDs to independent tests/karts. Domain IDs are discovery
separation, not authorization or a physical safety barrier. Prevent a simulator
from joining and commanding a live deployment accidentally.

Simulation has one `/clock` publisher and sets `use_sim_time=true` on participating
nodes, including Jetson nodes in remote simulation mode. Physical operation uses
real time and appropriate host/sensor clock synchronization. Define reset and time
jump handling. Benchmark wall-clock latency separately from simulated time; slower
simulation can conceal missed real-world deadlines.

Container startup order does not establish sensor or controller readiness. Check
measurement freshness, calibration, required transforms, estimator validity, and
the command path before permitting arming. Docker health checks support operations;
they are not the runtime command watchdog. An unhealthy flag alone does not imply
an automatic Docker restart. Explicitly define child-node failure handling and
restart behavior. Recovery must not automatically rearm the kart.

## Documentation authority

When repositories exist, shared interfaces belong in `kart-common`, simulation
assumptions in `kart-sim`, and deployment pins/modes here. Keep references between
them rather than creating conflicting copies. See [decisions.md](decisions.md)
for the provisional version baseline and unresolved questions.
