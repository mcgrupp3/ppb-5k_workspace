#!/usr/bin/env python3
"""
ZMQ Listener Node (Pi 4 side)
Receives JSON responses pushed from Pi 5 and publishes
them to /zmq_response as a std_msgs/String.

Note: This is separate from the REQ/REP loop in the talker.
Use this if Pi 5 needs to push unsolicited messages to Pi 4.

Launch:
  ros2 run zmq_bridge zmq_listener_node --ros-args -p listen_port:=5556
"""

import json
import threading
import zmq
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class ZmqListenerNode(Node):
    def __init__(self):
        super().__init__('zmq_listener_node')

        self.declare_parameter('listen_port', 5556)
        port = self.get_parameter('listen_port').value

        self._pub = self.create_publisher(String, 'zmq_response', 10)

        # ZMQ PULL socket — Pi 5 pushes unsolicited messages here
        self._ctx  = zmq.Context()
        self._sock = self._ctx.socket(zmq.PULL)
        self._sock.bind(f'tcp://0.0.0.0:{port}')
        self.get_logger().info(f'ZMQ PULL bound on port {port}')

        # Non-blocking receive loop in background thread
        self._running = True
        self._thread  = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()

    def _recv_loop(self):
        self._sock.setsockopt(zmq.RCVTIMEO, 500)  # poll every 500ms so we can check _running
        while self._running and rclpy.ok():
            try:
                raw  = self._sock.recv_string()
                data = json.loads(raw)
                self.get_logger().info(f'Received from Pi 5: {data}')
                msg      = String()
                msg.data = json.dumps(data)
                self._pub.publish(msg)
            except zmq.Again:
                continue  # timeout, loop again
            except Exception as e:
                self.get_logger().error(f'ZMQ recv error: {e}')

    def destroy_node(self):
        self._running = False
        self._thread.join(timeout=1.0)
        self._sock.close()
        self._ctx.term()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    try:
        node = ZmqListenerNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
