#!/bin/bash

# ROS2 environment variables for local-only communication and isolation from other ROS2 networks
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
# This ROS2 environment variable achieves the same effect,
# internally reconfiguring the network to localhost.
export ROS_LOCALHOST_ONLY=1
export ROS_DOMAIN_ID=42  # Isolation from faulty DDS packages running in the background

# Source the ROS 2 setup configuration
source install/setup.bash

echo "Starting Gazebo Simulation..."
# Start Gazebo in the background
HEADLESS_PARAM=${GAZEBO_HEADLESS:-True}
ros2 launch two_wheeled_robot load_world_into_gazebo.launch.py headless:=$HEADLESS_PARAM &
GAZEBO_PID=$!

echo "Waiting for 3 seconds to let Gazebo initialize (especially for GUI mode)..."
sleep 3

echo "Starting Training Script..."
# Start the RL training
ros2 launch two_wheeled_robot launch_rl_training.launch.py

# When the training finishes (or gets interrupted), also kill Gazebo
echo "Training finished or interrupted. Cleaning up Gazebo..."
# 1. Send a termination signal (like Ctrl+C) to the launch process
kill -INT $GAZEBO_PID 2>/dev/null


sleep 2


pkill -9 -f gzserver 2>/dev/null
pkill -9 -f gzclient 2>/dev/null
kill -9 $GAZEBO_PID 2>/dev/null

echo "Cleanup complete."
