import rclpy
import time
import math
import os
import re
import subprocess
import tempfile
from gazebo_msgs.srv import SpawnEntity, DeleteEntity, SetEntityState
from std_srvs.srv import Empty

from gazebo_utils import TrackGenerator

class GazeboEntityManager:
    def __init__(self, node, robot_name='two_wheeled_robot', line_model_name='track_line', urdf_path=''):
        self.node = node
        self.robot_name = robot_name
        self.line_model_name = line_model_name
        self.urdf_path = urdf_path
        
        self.spawn_client = self.node.create_client(SpawnEntity, '/spawn_entity')
        self.delete_client = self.node.create_client(DeleteEntity, '/delete_entity')
        self.set_state_client = self.node.create_client(SetEntityState, '/set_entity_state')
        self.pause_client = self.node.create_client(Empty, '/pause_physics')
        self.unpause_client = self.node.create_client(Empty, '/unpause_physics')

        self.track_version = 0
        self.global_track_counter = 0
        self.global_track_counter = 0
        self.current_visible_track = None
        self.missing_service_count = 0

    def pause_physics(self):
        req = Empty.Request()
        if self.pause_client.wait_for_service(timeout_sec=1.0):
            try:
                future = self.pause_client.call_async(req)
                rclpy.spin_until_future_complete(self.node, future, timeout_sec=2.0)
            except Exception:
                pass

    def unpause_physics(self):
        req = Empty.Request()
        if self.unpause_client.wait_for_service(timeout_sec=1.0):
            try:
                future = self.unpause_client.call_async(req)
                rclpy.spin_until_future_complete(self.node, future, timeout_sec=2.0)
            except Exception:
                pass

    def reset_robot_position(self, spawn_x, spawn_y, yaw=-3.14):
        """Reset robot to starting position without respawning (faster)."""
        success = False

        # Közvetlen Gazebo C++ CLI használata! Ez a leggyorsabb és Nálad mentes az összes ROS plugin bugtól!
        if self.set_state_client.wait_for_service(timeout_sec=1.0):
            try:
                req = SetEntityState.Request()
                req.state.name = self.robot_name
                req.state.reference_frame = "world"
                req.state.pose.position.x = float(spawn_x)
                req.state.pose.position.y = float(spawn_y)
                req.state.pose.position.z = 0.1 
                
                import math
                cy = math.cos(yaw * 0.5)
                sy = math.sin(yaw * 0.5)
                req.state.pose.orientation.w = cy
                req.state.pose.orientation.z = sy
                req.state.pose.orientation.x = 0.0
                req.state.pose.orientation.y = 0.0
                
                
                req.state.twist.linear.x = 0.0
                req.state.twist.linear.y = 0.0
                req.state.twist.linear.z = 0.0
                req.state.twist.angular.x = 0.0
                req.state.twist.angular.y = 0.0
                req.state.twist.angular.z = 0.0

                future = self.set_state_client.call_async(req)
                rclpy.spin_until_future_complete(self.node, future, timeout_sec=2.0)
                if future.result() is not None and future.result().success:
                    success = True
            except Exception as e:
                self.node.get_logger().error(f"SetEntityState failed: {e}")
                
        if not success:
            # Fallback
            cmd = [
                "gz", "model", "-m", self.robot_name,
                "-x", str(spawn_x), "-y", str(spawn_y), "-z", "0.05",
                "-Y", str(yaw) 
            ]
            for _ in range(3):
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
                    if res.returncode == 0:
                        success = True
                        break
                except Exception:
                    pass
                time.sleep(0.5)

        if not success:
            self.node.get_logger().warn("C++ level gz model CLI teleport failed, using full respawn!")
            return False
            
        return True

    def delete_entity(self, name):
        
        
        time.sleep(0.5)
        
        req = DeleteEntity.Request()
        req.name = name

        max_retries = 3
        for attempt in range(max_retries):
            if not self.delete_client.wait_for_service(timeout_sec=2.0):
                self.node.get_logger().warning(f"DeleteEntity service not available in rclpy, attempting terminal (CLI) fallback: {name}")
                try:
                    cmd = ["ros2", "service", "call", "/delete_entity", "gazebo_msgs/srv/DeleteEntity", f"{{name: '{name}'}}"]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
                    if "success=True" in res.stdout or "successs=True" in res.stderr:
                        return True
                except Exception as e:
                    pass
                time.sleep(1.0)
                continue
                
            try:
                future = self.delete_client.call_async(req)
                rclpy.spin_until_future_complete(self.node, future, timeout_sec=2.0)
                
                if future.result() is not None and future.result().success:
                    return True
                else:
                    self.node.get_logger().warning(f"Failed to delete entity: {name} (it may no longer exist).")
                    return False
            except Exception as e:
                self.node.get_logger().error(f"Error calling delete_entity: {e}")
                time.sleep(1.0)
        
        self.node.get_logger().error("DeleteEntity service is permanently unavailable!")
        

        try:
            with open('/tmp/gazebo_fatal_error.flag', 'w') as f:
                f.write('FATAL: DeleteEntity service is permanently unavailable')
        except:
            pass
        os._exit(1)
        
        return False

    def spawn_entity(self, name, xml, x, y, z, roll=0.0, pitch=0.0, yaw=0.0):
        """Spawn an entity in Gazebo robustly."""
        
        time.sleep(0.5)
        
        req = SpawnEntity.Request()
        req.name = name
        req.xml = xml
        req.initial_pose.position.x = float(x)
        req.initial_pose.position.y = float(y)
        req.initial_pose.position.z = float(z)
        
        cy = math.cos(yaw * 0.5); sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5); sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5); sr = math.sin(roll * 0.5)
        
        req.initial_pose.orientation.w = cr * cp * cy + sr * sp * sy
        req.initial_pose.orientation.x = sr * cp * cy - cr * sp * sy
        req.initial_pose.orientation.y = cr * sp * cy + sr * cp * sy
        req.initial_pose.orientation.z = cr * cp * sy - sr * sp * cy

        # 1. API attempt
        if self.spawn_client.wait_for_service(timeout_sec=5.0):
            try:
                
                future = self.spawn_client.call_async(req)
                rclpy.spin_until_future_complete(self.node, future, timeout_sec=15.0)
                if future.result() is not None and future.result().success:
                    return True
            except Exception:
                pass
                
        # 2. CLI fallback
        self.node.get_logger().warn(f"API spawn failed for {name}. Returning False to retry.")
        return False

    def respawn_robot(self, spawn_x, spawn_y, current_camera_pitch, yaw=-3.14):
        """Delete and respawn the robot with modified camera pitch."""
        max_retries = 3
        
        for attempt in range(max_retries):
            # Read and modify URDF with new camera pitch
            try:
                with open(self.urdf_path, 'r') as f:
                    urdf_content = f.read()
                
                pattern = r'(<joint name="camera_joint"[^>]*>.*?rpy=")[^"]*(")'
                replacement = rf'\g<1>0 {current_camera_pitch} 0\2'
                modified_urdf = re.sub(pattern, replacement, urdf_content)
                
                # Spawn robot at start position
                success = self.spawn_entity(
                    self.robot_name,
                    modified_urdf,
                    spawn_x, spawn_y, 0.2,
                    yaw=yaw  
                )
                
                if success:
                    self.node.get_logger().info(f"Robot respawned (attempt {attempt+1}) with camera pitch: {math.degrees(current_camera_pitch):.1f}°")
                    return True
                else:
                    self.node.get_logger().warn(f"Failed to respawn robot (attempt {attempt+1}/{max_retries})")
                    time.sleep(1.0)  # Wait before retry
                    
            except Exception as e:
                self.node.get_logger().error(f"Error respawning robot: {e}")
                time.sleep(1.0)
        
        self.node.get_logger().error("Failed to respawn robot after all retries!")
        
        
        try:
            with open('/tmp/gazebo_fatal_error.flag', 'w') as f:
                f.write('FATAL: Respawn limit reached')
        except:
            pass
        os._exit(1) # Azonnal kinyírjuk a python scriptet hibakóddal
        
        return False

    def respawn_line(self, track_points, spline_resolution, line_width):
        # inicialize spawned_tracks dictionary on first call
        if not hasattr(self, 'spawned_tracks'):
            self.spawned_tracks = {}
            
        #Deleting the old track (if exists)
        if self.track_version == 0:
            req = DeleteEntity.Request()
            for i in range(1, 5):
                req.name = f"track_line_v{i}"
                if self.delete_client.wait_for_service(timeout_sec=0.1):
                    self.delete_client.call_async(req)
            req.name = "track_line"
            if self.delete_client.wait_for_service(timeout_sec=0.1):
                self.delete_client.call_async(req)
            
            self.track_version = 1
            import time
            time.sleep(0.5)

        track_hash = hash(str(track_points))
        
        # Only spawn a new track if we haven't seen this exact track configuration before. If we have, just teleport the existing one up and the previously visible one down.
        if track_hash not in self.spawned_tracks:
            self.global_track_counter += 1
            self.line_model_name = f"track_line_{self.global_track_counter}"
            self.node.get_logger().info(f"Generating and parking new track: {self.line_model_name}")
            
            from gazebo_utils import TrackGenerator
            import math
            spline_points = TrackGenerator._catmull_rom_spline(track_points, spline_resolution)
            segments_sdf = ""
            segment_id = 0
            
            for i in range(len(spline_points) - 1):
                x1, y1 = spline_points[i]
                x2, y2 = spline_points[i + 1]
                
                length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                if length < 0.001:
                    continue
                    
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                angle = math.atan2(y2 - y1, x2 - x1)
                
                
                segments_sdf += f'''
          <visual name="visual_{segment_id}">
            <pose>{center_x} {center_y} 0.015 0 0 {angle}</pose>
            <geometry>
              <box>
                <size>{length + 0.005} {line_width} 0.002</size>
              </box>
            </geometry>
            <material>
              <script>
                <uri>file://media/materials/scripts/gazebo.material</uri>
                <name>Gazebo/Red</name>
              </script>
            </material>
          </visual>'''
                segment_id += 1
            
            # Build the full SDF for the track model with all segments
            sdf = f'''<?xml version="1.0"?>
    <sdf version="1.6">
      <model name="{self.line_model_name}">
        <static>false</static>
        <link name="track_link">
          <kinematic>true</kinematic>
          <gravity>0</gravity>
          <inertial>
            <mass>10.0</mass>
            <inertia>
              <ixx>1.0</ixx><iyy>1.0</iyy><izz>1.0</izz>
            </inertia>
          </inertial>{segments_sdf}
        </link>
      </model>
    </sdf>'''
            
            # Spawn the new track model underground (z=-10.0) so it's not visible until we teleport it up. This avoids any flickering or physics issues with spawning directly at z=0.0.
            success = self.spawn_entity(self.line_model_name, sdf, 0.0, 0.0, -10.0)
            
            import time
            if success:
                self.spawned_tracks[track_hash] = self.line_model_name
                time.sleep(0.5) 
            else:
                self.node.get_logger().warn(f"Failed to build track: {self.line_model_name}")
                return

        
        from gazebo_msgs.srv import SetEntityState
        
        # Pause during teleportation of kinematic tracks so physics engine doesn't trip up
        for h, model_name in self.spawned_tracks.items():
            target_z = 0.0 if h == track_hash else -10.0
            
            # Optimization: only teleport the newly requested track and the PREVIOUSLY visible track down!
            if h != track_hash and h != getattr(self, 'current_visible_track', None):
                continue
                
            if self.set_state_client.wait_for_service(timeout_sec=2.0):
                self.missing_service_count = 0
                try:
                    req = SetEntityState.Request()
                    req.state.name = model_name
                    req.state.reference_frame = "world"
                    # Only teleport Z coordinate! 
                   
                    req.state.pose.position.x = 0.0
                    req.state.pose.position.y = 0.0
                    req.state.pose.position.z = target_z
                    # Kinematic object needs to explicitly tell Gazebo its orientation
                    req.state.pose.orientation.w = 1.0
                    req.state.pose.orientation.x = 0.0
                    req.state.pose.orientation.y = 0.0
                    req.state.pose.orientation.z = 0.0
                    
                    # Also zero out velocity explicitly
                    req.state.twist.linear.x = 0.0
                    req.state.twist.linear.y = 0.0
                    req.state.twist.linear.z = 0.0
                    req.state.twist.angular.x = 0.0
                    req.state.twist.angular.y = 0.0
                    req.state.twist.angular.z = 0.0

                    future = self.set_state_client.call_async(req)
                    rclpy.spin_until_future_complete(self.node, future, timeout_sec=5.0)
                except Exception as e:
                    self.node.get_logger().error(f"Set track state failed: {e}")
            else:
                self.node.get_logger().error(f"SetEntityState service not found! Track {model_name} might be stuck.")
                self.missing_service_count += 1
                if self.missing_service_count >= 3:
                    import os
                    import sys
                    open("/tmp/gazebo_fatal_error.flag", "w").close()
                    self.node.get_logger().fatal("SetEntityState missing 3 times! GAZEBO IS DEAD. TRIGGERING WATCHDOG.")
                    sys.exit(1)
                
            if h == track_hash:
                self.node.get_logger().info(f"Track on Surface (Visible): {model_name}")
                
        self.current_visible_track = track_hash
        import time
        time.sleep(0.1)
