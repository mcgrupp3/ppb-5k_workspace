#!/usr/bin/env python3
"""
Manual Control Node - Joystick teleop for mecanum robot
Drives motors directly via GPIO to L298N drivers (no Pico)
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy

from movement.motor_utils import MotorController


class ManualControlNode(Node):
    def __init__(self):
        super().__init__('manual_control_node')

        # Parameters
        self.declare_parameter('movement_type', 'manual')   # manual | auto
        self.declare_parameter('deadzone',      0.1)
        self.declare_parameter('max_speed',     0.8)        # 0.0–1.0
        self.declare_parameter('alpha',         0.4)        # smoothing: lower=smoother, higher=snappier
        self.declare_parameter('send_hz',       20.0)

        self.movement_type = self.get_parameter('movement_type').value
        self.deadzone      = self.get_parameter('deadzone').value
        self.max_speed     = self.get_parameter('max_speed').value
        self.ALPHA         = self.get_parameter('alpha').value
        self.SEND_HZ       = self.get_parameter('send_hz').value

        # Init motor controller
        self.get_logger().info('Initializing GPIO motor controller...')
        self.motors = MotorController(max_speed=self.max_speed)

        # Subscribe to joystick
        self.joy_sub = self.create_subscription(Joy, 'joy', self.joy_callback, 10)

        self.get_logger().info(f'Manual control node ready! [mode={self.movement_type}]')
        self.get_logger().info('  Left stick Y:  Forward / back')
        self.get_logger().info('  Left stick X:  Strafe left / right')
        self.get_logger().info('  Right stick X: Rotate')
        self.get_logger().info(f'  Max speed: {self.max_speed * 100:.0f}%  |  Alpha: {self.ALPHA}  |  Send Hz: {self.SEND_HZ}')

        self.ready        = False
        self.vx_smooth    = 0.0
        self.vy_smooth    = 0.0
        self.omega_smooth = 0.0
        self.last_send    = 0.0

    def joy_callback(self, msg):
        if not self.ready:
            self.ready = True
            return

        now = self.get_clock().now().nanoseconds / 1e9
        if now - self.last_send < 1.0 / self.SEND_HZ:
            return
        self.last_send = now

        vx    = -msg.axes[1]   # left stick Y (negated: push forward = positive)
        vy    =  msg.axes[0]   # left stick X
        omega =  msg.axes[3]   # right stick X

        # Deadzone
        vx    = vx    if abs(vx)    > self.deadzone else 0.0
        vy    = vy    if abs(vy)    > self.deadzone else 0.0
        omega = omega if abs(omega) > self.deadzone else 0.0

        # Exponential smoothing
        self.vx_smooth    = self.ALPHA * vx    + (1 - self.ALPHA) * self.vx_smooth
        self.vy_smooth    = self.ALPHA * vy    + (1 - self.ALPHA) * self.vy_smooth
        self.omega_smooth = self.ALPHA * omega + (1 - self.ALPHA) * self.omega_smooth

        self.get_logger().debug(
            f'sending: vx={self.vx_smooth:.2f} vy={self.vy_smooth:.2f} omega={self.omega_smooth:.2f}'
        )

        # Values are -1.0 to 1.0, MotorController scales by max_speed internally
        self.motors.set_mecanum_velocity(
            self.vx_smooth,
            self.vy_smooth,
            self.omega_smooth,
        )

    def destroy_node(self):
        self.get_logger().info('Shutting down, stopping motors...')
        self.motors.cleanup()
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
