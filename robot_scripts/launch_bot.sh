#!/bin/bash
# PPB-5K Pi 5 Startup Script
# Run on Pi 5 HOST

set -e

echo "[ppb] Starting ZMQ inference server..."
cd ~/hailo-apps && source setup_env.sh && python3 hailo_apps/python/gen_ai_apps/vlm_chat/zmq_listener.py &
INFER_PID=$!

echo "[ppb] Waiting for inference server to warm up (20s)..."
sleep 20

echo "[ppb] Removing old container if exists..."
docker rm -f ros-robot 2>/dev/null || true

echo "[ppb] Starting ROS2 container..."
docker run -it \
  --name ros-robot \
  --privileged \
  -v /dev:/dev \
  -v ~/ppb-5k_workspace/robot_scripts:/workspace \
  -v /sys:/sys \
  --network host \
  -e XDG_RUNTIME_DIR=/tmp/runtime-root \
  pi5-ros bash -c "
    source /workspace/install/setup.bash && \
    ros2 launch robot_bringup robot.launch.py
  "

# Ctrl+C kills inference server too
trap "echo '[ppb] Shutting down...'; kill $INFER_PID" EXIT
