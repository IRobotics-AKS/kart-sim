# Agent instructions for kart-sim

Read `docs/architecture.md` and `docs/decisions.md` before proposing or making
architectural changes. These files carry project context across chats. Update
them when the user confirms a decision or changes a requirement.

## Repository scope

- This repository owns the MuJoCo simulation of an autonomous Top Kart Dreamer:
  vehicle and world models, simulated sensors, actuator dynamics, scenarios,
  simulation tests, and a ROS 2 adapter.
- Keep the simulation core independent of ROS so it can run standalone.
- Keep deployed perception, localization, planning, and controls in
  `kart-autonomy`. Do not put the production controller in this repository.
- Physical drivers, the Jetson-to-microcontroller bridge, and MCU firmware belong
  in `kart-hardware`. Full-system launch and deployment belong in `kart-bringup`.
- The other repositories are proposed boundaries; do not assume they exist.

## Interface and simulation rules

- MuJoCo is the selected simulation engine. Isaac ROS is an optional collection
  of accelerated ROS packages; it does not replace MuJoCo with Isaac Sim.
- Match simulated measurements and actuator commands to shared ROS interfaces.
  Keep simulator internals out of production autonomy code.
- Publish ground truth separately from simulated measurements. Do not silently
  feed perfect state into localization or controls.
- Treat time, frames, units, covariance, QoS, limits, and reset behavior as part
  of the interface. Do not invent final values for unknown hardware.
- Simulated actuator behavior must represent the chosen real command boundary;
  do not silently add an ideal speed controller that the real kart lacks.
- Use simulation time for simulated ROS data. Measure wall-clock performance
  separately when assessing Jetson deadlines.
- Keep simulated commands isolated from physical actuators. Simulation testing
  on the Jetson must not launch the physical actuator bridge or arm the kart.

## Working practices

- Distinguish confirmed requirements, proposed designs, and open questions.
  The version baseline is provisional, not an installed or validated stack.
- Preserve user edits. Implement only the requested scope; documentation of a
  feature does not mean that feature is implemented.
- For implementation changes, run checks appropriate to the changed model,
  sensor, actuator, or adapter and report what was actually verified.
- Do not choose motor limits, brake behavior, camera specifications, or MCU
  hardware without the required project information.
- `handoff/kart-bringup/` contains starter documents for a separate repository.
  It is not an implementation of bringup or the authoritative deployment config.
