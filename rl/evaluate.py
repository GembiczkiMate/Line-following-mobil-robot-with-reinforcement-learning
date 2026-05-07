import os

import rclpy
import os
import numpy as np
import argparse
from stable_baselines3 import PPO
from ros_line_follow_env import RosLineFollowEnv
from ament_index_python.packages import get_package_share_directory

def main():
    parser = argparse.ArgumentParser(description='Evaluate PPO on Line Follower.')
    parser.add_argument('--reward-mode', type=str, default='vision', choices=['vision', 'coordinate'], help="Model type to evaluate.")
    args, unknown = parser.parse_known_args()
    
    rclpy.init()
    
    print("==================================================")
    print(" VALIDATION (EVALUATION WITH STATISTICS) STARTING")
    print("==================================================")

    # Create the environment for validation (same Gazebo track)
    # Here is_testing_mode=False is required so that it evaluates itself on the tracks
    # where training also took place. The model here no longer updates the network, it only predicts!
    env = RosLineFollowEnv(is_testing_mode=False, reward_mode=args.reward_mode)
    env.sequential_mode = True # Sorban menjen végig
    env.current_track_index = 0 # Kezdje a legelsővel
    
    
    # Set PPO hyperparameters (these should match the ones used during training for a fair evaluation)
    package_share_dir = get_package_share_directory('two_wheeled_robot')
    workspace_dir = '/media/gembi/4a3cde59-7329-4c35-983a-99689c6819c0/rl_ros/src/two_wheeled_robot'
    folder_name = f"ppo_line_follower_{args.reward_mode}"
    save_dir = os.path.abspath(os.path.join(workspace_dir, folder_name))
    model_path = os.path.join(save_dir, "model.zip")
    
    if not os.path.exists(model_path):
        print(f"Error: Trained model not found at: {model_path}")
        print("Please start training first and wait for the model to be saved!")
        return
        
    print(f"Loading: {model_path}...")
    # Load the trained model with the previously learned "weights" (knowledge)
    model = PPO.load(model_path, env=env)
    
    NUM_EPISODES = len(env.PREDEFINED_TRACKS)  
    total_rewards = []
    success_count = 0
    
    print(f"\nEvaluating the model on {NUM_EPISODES} random episodes (tracks)...")
    
    # Run for 10 episodes (each episode is a full run on a track until it finishes or fails)
    for episode in range(NUM_EPISODES):
        obs, info = env.reset()
        done = False
        episode_reward = 0.0
        steps = 0
        
        while not done:
            
            action, _states = model.predict(obs, deterministic=True)
            
            #  Take the action in the environment and observe the result
            obs, reward, terminated, truncated, info = env.step(action)
            episode_reward += reward
            steps += 1
            
            done = terminated or truncated
            
            # Check if the episode ended due to falling off or successfully reaching the goal line bonus
            if done and reward >= env.FINISH_REWARD - 50: # Approximate check, if the reward is still high despite penalties due to reaching the goal
                success_count += 1
                
        total_rewards.append(episode_reward)
        print(f"Episode {episode + 1}/{NUM_EPISODES} - Steps: {steps} - Final Reward: {episode_reward:.2f}")
        
    # Calculate results (statistics)
    mean_reward = np.mean(total_rewards)
    std_reward = np.std(total_rewards)
    success_rate = (success_count / NUM_EPISODES) * 100
    
    print("\n" + "="*40)
    print(" EVALUATION RESULTS")
    print("="*40)
    print(f"Average Reward:  {mean_reward:.2f} +/- {std_reward:.2f}")
    print(f"Success Rate: {success_rate:.1f}% ({success_count} out of {NUM_EPISODES} reached the goal!)")
    print("="*40)
    
    env.close()

if __name__ == '__main__':
    main()
