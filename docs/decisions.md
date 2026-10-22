# Decisions and open questions

Recorded: 2026-10-21. Status is explicit so future chats do not mistake a
recommendation for a confirmed requirement or an implemented feature.

## Confirmed user requirements and plans

| Item | Status |
| --- | --- |
| Autonomous Top Kart Dreamer | Project target |
| MuJoCo simulation | Selected by the user |
| Multiple repositories | Required by the user |
| Controls separate from `kart-sim` | Required by the user |
| IMU, GNSS, three cameras | Planned; models unknown |
| Two cameras described as OpenCV AI cameras, one as OAK | User description; do not infer exact devices or outputs |
| Jetson on kart runs autonomy/controls | Planned; Jetson model unknown |
| JetPack 7.x | Planned; exact release not chosen |
| TRAMPA VESC 75/300 MkIV | Planned motor controller; number and actuator roles unknown |
| Controls on workstation using simulation data | Required |
| Controls on kart's Jetson using simulation data | Required; simulated commands return to MuJoCo |

## Proposed architecture

- Five repositories: `kart-sim`, `kart-autonomy`, `kart-hardware`, `kart-common`,
  `kart-bringup`. Only the simulation repository is known to exist here.
- Keep the MuJoCo core ROS-independent; implement its ROS adapter in `kart-sim`.
- Reuse the same autonomy source across simulation and real driving.
- Use standard ROS sensor messages where appropriate and a shared actuator
  contract once its semantics are agreed.
- Use Docker Compose per host, ROS launch per service, and optionally systemd
  to start the kart deployment at boot while leaving the vehicle disarmed.
- Use a microcontroller supervisor between Jetson and VESCs, with a separate
  independent stop/braking design. MCU choice and firmware architecture are open.

These are design recommendations from the discussion, not a claim of user
approval of every detail. Update their status as decisions are made.

## Provisional version baseline

This is the recommendation recorded on 2026-10-21, not an installation lock or
validation result. Recheck compatibility before installing or publishing images.

| Component | Proposed baseline | Qualification |
| --- | --- | --- |
| MuJoCo | `3.16.0` | Pin exactly when implementation begins; test physics and rendering |
| ROS 2 | Jazzy | Keep simulation and Jetson on the same distribution |
| Isaac ROS | `4.6.0` | Optional selected perception packages; not needed by the simulation core |
| JetPack | `7.2` compatibility baseline | User specified only 7.x; hardware/carrier and patch release need confirmation |
| Ubuntu | `24.04` | Target environment for the proposed ROS/Isaac stack |
| Python | `3.12` | Already selected in this scaffold; validate with the chosen ROS environment |

JetPack 7.2.1 was available when discussed, but the cited Isaac ROS 4.6 matrix
explicitly named 7.2. Do not treat the patch release as validated here. Isaac ROS
5.0 / ROS 2 Lyrical was discussed as a newer alternative, not selected. Jazzy/4.6
was recommended partly because the camera stack was unresolved and Luxonis
explicitly documented Jazzy support.

References checked during the discussion:

- [MuJoCo changelog](https://mujoco.readthedocs.io/en/stable/changelog.html)
- [Isaac ROS 4.6 requirements](https://nvidia-isaac-ros.github.io/v/release-4.6/getting_started/index.html)
- [Isaac ROS release notes](https://nvidia-isaac-ros.github.io/v/release-5.0/releases/index.html)
- [JetPack downloads](https://developer.nvidia.com/embedded/jetpack/downloads)
- [DepthAI ROS](https://docs.luxonis.com/software-v3/depthai/ros)
- [Planned VESC model](https://trampaboards.com/vesc-75v-300a-mkiv--300-each-p-36236.html)
- [VESC CAN protocol and timeout](https://github.com/vedderb/bldc/blob/master/documentation/comm_can.md)
- [ROS clock design](https://design.ros2.org/articles/clock_and_time.html)

## Open questions before finalizing integration

1. Which Jetson module, RAM size, carrier board, and storage are installed?
2. Which exact JetPack image is supported by that hardware?
3. What are the camera, IMU, and GNSS models, interfaces, rates, synchronization,
   calibration, and mounting transforms? Will camera-side inference be used?
4. How many VESCs are used, and for propulsion, steering, or other actuators?
5. What motors, gear ratios, encoders, steering mechanism, battery/BMS, and
   physical current/voltage limits apply?
6. How will mechanical braking and an independent emergency stop be actuated?
7. Which MCU and Jetson-to-MCU transport will be used? What is the final command
   boundary and feedback contract?
8. What operating speeds, deadlines, sensor rates, and stopping requirements must
   be met? Determine timeout values from these requirements and measurements.
9. Which workstation OS/architectures/GPUs must support the full stack?
10. Which Isaac ROS packages are actually needed for the chosen perception stack?

## Implementation status

At documentation creation, MuJoCo integration, ROS packaging, shared messages,
Dockerfiles, Compose deployments, MCU firmware, and control integration are not
implemented in this repository. The files under `handoff/kart-bringup/` are
copyable documentation, not an executable deployment.

## Maintaining this record

When a decision changes, record the date, new choice, reason, and affected
repositories. Put deployment version pins in `kart-bringup` once that repository
exists. Put shared interface contracts in `kart-common`. This document records
simulation implications and should link to those authoritative sources.
