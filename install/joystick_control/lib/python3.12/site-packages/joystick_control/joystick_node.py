#!/usr/bin/env python3
"""
Joystick Driver Node
Reads Xbox controller input and publishes to /joy topic
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
import pygame


class JoystickNode(Node):
    def __init__(self):
        super().__init__("joystick_node")
        
        # Parameters
        self.declare_parameter('device_id', 0)
        self.declare_parameter('publish_rate', 100.0)  # Hz
        
        device_id = self.get_parameter('device_id').value
        publish_rate = self.get_parameter('publish_rate').value
        
        # Initialize pygame
        pygame.display.init()
        pygame.joystick.init()
        
        # Check for controllers
        joystick_count = pygame.joystick.get_count()
        if joystick_count == 0:
            self.get_logger().error("No controllers detected!")
            raise RuntimeError("No joystick found")
            
        self.get_logger().info(f"Found {joystick_count} controller(s)")
        
        # Initialize joystick
        self.joystick = pygame.joystick.Joystick(device_id)
        self.joystick.init()
        
        # Log controller details
        self.get_logger().info(f"Using controller: {self.joystick.get_name()}")
        self.get_logger().info(f"  Axes: {self.joystick.get_numaxes()}")
        self.get_logger().info(f"  Buttons: {self.joystick.get_numbuttons()}")
        self.get_logger().info(f"  Hats: {self.joystick.get_numhats()}")
        
        # Create publisher
        self.publisher = self.create_publisher(Joy, 'joy', 10)
        
        # Create timer
        timer_period = 1.0 / publish_rate
        self.timer = self.create_timer(timer_period, self.publish_joy)
        
        # State tracking for change detection
        self.last_axes = []
        self.last_buttons = []
        
        self.get_logger().info(f"Joystick node ready! Publishing at {publish_rate} Hz")
    
    def publish_joy(self):
        """Read joystick state and publish"""
        # Update pygame event queue
        pygame.event.pump()
        
        # Read all axes
        axes = [
            self.joystick.get_axis(i)
            for i in range(self.joystick.get_numaxes())
        ]
        
        # Read all buttons
        buttons = [
            self.joystick.get_button(i)
            for i in range(self.joystick.get_numbuttons())
        ]
        
        # Optional: Only publish on change to reduce traffic
        # Comment out if you want continuous publishing
        if axes == self.last_axes and buttons == self.last_buttons:
            return
        
        # Create and publish message
        msg = Joy()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'joystick'
        msg.axes = axes
        msg.buttons = buttons
        
        self.publisher.publish(msg)
        
        # Update state
        self.last_axes = axes
        self.last_buttons = buttons
    
    def destroy_node(self):
        """Cleanup"""
        self.get_logger().info("Shutting down joystick node")
        if hasattr(self, 'joystick'):
            pygame.quit()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = JoystickNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()