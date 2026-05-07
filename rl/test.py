import rclpy
import os
import argparse
from stable_baselines3 import PPO
from ros_line_follow_env import RosLineFollowEnv
from ament_index_python.packages import get_package_share_directory

def main():
    parser = argparse.ArgumentParser(description='Test PPO on Line Follower.')
    parser.add_argument('--reward-mode', type=str, default='vision', choices=['vision', 'coordinate'], help="Model type to test.")
    args, unknown = parser.parse_known_args()
    
    rclpy.init()
    
    print("==================================================")
    print(" INFINITE TESTING (INFERENCE / DEPLOYMENT) STARTING")
    print("==================================================")
    print("In this mode, the robot will keep trying indefinitely on the completed tracks.")
    print("Press CTRL+C to stop!")
    print("==================================================\n")

    # Create the environment in testing mode
    env = RosLineFollowEnv(is_testing_mode=True, reward_mode=args.reward_mode)
    
    package_share_dir = get_package_share_directory('two_wheeled_robot')
    workspace_dir = os.path.join(package_share_dir, '..', '..', '..', '..')
    folder_name = f"ppo_line_follower_{args.reward_mode}"
    save_dir = os.path.abspath(os.path.join(workspace_dir, folder_name))
    model_path = os.path.join(save_dir, "model.zip")
    
    if not os.path.exists(model_path):
        print(f"Error: Trained model not found at: {model_path}")
        print("Please start training first and wait for the model to be saved!")
        return
        
    print(f"Loading: {model_path}...")
    model = PPO.load(model_path, env=env)
    
    try:
        obs, info = env.reset()
        while True:
            # Only generate actions based on the model's current knowledge (cannot explore new actions -> deterministic=True)
            action, _states = model.predict(obs, deterministic=True)
            
            obs, reward, terminated, truncated, info = env.step(action)
            
            # If terminated or truncated, reset the environment to start a new episode on a new track. The robot will keep trying indefinitely until the user stops it with CTRL+C.
            if terminated or truncated:
                print(" -> Episode ended! Restarting...")
                obs, info = env.reset()
                
    except KeyboardInterrupt:
        print("\n\nExiting on user request...")
    finally:
        env.close()

if __name__ == '__main__':
    main()
