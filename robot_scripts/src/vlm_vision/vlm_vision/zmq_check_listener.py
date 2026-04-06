#!/usr/bin/env python3
"""
Pi 5: ZMQ REP listener — Pi 4 (or any REQ client) sends JSON; this calls ROS ``vlm/check_object`` and replies with JSON.

Wire: Pi 5 ``bind`` REP; Pi 4 ``connect`` REQ to the same address (e.g. ``tcp://pi5-ip:5559``).

Request (one JSON object per ZMQ message, UTF-8)::

    {"cmd": "check_object", "object_name": "apple"}

Response::

    {
      "ok": true,
      "success": true,
      "present": true,
      "yes_no": "yes",
      "raw_answer": "...",
      "message": "..."
    }

On protocol errors ``ok`` is false and ``error`` explains.
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict

import rclpy
from rclpy.node import Node
import zmq

from vlm_vision.srv import CheckObject


def _reply(sock: zmq.Socket, payload: Dict[str, Any]) -> None:
    sock.send_string(json.dumps(payload))


def main() -> None:
    parser = argparse.ArgumentParser(description='ZMQ listener -> vlm/check_object bridge')
    parser.add_argument(
        '--bind',
        dest='zmq_bind',
        default='tcp://*:5559',
        help='ZMQ REP bind address (default: tcp://*:5559)',
    )
    parser.add_argument(
        '--service',
        default='/vlm/check_object',
        help='ROS 2 CheckObject service name',
    )
    args = parser.parse_args()

    rclpy.init()
    node = Node('zmq_vlm_bridge')
    client = node.create_client(CheckObject, args.service)

    ctx = zmq.Context()
    sock = ctx.socket(zmq.REP)
    sock.bind(args.zmq_bind)
    node.get_logger().info(f'ZMQ REP listening on {args.zmq_bind!r} -> ROS {args.service!r}')

    while rclpy.ok():
        try:
            raw = sock.recv_string()
        except zmq.ZMQError as e:
            node.get_logger().error(f'ZMQ recv failed: {e}')
            break

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            _reply(sock, {'ok': False, 'error': f'invalid JSON: {e}'})
            continue

        if not isinstance(data, dict):
            _reply(sock, {'ok': False, 'error': 'message must be a JSON object'})
            continue

        cmd = data.get('cmd')
        if cmd != 'check_object':
            _reply(sock, {'ok': False, 'error': f'unknown cmd: {cmd!r}, expected check_object'})
            continue

        name = data.get('object_name', '')
        if not isinstance(name, str):
            name = str(name) if name is not None else ''

        req = CheckObject.Request()
        req.object_name = name

        if not client.wait_for_service(timeout_sec=5.0):
            _reply(
                sock,
                {
                    'ok': False,
                    'error': f'timeout waiting for ROS service {args.service!r} (is vlm_vision running?)',
                },
            )
            continue

        future = client.call_async(req)
        rclpy.spin_until_future_complete(node, future)
        try:
            resp = future.result()
        except Exception as e:
            _reply(sock, {'ok': False, 'error': f'ROS service call failed: {e}'})
            continue

        _reply(
            sock,
            {
                'ok': True,
                'success': bool(resp.success),
                'present': bool(resp.present),
                'yes_no': resp.yes_no,
                'raw_answer': resp.raw_answer,
                'message': resp.message,
            },
        )

    sock.close(0)
    ctx.term()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
