import os

import rclpy
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.callbacks import BaseCallback
from ros_line_follow_env import RosLineFollowEnv
from ament_index_python.packages import get_package_share_directory
import os
import torch
import math

import argparse
from stable_baselines3.common.logger import configure

# ============================================================================
# HYPERPARAMETERS - Modify these to tune your training
# ============================================================================
# --- Training Parameters ---
TOTAL_TIMESTEPS = 10000    
LOG_INTERVAL = 1        # Log every N episodes

# --- PPO Algorithm Parameters ---
# Default Stable Baselines3 PPO parameters for both modes
PPO_HYPERPARAMS_VISION = {
    "learning_rate": 3e-4,
    "n_steps": 2048,
    "batch_size": 64,
    "n_epochs": 10,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip_range": 0.2,
    "ent_coef": 0.01,
    "vf_coef": 0.5,
    "max_grad_norm": 0.5,
}

PPO_HYPERPARAMS_COORDINATE = {
    "learning_rate": 3e-4,
    "n_steps": 2048,
    "batch_size": 64,
    "n_epochs": 10,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip_range": 0.2,
    "ent_coef": 0.01,
    "vf_coef": 0.5,
    "max_grad_norm": 0.5,
}

# --- CNN Policy Architecture ---
# CnnPolicy automatically extracts features from images
# Then uses fully connected layers for policy and value heads
POLICY_KWARGS = {
    "net_arch": dict(
        pi=[64, 64],        # Policy network after CNN features
        vf=[64, 64]         # Value network after CNN features
    ),
    
    "features_extractor_kwargs": {
        "features_dim": 256   # Output dimension of CNN feature extractor
    }
}

# ============================================================================

# ============================================================================

class CustomSaveCallback(BaseCallback):
    """
    Silently overwrites the same model.zip so we don't spam the directory with checkpoins,
    but we still survive crashes securely.
    """
    def __init__(self, save_path, save_freq, verbose=0):
        super(CustomSaveCallback, self).__init__(verbose)
        self.save_path = save_path
        self.save_freq = save_freq

    def _on_step(self) -> bool:
        if self.n_calls % self.save_freq == 0:
            self.model.save(self.save_path)
            if self.verbose > 0:
                print(f"Silently auto-saved model at {self.num_timesteps} steps.")
        return True

def main():
    parser = argparse.ArgumentParser(description='Train PPO on Line Follower.')
    parser.add_argument('--reward-mode', type=str, default='vision', choices=['vision', 'coordinate'],
                        help="Reward calculation mode: 'vision' (based on camera) or 'coordinate' (based on odometry distance to spline).")
    args, unknown = parser.parse_known_args()

    rclpy.init()
    
    # --- 1. Create the environment ---
    env = RosLineFollowEnv(is_testing_mode=False, reward_mode=args.reward_mode)

    # PPO paraméterek kiválasztása reward_mode alapján
    if args.reward_mode == 'vision':
        PPO_HYPERPARAMS = PPO_HYPERPARAMS_VISION
    else:
        PPO_HYPERPARAMS = PPO_HYPERPARAMS_COORDINATE

    # --- 2. Create the PPO agent ---
    package_share_dir = get_package_share_directory('two_wheeled_robot')
    workspace_dir = os.path.join(package_share_dir, '..', '..', '..', '..')
    folder_name = f"ppo_line_follower_{args.reward_mode}"
    save_dir = os.path.abspath(os.path.join(workspace_dir, folder_name))
    os.makedirs(save_dir, exist_ok=True)
    model_save_path = os.path.join(save_dir, "model")
    tensorboard_log_dir = os.path.join(save_dir, "logs")

    import zipfile
    is_valid_zip = False
    if os.path.exists(model_save_path + ".zip") and os.path.getsize(model_save_path + ".zip") > 0:
        try:
            with zipfile.ZipFile(model_save_path + ".zip") as zf:
                is_valid_zip = True
        except zipfile.BadZipFile:
            print("WARNING: Existing model.zip is corrupted (e.g. interrupted save). Ignoring it and creating a new one.")

    if is_valid_zip:
        print("Loading existing model...")
        try:
            model = PPO.load(model_save_path, env=env, custom_objects=PPO_HYPERPARAMS)
        except AssertionError as e:
            if "No data found in the saved file" in str(e):
                print("WARNING: Existing model is missing data (AssertionError). Creating a new one...")
                model = PPO("MlpPolicy", env, verbose=1, tensorboard_log=tensorboard_log_dir, **PPO_HYPERPARAMS)
            else:
                raise e
        model.tensorboard_log = tensorboard_log_dir
    else:
        print("Creating new CNN-based model...")
        print(f"Using device: {torch.device('cuda' if torch.cuda.is_available() else 'cpu')}")
        model = PPO(
            "CnnPolicy",
            env,
            verbose=1,
            tensorboard_log=tensorboard_log_dir,
            policy_kwargs=POLICY_KWARGS,
            device="auto",
            **PPO_HYPERPARAMS
        )

    # --- 3. Train the agent ---
    
    try:
        # Train for a specified number of timesteps with the custom callback for auto-saving
        auto_save_callback = CustomSaveCallback(save_path=model_save_path, save_freq=1000)
        model.learn(total_timesteps=TOTAL_TIMESTEPS, log_interval=LOG_INTERVAL, reset_num_timesteps=False, tb_log_name="PPO_unified", callback=auto_save_callback)
        print("Training finished. Saving model...")
        tmp_path = model_save_path + "_tmp"
        model.save(tmp_path)
        if os.path.exists(tmp_path + ".zip"):
            os.replace(tmp_path + ".zip", model_save_path + ".zip")
    except (KeyboardInterrupt, BaseException) as e:
        print(f"Training interrupted ({e}). Saving model...")
        tmp_path = model_save_path + "_tmp"
        model.save(tmp_path)
        if os.path.exists(tmp_path + ".zip"):
            os.replace(tmp_path + ".zip", model_save_path + ".zip")
    finally:
        env.close()

if __name__ == '__main__':
    main()