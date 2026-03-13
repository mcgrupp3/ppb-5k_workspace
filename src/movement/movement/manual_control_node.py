#!/usr/bin/env python3
"""
Manual Control Node - Joystick teleop for mecanum robot
Sends velocity commands to Pico over UART
"""

import struct
import serial
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy


class PicoSerial:
    """
    Sends vx/vy/omega commands to Pico over UART.
    Packet format: [0xFF][vx][vy][omega][checksum]
    vx/vy/omega are int8 (-100 to 100)
    """

    def __init__(self, port='/dev/ttyAMA3', baud=115200):
        self.ser = serial.Serial(port, baud, timeout=0)

    def send_velocity(self, vx: float, vy: float, omega: float):
        self.ser.reset_output_buffer()
        self.ser.reset_input_buffer()
        vx_i    = int(max(-100, min(100, vx    * 100)))
        vy_i    = int(max(-100, min(100, vy    * 100)))
        omega_i = int(max(-100, min(100, omega * 100)))

        chk = (vx_i + vy_i + omega_i) & 0xFF
        packet = bytes([
            0xFF,
            vx_i    & 0xFF,
            vy_i    & 0xFF,
            omega_i & 0xFF,
            chk
        ])
        self.ser.write(packet)

    def stop(self):
        self.send_velocity(0.0, 0.0, 0.0)

    def close(self):
        self.stop()
        self.ser.close()


class ManualControlNode(Node):
    def __init__(self):
        super().__init__('manual_control_node')

        # Parameters
        self.declare_parameter('deadzone',   0.1)
        self.declare_parameter('max_speed',  0.5)
        self.declare_parameter('uart_port',  '/dev/ttyAMA3')
        self.declare_parameter('uart_baud',  115200)
        self.declare_parameter('alpha', 0.4)

        self.deadzone  = self.get_parameter('deadzone').value
        self.max_speed = self.get_parameter('max_speed').value
        port           = self.get_parameter('uart_port').value
        baud           = self.get_parameter('uart_baud').value
        self.ALPHA     = self.get_parameter('alpha').value

        # Init Pico UART link
        self.get_logger().info(f'Opening UART to Pico on {port} at {baud}...')
        self.pico = PicoSerial(port=port, baud=baud)

        # Subscribe to joystick
        self.joy_sub = self.create_subscription(Joy, 'joy', self.joy_callback, 10)

        self.get_logger().info('Manual control node ready!')
        self.get_logger().info('  Left stick:  Forward/back + turning')
        self.get_logger().info('  Right stick: Rotation + strafing')
        self.get_logger().info(f'  Max speed: {self.max_speed * 100:.0f}%')

        # In __init__, add:
        self.ready        = False
        self.vx_smooth    = 0.0
        self.vy_smooth    = 0.0
        self.omega_smooth = 0.0
        self.last_send = 0.0
        self.SEND_HZ   = 20  # send at most 20 times/sec

    # def joy_callback(self, msg):
    #     """Process joystick input and send to Pico."""
    #     left_y  = msg.axes[1]
    #     left_x  = msg.axes[0]
    #     right_y = msg.axes[3]
    #     right_x = msg.axes[2]

    #     left_active = (abs(left_y) > self.deadzone or abs(left_x) > self.deadzone)

    #     if left_active:
    #         vx    = -left_y if abs(left_y) > self.deadzone else 0.0
    #         vy    = 0.0
    #         omega = -left_x if abs(left_x) > self.deadzone else 0.0
    #     else:
    #         vx = 0.0
    #         if abs(right_y) > abs(right_x) and abs(right_y) > self.deadzone:
    #             vy    = 0.0
    #             omega = -right_y
    #         elif abs(right_x) > abs(right_y) and abs(right_x) > self.deadzone:
    #             vy    = right_x
    #             omega = 0.0
    #         else:
    #             vy    = 0.0
    #             omega = 0.0

    #     # Scale and send
    #     self.pico.send_velocity(
    #         vx    * self.max_speed,
    #         vy    * self.max_speed,
    #         omega * self.max_speed
    #     )

    def joy_callback(self, msg):
        if not self.ready:
            self.ready = True
            return

        now = self.get_clock().now().nanoseconds / 1e9
        if now - self.last_send < 1.0 / self.SEND_HZ:
            return
        self.last_send = now

        vx    = -msg.axes[1]
        vy    =  msg.axes[0]
        omega =  msg.axes[3]

        # Apply deadzone
        vx    = vx    if abs(vx)    > self.deadzone else 0.0
        vy    = vy    if abs(vy)    > self.deadzone else 0.0
        omega = omega if abs(omega) > self.deadzone else 0.0

        # Smooth
        self.vx_smooth    = self.ALPHA * vx    + (1 - self.ALPHA) * self.vx_smooth
        self.vy_smooth    = self.ALPHA * vy    + (1 - self.ALPHA) * self.vy_smooth
        self.omega_smooth = self.ALPHA * omega + (1 - self.ALPHA) * self.omega_smooth

        self.pico.send_velocity(
            self.vx_smooth    * self.max_speed,
            self.vy_smooth    * self.max_speed,
            self.omega_smooth * self.max_speed
        )

    def destroy_node(self):
        self.get_logger().info('Shutting down, stopping motors...')
        self.pico.close()
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