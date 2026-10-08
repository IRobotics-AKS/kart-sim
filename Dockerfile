# ROS 2 Jazzy + MuJoCo simulation environment
# Matches the ROS 2 distro running on the Jetson Orin Nano (JetPack 7 -> Jazzy)

FROM ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# --- System deps -------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-venv \
    git \
    wget \
    curl \
    build-essential \
    cmake \
    libgl1 \
    libglfw3 \
    libglew-dev \
    libosmesa6-dev \
    ros-jazzy-ros2-control \
    ros-jazzy-ros2-controllers \
    ros-jazzy-xacro \
    ros-jazzy-robot-state-publisher \
    ros-jazzy-joint-state-publisher \
    ros-jazzy-rosbridge-suite \
    && rm -rf /var/lib/apt/lists/*

# --- Python deps ---------------------------------------------------------
# MuJoCo's Python bindings (pip package, works fine inside Linux container)
# --ignore-installed avoids pip trying (and failing) to uninstall the
# apt-installed numpy, which has no RECORD file for pip to work with.
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed \
    mujoco \
    numpy \
    scipy \
    flask \
    pillow

# --- Workspace -------------------------------------------------------
ENV ROS_WS=/root/ros2_ws
RUN mkdir -p ${ROS_WS}/src
WORKDIR ${ROS_WS}/src

# Clone mujoco_ros2_control into the workspace
# (pin a specific commit/tag once you've confirmed it works, instead of tracking main)
RUN git clone https://github.com/ros-controls/mujoco_ros2_control.git

WORKDIR ${ROS_WS}

# Build (will no-op cleanly on first image build if you mount src fresh later too)
RUN /bin/bash -c "source /opt/ros/jazzy/setup.bash && \
    apt-get update && \
    rosdep update && \
    rosdep install --from-paths src --ignore-src -r -y && \
    rm -rf /var/lib/apt/lists/* && \
    colcon build --symlink-install"

# --- Entrypoint -------------------------------------------------------
# Auto-source ROS 2 + the workspace overlay for every new shell,
# including `docker exec -it ... bash` sessions (which bypass ENTRYPOINT).
RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc && \
    echo "if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi" >> /root/.bashrc

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
