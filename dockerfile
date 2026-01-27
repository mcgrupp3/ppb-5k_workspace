FROM ros:jazzy

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=jazzy

# Update and install TurtleBot4 packages
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-zmq \
    git \
    '~nros-jazzy-rqt*' \
    ros-jazzy-joy \
    joystick \
    python3-gpiozero \
    python3-lgpio \
    python3-pygame \
    && rm -rf /var/lib/apt/lists/*

# Source ROS2 setup in bashrc
RUN echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
RUN echo "export ROS_DOMAIN_ID=42" >> ~/.bashrc

# Create workspace
WORKDIR /workspace

CMD ["/bin/bash"]