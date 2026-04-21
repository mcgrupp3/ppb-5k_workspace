#!/usr/bin/env python3
"""
PPB-5K State Manager Node — manual control mode
Runs on Pi 4 (Docker, ROS2 Jazzy)

Flow
----
1. X button                      → WAITING
2. /state_manager/set_target     → store object name
   /state_manager/set_description → store description (optional)
   (both can be set in any order while WAITING)
3. Once set_target received      → FIND (drive manually, press RB to query)
4. RB button                     → single VLM query
5. VLM YES                       → FOUND
6. B button (any state)          → IDLE reset
"""

from __future__ import annotations
import json
from enum import Enum, auto

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import Joy


class State(Enum):
    IDLE    = auto()
    WAITING = auto()
    FIND    = auto()
    FOUND   = auto()


class StateManagerNode(Node):

    def __init__(self) -> None:
        super().__init__('state_manager')

        self.declare_parameter('joy_button_start', 2)    # X
        self.declare_parameter('joy_button_reset', 1)    # B
        self.declare_parameter('joy_button_query', 10)   # RB

        self._state              : State     = State.IDLE
        self._object_name        : str       = ''
        self._description        : str       = ''
        self._joy_prev_buttons   : list[int] = []
        self._query_in_flight    : bool      = False

        # Publishers
        self._vlm_query_pub = self.create_publisher(String, '/vlm/query', 10)
        self._state_pub     = self.create_publisher(String, '/state_manager/state', 10)

        # Subscribers
        self.create_subscription(String, '/vlm/result',                  self._on_vlm_result,     10)
        self.create_subscription(String, '/state_manager/set_target',     self._on_set_target,     10)
        self.create_subscription(String, '/state_manager/set_description', self._on_set_description, 10)
        self.create_subscription(Joy,    '/joy',                          self._on_joy,            10)

        self.get_logger().info('State manager ready — IDLE. Press X to begin.')

    # ---------------------------------------------------------------- helpers

    def _set_state(self, new_state: State) -> None:
        if new_state == self._state:
            return
        self.get_logger().info(f'State: {self._state.name} → {new_state.name}')
        self._state = new_state
        msg = String()
        msg.data = new_state.name
        self._state_pub.publish(msg)

    def _reset(self) -> None:
        self._object_name     = ''
        self._description     = ''
        self._query_in_flight = False
        self._set_state(State.IDLE)
        self.get_logger().info('Reset — IDLE. Press X to begin.')

    def _build_prompt_summary(self) -> str:
        if self._description:
            return f'"{self._object_name}" — "{self._description}"'
        return f'"{self._object_name}"'

    # -------------------------------------------------------------- callbacks

    def _on_joy(self, msg: Joy) -> None:
        btn_start = self.get_parameter('joy_button_start').get_parameter_value().integer_value
        btn_reset = self.get_parameter('joy_button_reset').get_parameter_value().integer_value
        btn_query = self.get_parameter('joy_button_query').get_parameter_value().integer_value
        buttons   = list(msg.buttons)

        def rising_edge(idx: int) -> bool:
            prev = self._joy_prev_buttons[idx] if idx < len(self._joy_prev_buttons) else 0
            return idx < len(buttons) and buttons[idx] == 1 and prev == 0

        if rising_edge(btn_start) and self._state == State.IDLE:
            self._set_state(State.WAITING)
            self.get_logger().info(
                'WAITING — set target with /state_manager/set_target\n'
                '          optionally set description with /state_manager/set_description'
            )

        if rising_edge(btn_query) and self._state == State.FIND:
            self._send_query()

        if rising_edge(btn_reset):
            self._reset()

        self._joy_prev_buttons = buttons

    def _on_set_description(self, msg: String) -> None:
        self._description = msg.data.strip()
        self.get_logger().info(f'Description set: "{self._description}"')

    def _on_set_target(self, msg: String) -> None:
        target = msg.data.strip()
        if not target:
            return

        if self._state != State.WAITING:
            self.get_logger().warn(
                f'Target received in {self._state.name} — press X first.'
            )
            return

        self._object_name = target
        self.get_logger().info(
            f'Target set: {self._build_prompt_summary()} — '
            f'FIND mode. Drive around and press RB to query.'
        )
        self._set_state(State.FIND)

    def _on_vlm_result(self, msg: String) -> None:
        self._query_in_flight = False

        if self._state != State.FIND:
            return

        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().error(f'Bad VLM result JSON: {msg.data}')
            return

        present = data.get('present', False)
        raw     = data.get('raw_answer', '')

        self.get_logger().info(f'VLM result — present={present}, answer="{raw}"')

        if present:
            self.get_logger().info(f'Target FOUND: {self._build_prompt_summary()}')
            self._set_state(State.FOUND)
        else:
            self.get_logger().info('Not found — keep driving and press RB to query again.')

    # ----------------------------------------------------------------- query

    def _send_query(self) -> None:
        if self._query_in_flight:
            self.get_logger().warn('Query already in flight — wait for result.')
            return

        if not self._object_name:
            self.get_logger().warn('No target set.')
            return

        self._query_in_flight = True
        payload = {
            'object_name': self._object_name,
            'description': self._description,
        }
        msg = String()
        msg.data = json.dumps(payload)
        self._vlm_query_pub.publish(msg)
        self.get_logger().info(f'VLM query sent: {self._build_prompt_summary()}')


def main(args=None) -> None:
    rclpy.init(args=args)
    node = StateManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()