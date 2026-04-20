#!/usr/bin/env python3
"""
PPB-5K VLM Vision Node
Runs on Pi 5 (Docker, ROS2 Jazzy) — bridges ROS2 ↔ Pi 5 host ZMQ inference server.

Topic contract
--------------
Subscribes:
  /vlm/query    std_msgs/String   JSON {"object_name": "...", "description": "..."}

Publishes:
  /vlm/result   std_msgs/String   JSON {"present": bool, "yes_no": "yes"|"no", "raw_answer": "..."}

ZMQ
---
Sends REQ to Pi 5 host zmq_listener.py (localhost, configurable port).
Request:  {"command": "query", "prompt": "<built from object_name + description>"}
Response: {"status": "ok", "answer": "...", "time": "..."}

On ZMQ timeout the socket is closed and recreated (avoids REQ deadlock).
"""

from __future__ import annotations
import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

import zmq


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class VlmVisionNode(Node):

    def __init__(self) -> None:
        super().__init__('vlm_vision_node')

        self.declare_parameter('zmq_host', 'localhost')
        self.declare_parameter('zmq_port', 5555)
        self.declare_parameter('zmq_timeout_ms', 8000)   # 8 s — Hailo is ~2-3 s

        self._zmq_host       = self.get_parameter('zmq_host').get_parameter_value().string_value
        self._zmq_port       = self.get_parameter('zmq_port').get_parameter_value().integer_value
        self._zmq_timeout_ms = self.get_parameter('zmq_timeout_ms').get_parameter_value().integer_value

        self._ctx    = zmq.Context()
        self._socket = self._make_socket()

        self._result_pub = self.create_publisher(String, '/vlm/result', 10)

        self.create_subscription(String, '/vlm/query', self._on_query, 10)

        self.get_logger().info(
            f'VLM vision node ready — ZMQ target tcp://{self._zmq_host}:{self._zmq_port}'
        )

    # ---------------------------------------------------------------- helpers

    def _make_socket(self) -> zmq.Socket:
        """Create (or recreate) a REQ socket with a receive timeout."""
        sock = self._ctx.socket(zmq.REQ)
        sock.setsockopt(zmq.RCVTIMEO, self._zmq_timeout_ms)
        sock.setsockopt(zmq.LINGER, 0)
        sock.connect(f'tcp://{self._zmq_host}:{self._zmq_port}')
        return sock

    def _reset_socket(self) -> None:
        """Close current socket and open a fresh one (REQ deadlock recovery)."""
        try:
            self._socket.close(linger=0)
        except Exception:
            pass
        self._socket = self._make_socket()
        self.get_logger().warn('ZMQ socket recreated after timeout/error.')

    @staticmethod
    def _build_prompt(object_name: str, description: str) -> str:
        if description:
            return (
                f'Is there a {object_name} that looks like {description} '
                f'in this image? Answer only yes or no.'
            )
        return f'Is there a {object_name} in this image? Answer only yes or no.'

    # ------------------------------------------------------------ subscriber

    def _on_query(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().error(f'Malformed /vlm/query JSON: {msg.data}')
            return

        object_name = data.get('object_name', '').strip()
        description = data.get('description', '').strip()

        if not object_name:
            self.get_logger().error('/vlm/query missing object_name — ignoring.')
            return

        prompt = self._build_prompt(object_name, description)
        self.get_logger().info(f'Querying VLM: "{prompt}"')

        request = json.dumps({'command': 'query', 'prompt': prompt})

        try:
            self._socket.send_string(request)
            raw = self._socket.recv_string()
        except zmq.Again:
            self.get_logger().error('ZMQ timeout — no response from inference server.')
            self._reset_socket()
            self._publish_result(present=False, yes_no='no', raw_answer='timeout')
            return
        except zmq.ZMQError as e:
            self.get_logger().error(f'ZMQ error: {e}')
            self._reset_socket()
            self._publish_result(present=False, yes_no='no', raw_answer=f'error: {e}')
            return

        self.get_logger().info(f'ZMQ response: {raw}')

        try:
            resp = json.loads(raw)
        except json.JSONDecodeError:
            self.get_logger().error(f'Non-JSON ZMQ response: {raw}')
            self._publish_result(present=False, yes_no='no', raw_answer=raw)
            return

        if resp.get('status') != 'ok':
            self.get_logger().error(f'Inference server returned error: {resp}')
            self._publish_result(present=False, yes_no='no', raw_answer=str(resp))
            return

        answer = resp.get('answer', '').strip().lower()
        present = answer.startswith('yes')
        yes_no  = 'yes' if present else 'no'
        self._publish_result(present=present, yes_no=yes_no, raw_answer=answer)

    def _publish_result(self, *, present: bool, yes_no: str, raw_answer: str) -> None:
        payload = {
            'present':    present,
            'yes_no':     yes_no,
            'raw_answer': raw_answer,
        }
        msg = String()
        msg.data = json.dumps(payload)
        self._result_pub.publish(msg)
        self.get_logger().info(f'Published /vlm/result: {payload}')

    # --------------------------------------------------------------- cleanup

    def destroy_node(self) -> None:
        try:
            self._socket.close(linger=0)
            self._ctx.term()
        except Exception:
            pass
        super().destroy_node()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(args=None) -> None:
    rclpy.init(args=args)
    node = VlmVisionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()