# Bringup decisions and open questions

Recorded: 2026-10-21. This handoff preserves context from the initial simulation
discussion. It distinguishes user requirements from proposed implementation.

## Confirmed requirements and plans

- Autonomous Top Kart Dreamer with a Jetson running autonomy and controls.
- MuJoCo is the simulation engine.
- Use multiple repositories; keep production controls out of `kart-sim`.
- Support controls on a workstation consuming simulated measurements.
- Support controls on the physical Jetson consuming simulated measurements, with
  outputs returned to MuJoCo and physical actuators disarmed.
- Support eventual physical operation from real sensors through the real actuator
  interface.
- Planned sensors: IMU, GNSS, and three cameras, described as two OpenCV AI and
  one OAK. Exact devices are not known.
- JetPack 7.x is planned. Jetson model, carrier board, and exact image are unknown.
- TRAMPA VESC 75/300 MkIV is the planned motor controller. Quantity and roles
  are not yet known.

## Proposed choices, not yet fully confirmed or implemented

| Proposal | Reason |
| --- | --- |
| `kart-sim`, `kart-autonomy`, `kart-hardware`, `kart-common`, `kart-bringup` | Separate simulation, deployed software, physical integration, contracts, and deployment |
| ROS-independent simulation core with local ROS adapter | Enable standalone simulation and common interfaces |
| Compose per host, ROS launch within services | Simple workstation/Jetson orchestration |
| Initial `sim`, `autonomy`, `hardware`, optional `recorder` services | Separate major runtime responsibilities without one container per node |
| MCU supervisor between Jetson and VESCs | Enforce freshness, arming, limits, and faults independently of ROS |
| Separate mechanical braking and independent stop path | Electrical motor braking alone is not the complete stop design |
| Prebuilt versioned deployment images | Reproducible startup and rollback |

No microcontroller, communication protocol, timeout duration, brake sequence, or
electrical limit has been selected. Do not silently turn those into fixed defaults.

## Provisional software baseline

Recommendation recorded on 2026-10-21:

| Component | Candidate | Status |
| --- | --- | --- |
| MuJoCo | `3.16.0` | Simulator version to pin and validate |
| ROS 2 | Jazzy | Proposed common distribution |
| Isaac ROS | `4.6.0` | Selected perception packages only, after requirements are known |
| JetPack | `7.2` compatibility baseline | Must confirm Jetson/carrier support and exact patch release |
| Ubuntu | `24.04` | Proposed Linux environment |
| Python | `3.12` | Present in simulation scaffold; validate runtime dependencies |

These are not installed or integration-tested project versions. JetPack 7.2.1
was available when discussed, while the Isaac ROS 4.6 requirements named 7.2.
Verify the exact image rather than assuming any 7.x release is interchangeable.
Isaac ROS 5.0 with ROS 2 Lyrical is a newer alternative discussed but not selected.
Jazzy/4.6 was recommended as an initial integration baseline with documented
Luxonis Jazzy support and unknown camera hardware.

Sources from the discussion; recheck before installation:

- [MuJoCo changelog](https://mujoco.readthedocs.io/en/stable/changelog.html)
- [Isaac ROS 4.6 requirements and Docker setup](https://nvidia-isaac-ros.github.io/v/release-4.6/getting_started/index.html)
- [Isaac ROS release notes](https://nvidia-isaac-ros.github.io/v/release-5.0/releases/index.html)
- [JetPack downloads](https://developer.nvidia.com/embedded/jetpack/downloads)
- [DepthAI ROS support](https://docs.luxonis.com/software-v3/depthai/ros)
- [VESC product](https://trampaboards.com/vesc-75v-300a-mkiv--300-each-p-36236.html)
- [VESC CAN and timeout documentation](https://github.com/vedderb/bldc/blob/master/documentation/comm_can.md)
- [ROS clock design](https://design.ros2.org/articles/clock_and_time.html)
- [Compose startup behavior](https://docs.docker.com/compose/how-tos/startup-order/)
- [Docker host networking](https://docs.docker.com/engine/network/drivers/host/)
- [vcstool manifests](https://github.com/dirk-thomas/vcstool)

## Open questions

1. Jetson module, RAM, carrier board, storage, supported JetPack image?
2. Workstation OS, CPU architectures, and GPUs? macOS native MuJoCo development
   is possible; full Isaac ROS GPU validation needs a supported NVIDIA environment.
3. Exact sensors, camera outputs/inference, calibration, mounting, synchronization,
   interfaces, bandwidth, and rates?
4. VESC quantity and purpose, motor and encoder specifications, gearing, battery
   and BMS limits, steering mechanism, and brake actuator?
5. MCU choice, Jetson-to-MCU link, supervisor state machine, command semantics,
   feedback, timeout/arming rules, and independent stopping behavior?
6. Target speeds and deadlines, expected sensor latency, required stopping behavior?
7. Which Isaac ROS packages are needed, and what resources do they require?
8. Actual repository URLs, ownership, image registry, CI availability, and release
   process? No remote URLs or registries have been established in this handoff.

## Initial implementation sequence

1. Verify hardware/platform compatibility and finalize the initial shared ROS
   contract with the relevant repositories.
2. Assemble source revisions and build the minimal workstation simulation loop:
   external controls, MuJoCo actuator model, IMU/GNSS, and ROS adapter.
3. Add reproducible simulation/autonomy images and workstation Compose deployment.
4. Build the same autonomy revision for Jetson and test with remote MuJoCo.
5. Add the isolated physical-hardware deployment after actuator/supervisor details
   and the independent stopping design are established.
6. Integrate camera/perception pipelines and expand fault and timing tests.

## Current implementation status

The source `kart-sim` repository was a minimal Python scaffold when this handoff
was created. These three documents do not create repositories, package metadata,
ROS launch files, Docker images, Compose files, or a working simulation.

Record future decisions with date, rationale, affected repositories, and actual
validation evidence. Maintain exact source/image pins here once integration exists.
