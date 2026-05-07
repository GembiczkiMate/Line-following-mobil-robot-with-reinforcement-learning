#!/bin/bash

# Enabling the Cyclone DDS network layer to prevent instabilities and service hangs
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_LOCALHOST_ONLY=1
export ROS_DOMAIN_ID=42

echo "========================================================="
echo " TESTING (INFINITE LOOP) - VISUAL TEST WITH OPEN GAZEBO"
echo "========================================================="
echo ""
echo "Which model (reward system) would you like to load and evaluate?"
echo "1) Based on camera image (Vision - original version)"
echo "2) Based on track coordinates (Coordinate - spline measurement)"
while true; do
    read -p "Your choice (1/2): " REWARD_CHOICE
    case $REWARD_CHOICE in
        1) REWARD_MODE="vision"; break;;
        2) REWARD_MODE="coordinate"; break;;
        *) echo "Please choose a valid option (1 or 2).";;
    esac
done

echo ""
echo "=> Selected mode: $REWARD_MODE (Gazebo will open)"

# Source the ROS 2 setup configuration
source install/setup.bash

echo "Starting Gazebo Simulation (Visible / GUI mode)..."
# Start Gazebo in the background WITH HEADLESS FALSE explicitly
export GAZEBO_HEADLESS="False"
ros2 launch two_wheeled_robot load_world_into_gazebo.launch.py headless:=False &
GAZEBO_PID=$!

echo "Waiting for 3 seconds to let Gazebo initialize (especially for GUI mode)..."
sleep 3

echo "Starting Model Testing (Infinite loop) for $REWARD_MODE..."
# Run the test script in an infinite loop. The user can stop it with Ctrl+C, which will trigger the cleanup function.
python3 $(ros2 pkg prefix two_wheeled_robot)/share/two_wheeled_robot/rl/test.py --reward-mode $REWARD_MODE

# When it finishes (Ctrl+C)
echo "Testing finished or interrupted. Cleaning up Gazebo..."
kill -INT $GAZEBO_PID 2>/dev/null
sleep 2
pkill -9 -f gzserver 2>/dev/null
pkill -9 -f gzclient 2>/dev/null
kill -9 $GAZEBO_PID 2>/dev/null

echo "Cleanup complete."
