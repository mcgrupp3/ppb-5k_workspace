#!/usr/bin/env python3
"""
Autonomous Motor Controller
Subscribes to /cmd_vel (Twist) from Nav2 and drives motors via MotorController.
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

from movement.motor_utils import MotorController


class AutonomousMotorController(Node):
    def __init__(self):
        super().__init__('autonomous_motor_controller')

        self.declare_parameter('max_speed', 0.8)
        max_speed = self.get_parameter('max_speed').value

        self.get_logger().info('Initializing GPIO motor controller...')
        self.motors = MotorController(max_speed=max_speed)

        self.cmd_vel_sub = self.create_subscription(
            Twist, 'cmd_vel', self._cmd_vel_cb, 10
        )

        self.get_logger().info(
            f'Autonomous motor controller ready | max_speed={max_speed}'
        )

    def _cmd_vel_cb(self, msg: Twist):
        vx    = msg.linear.x
        vy    = msg.linear.y
        omega = msg.angular.z

        self.get_logger().debug(
            f'cmd_vel → vx={vx:.2f}  vy={vy:.2f}  omega={omega:.2f}'
        )

        self.motors.set_mecanum_velocity(vx, vy, omega)

    def destroy_node(self):
        self.get_logger().info('Shutting down — stopping motors')
        self.motors.cleanup()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = AutonomousMotorController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()