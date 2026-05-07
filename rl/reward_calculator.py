import math

class RewardCalculator:
    def __init__(self, max_speed=0.5, max_turn=1.7, finish_reward=300.0, reward_mode='vision', stationary_threshold=0.1):
        self.max_speed = max_speed
        self.max_turn = max_turn
        self.finish_reward = finish_reward
        self.reward_mode = reward_mode
        self.stationary_threshold = stationary_threshold 
        
        
    def calculate_reward(self, error, linear_speed, angular_speed, prev_angular_speed):
        """
        Calculates the immediate reward, penalties, and stability factors
        based on the robot's current speed and visually detected error.
        
        Returns:
            reward: The calculated float reward
        """
        if self.reward_mode == 'coordinate':
            return self._calculate_coordinate_reward(error, linear_speed, angular_speed, prev_angular_speed)
        else:
            return self._calculate_vision_reward(error, linear_speed, angular_speed, prev_angular_speed)

    def _calculate_coordinate_reward(self, error, linear_speed, angular_speed, prev_angular_speed):
        stability_factor = math.exp(-6.5 * abs(error))
        speed_factor = max(0.0, linear_speed) / self.max_speed
        progress_reward = speed_factor * stability_factor

        survival_bonus = 0.25
        stationary_penalty = 0.5 if linear_speed < self.stationary_threshold else 0.0
        
        steering_change = abs(angular_speed - prev_angular_speed)
        smoothness_penalty = (steering_change / (2.0 * self.max_turn)) * 0.5 
        steering_penalty = (abs(angular_speed) / self.max_turn) * 0.25

        reward = (progress_reward + survival_bonus - 
                  stationary_penalty - 
                  smoothness_penalty - 
                  steering_penalty) * 5.0 
        return reward

    def _calculate_vision_reward(self, error, linear_speed, angular_speed, prev_angular_speed):

        stability_factor = math.exp(-4.5 * abs(error))
        speed_factor = max(0.0, linear_speed) / self.max_speed

        # 1. Progress reward (only if actually moving)
        progress_reward = 0.0
        if linear_speed > 0.05:
            progress_reward = speed_factor * stability_factor * 12.0

        # 2. Center bonus (reward if close to the center of the line)
        center_bonus = 0.0
        if abs(error) < 0.10:
            center_bonus = 0.5

        # 3. Survival bonus (very small, to prevent optimizing only for survival)
        survival_bonus = 0.01

        # 4. Off-center penalty (penalty if far from the center, but only if actually seeing the line)
        off_center_penalty = (max(0.0, (abs(error) - 0.5)) * 0.5)

        # 5. Explicit penalty for spinning in place (penalty for spinning in place)
        spin_penalty = 0.0
        if linear_speed < 0.05 and abs(angular_speed) > 0.2:
            spin_penalty = 0.5  

        # 6. Small penalty for idling (penalty for idling)
        idle_penalty = 0.0
        if linear_speed < 0.05:
            idle_penalty = 0.2

        # Combined weighted reward (only the main components)
        reward = (progress_reward + center_bonus + survival_bonus - off_center_penalty - spin_penalty - idle_penalty) * (5.0 / 3.0)
        return reward
        
    def calculate_termination_reward(self, terminated, crossed_finish, current_step, grace_period=5):
        """
        Calculates termination modifications to the reward based on success/failure.
        Allows separate penalties for vision and coordinate modes.
        Returns:
            bonus_or_penalty: Reward addition or subtraction
            modified_terminated: Overridden termination state
        """
        # Set penalties for each mode
        if self.reward_mode == 'vision':
            termination_penalty = -100.0
        else:
            termination_penalty = -100.0

        if crossed_finish:
            return self.finish_reward, True

        if terminated and not crossed_finish:
            if current_step < grace_period:
                # Grace period at the beginning of the episode to find the line
                return 0.0, False
            else:
                return termination_penalty, True

        return 0.0, terminated
