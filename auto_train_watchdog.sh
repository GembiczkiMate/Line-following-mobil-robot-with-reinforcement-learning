#!/bin/bash

# ROS beállítása a szervizek lekérdezéséhez
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_LOCALHOST_ONLY=1
export ROS_DOMAIN_ID=42
source install/setup.bash

# Beállítások
TIMEOUT_LIMIT=120       # Hány másodperc elérhetetlenség után lője ki (120 mp = 2 perc)
CHECK_INTERVAL=10       # Hány másodpercenként csekkolja a rendszert

echo "*********************************************************"
echo "* SUPERVISED TRAINING (WATCHDOG) STARTED                *"
echo "* Automatic restart in case of hang or crash.         *"
echo "*********************************************************"
echo ""
echo "Which reward system would you like to use for training?"
echo "1) Based on camera image (Vision - original version)"
echo "2) Based on track coordinates (Coordinate - physical spline measurement)"
read -p "Your choice (1/2): " REWARD_CHOICE

# Export as an environment variable, which will be visible to the next threads (launch files)
export TRAIN_REWARD_MODE="vision"
if [ "$REWARD_CHOICE" == "2" ]; then
    export TRAIN_REWARD_MODE="coordinate"
    echo "[WATCHDOG] The mathematical (Coordinate) mode has been set."
else
    echo "[WATCHDOG] The visual (Vision) mode has been set."
fi
echo ""
echo "Would you like to monitor the simulation visually? (Headless mode is much faster!)"
echo "1) Yes (Visible Gazebo GUI, Watchdog monitors service hangs as well)"
echo "2) No  (Fast Headless Gazebo, Watchdog only monitors Python-level hangs)"
read -p "Your choice (1/2): " WATCH_GAZEBO

# If the user wants to watch Gazebo, we set headless to False, otherwise True for faster performance
if [ "$WATCH_GAZEBO" == "1" ]; then
    export GAZEBO_HEADLESS="False"
else
    export GAZEBO_HEADLESS="True"
fi
echo "====================================================="

cleanup_and_exit() {
    echo ""
    echo "====================================================="
    echo "[WATCHDOG] Manual shutdown (Ctrl+C) detected!"
    echo "[WATCHDOG] Terminating all processes and exiting..."
    echo "====================================================="
    pkill -SIGINT -f train.py 2>/dev/null
    sleep 3
    kill -9 $MAIN_PID 2>/dev/null
    pkill -9 -f train.py 2>/dev/null
    pkill -9 -f gzserver 2>/dev/null
    pkill -9 -f gzclient 2>/dev/null
    exit 0
}

# Trap Ctrl+C (SIGINT) and SIGTERM signals to prevent automatic restart
trap cleanup_and_exit SIGINT SIGTERM

while true; do
    echo "====================================================="
    echo "[WATCHDOG] Starting a new training session..."
    echo "====================================================="
    
    rm -f /tmp/gazebo_fatal_error.flag
    
    # Start the training script in the background
    bash ./start_training.sh &
    MAIN_PID=$!
    
    # After starting, give it some time, during which it's normal that the service is not yet available
    echo "[WATCHDOG] Waiting for systems to initialize (45 seconds)..."
    sleep 45
    
    HANG_TIMER=0
    
    # Inner loop that runs as long as start_training.sh is alive in the background
    while kill -0 $MAIN_PID 2>/dev/null; do
        
        # Faster check for FATAL errors sent from the Python script
        if [ -f "/tmp/gazebo_fatal_error.flag" ]; then
            echo "====================================================="
            echo "[WATCHDOG] Received a signal from the Python code that the robot respawn"
            echo "           failed after multiple attempts!"
            echo "[WATCHDOG] Terminating processes immediately and restarting..."
            echo "====================================================="
            rm -f /tmp/gazebo_fatal_error.flag
            pkill -SIGINT -f train.py 2>/dev/null
            sleep 3
            kill -9 $MAIN_PID 2>/dev/null
            pkill -9 -f train.py 2>/dev/null
            pkill -9 -f gzserver 2>/dev/null
            pkill -9 -f gzclient 2>/dev/null
            sleep 5
            break
        fi
        
        # If Gazebo hangs, this call will either hang or throw an error
        if [ "$WATCH_GAZEBO" == "1" ]; then
            # Corrected the service name to /gazebo/describe_parameters which is a more general service that should be available even if spawn_entity is not responding
            if timeout 15 ros2 service call /gazebo/describe_parameters rcl_interfaces/srv/DescribeParameters "{}" > /dev/null 2>&1; then
                HANG_TIMER=0  
            else
                HANG_TIMER=$((HANG_TIMER + CHECK_INTERVAL))
                echo "[WATCHDOG] WARNING: The simulator has not responded for $HANG_TIMER seconds..."
            fi
            
            # If the timer exceeds the limit, we consider it a critical hang and restart everything
            if [ $HANG_TIMER -ge $TIMEOUT_LIMIT ]; then
                echo "====================================================="
                echo "[WATCHDOG] CRITICAL: The simulation has completely hung (>$TIMEOUT_LIMIT seconds)!"
                echo "[WATCHDOG] Terminating processes immediately and restarting..."
                echo "====================================================="
                
                pkill -SIGINT -f train.py 2>/dev/null
                sleep 3
                kill -9 $MAIN_PID 2>/dev/null
                pkill -9 -f train.py 2>/dev/null
                pkill -9 -f gzserver 2>/dev/null
                pkill -9 -f gzclient 2>/dev/null
                sleep 5
                break # A belső ciklust megszakítja, így a külső while true elölről elindítja az egészet
            fi
        fi
        
        sleep $CHECK_INTERVAL
    done
    
    echo "[WATCHDOG] Munkamenet leállt. Biztonsági takarítás az újraindítás előtt..."
    pkill -9 -f train.py 2>/dev/null
    pkill -9 -f gzserver 2>/dev/null
    pkill -9 -f gzclient 2>/dev/null
    sleep 3
    echo "[WATCHDOG] Újraindítás 3 másodperc múlva..."
    sleep 3
done
