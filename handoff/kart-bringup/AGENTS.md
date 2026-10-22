# Agent instructions for kart-bringup

Read `docs/architecture.md` and `docs/decisions.md` before making changes. These
documents are the project handoff from the kart simulation discussion. Keep them
current as the user confirms decisions; do not assume prior chat memory exists.

## Scope

- Own workspace assembly, pinned source/image versions, full-system ROS launch,
  configuration, Docker Compose deployments, and optional systemd boot setup.
- Keep MuJoCo implementation in `kart-sim`; deployed autonomy and controls in
  `kart-autonomy`; physical drivers and MCU firmware in `kart-hardware`; shared
  interfaces and nominal geometry in `kart-common`.
- The other repository names describe a proposed layout. Verify their existence
  and actual URLs before creating manifests. Do not invent remote locations.
- MuJoCo is selected. Isaac ROS adds accelerated ROS packages and does not imply
  replacing the simulator with Isaac Sim.

## Deployment requirements

- Support workstation simulation, Jetson autonomy with remote MuJoCo, and real
  driving as explicit, mutually exclusive configurations for a given kart.
- Simulation on the Jetson must not launch physical actuator interfaces, grant
  actuator-device access, or arm the vehicle. Commands return to MuJoCo.
- Keep simulated and physical measurement sources separate. Use one actuator
  command destination and one authoritative time source per deployment.
- Simulation uses `/clock` and `use_sim_time=true`; real driving uses real time.
- Start with Compose per host and ROS launch inside services. Do not assume
  ordinary Compose schedules containers across multiple machines.
- A running container is not proof of readiness. Validate sensor freshness,
  estimator state, and command-path readiness before permitting arming.
- Restart/reconnect must not automatically rearm the physical kart. MCU timeout
  and independent stopping behavior must not depend on Docker recovery.
- Use the same autonomy source revision for workstation and Jetson builds, with
  platform-compatible images. Pin tested releases and image digests for deployment.

## Working practices

- Treat the documented version matrix as provisional until hardware and actual
  integration checks confirm it. Verify official compatibility before pinning.
- Preserve user edits and distinguish proposed, implemented, and verified work.
- Do not put production source trees into this repository by copying sibling
  repositories. Assemble them with manifests/build inputs.
- During development, source mounts are acceptable. Deployed startup should use
  prebuilt images, persistent recording storage, and read-only configuration.
- Validate Compose configuration, ROS packaging/launch, mode isolation, and
  integration as appropriate; report unavailable hardware checks honestly.
