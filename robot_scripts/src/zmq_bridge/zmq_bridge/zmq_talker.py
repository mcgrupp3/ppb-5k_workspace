#!/usr/bin/env python3
"""
ZMQ Talker Node
Subscribes to /joy, watches for RB button (index 5),
sends JSON commands to Pi 5 over ZMQ REQ socket.

Launch:
  ros2 run zmq_bridge zmq_talker_node --ros-args -p pi5_ip:=192.168.0.2 -p pi5_port:=5555
"""

import json
import zmq
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy


RB_BUTTON = 5  # Xbox controller RB index (pygame mapping)


class ZmqTalkerNode(Node):
    def __init__(self):
        super().__init__('zmq_talker_node')

        self.declare_parameter('pi5_ip',   '192.168.0.2')
        self.declare_parameter('pi5_port', 5555)

        ip   = self.get_parameter('pi5_ip').value
        port = self.get_parameter('pi5_port').value

        # ZMQ REQ socket
        self._ctx  = zmq.Context()
        self._sock = self._ctx.socket(zmq.REQ)
        self._sock.connect(f'tcp://{ip}:{port}')
        self._sock.setsockopt(zmq.RCVTIMEO, 3000)  # 3s reply timeout
        self.get_logger().info(f'ZMQ REQ connected to tcp://{ip}:{port}')

        self._rb_prev = 0
        self.create_subscription(Joy, 'joy', self._joy_cb, 10)
        self.get_logger().info('ZMQ talker ready — watching RB button')

    def _joy_cb(self, msg: Joy):
        if len(msg.buttons) <= RB_BUTTON:
            return

        rb = msg.buttons[RB_BUTTON]

        # Rising edge only — send once per press
        if rb == 1 and self._rb_prev == 0:
            self._send_command({'cmd': 'check_object', 'object_name': 'dog'})

        self._rb_prev = rb

    def _send_command(self, cmd: dict):
        self.get_logger().info(f'Sending: {cmd}')
        try:
            self._sock.send_string(json.dumps(cmd))
            reply = json.loads(self._sock.recv_string())
            self.get_logger().info(f'Reply: {reply}')
        except zmq.Again:
            self.get_logger().warn('ZMQ timeout — no reply from Pi 5')
        except Exception as e:
            self.get_logger().error(f'ZMQ error: {e}')

    def destroy_node(self):
        self._sock.close()
        self._ctx.term()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    try:
        node = ZmqTalkerNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
