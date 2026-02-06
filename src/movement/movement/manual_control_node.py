#!/usr/bin/env python3
"""
Manual Control Node - Joystick teleop for mecanum robot
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from movement.motor_utils import MotorController


class ManualControlNode(Node):
    def __init__(self):
        super().__init__('manual_control_node')
        
        # Initialize motor controller
        self.get_logger().info('Initializing motor controller...')
        self.motor_controller = MotorController(max_speed=100)
        
        # Parameters
        self.declare_parameter('deadzone', 0.1)
        self.declare_parameter('max_speed', 0.5)  # Scale factor (0-1)
        
        self.deadzone = self.get_parameter('deadzone').value
        self.max_speed = self.get_parameter('max_speed').value
        
        # Subscribe to joystick
        self.joy_sub = self.create_subscription(
            Joy,
            'joy',
            self.joy_callback,
            10
        )
        
        self.get_logger().info('Manual control node ready!')
        self.get_logger().info(f'Controls:')
        self.get_logger().info(f'  Left stick: Forward/back + turning')
        self.get_logger().info(f'  Right stick: Rotation + strafing')
        self.get_logger().info(f'  Max speed: {self.max_speed * 100}%')
    
    def joy_callback(self, msg):
        """Process joystick input"""
        # Left stick
        left_y = msg.axes[1]   # Forward/backward
        left_x = msg.axes[0]   # Turning
        
        # Right stick
        right_y = msg.axes[3]  # Rotation
        right_x = msg.axes[2]  # Strafing
        
        # Determine which stick is active
        left_active = (abs(left_y) > self.deadzone or abs(left_x) > self.deadzone)
        
        if left_active:
            # Left stick: forward/back with turning
            vx = -left_y if abs(left_y) > self.deadzone else 0.0
            vy = 0.0
            omega = -left_x if abs(left_x) > self.deadzone else 0.0
        else:
            # Right stick: rotation or strafing (whichever is stronger)
            right_y_abs = abs(right_y)
            right_x_abs = abs(right_x)
            
            vx = 0.0
            if right_y_abs > right_x_abs and right_y_abs > self.deadzone:
                # Rotation
                vy = 0.0
                omega = -right_y
            elif right_x_abs > right_y_abs and right_x_abs > self.deadzone:
                # Strafing
                vy = right_x
                omega = 0.0
            else:
                vy = 0.0
                omega = 0.0
        
        # Scale by max_speed
        vx *= self.max_speed
        vy *= self.max_speed
        omega *= self.max_speed
        
        # Send to motors
        self.motor_controller.set_mecanum_velocity(vx, vy, omega)
    
    def destroy_node(self):
        """Clean shutdown"""
        self.get_logger().info('Shutting down motor controller...')
        self.motor_controller.cleanup()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ManualControlNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()