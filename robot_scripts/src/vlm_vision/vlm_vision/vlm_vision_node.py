#!/usr/bin/env python3
"""
ROS 2 node: buffer camera frames; on ``CheckObject`` service call run VLM with
``Is there {object} in this image?`` (configurable template) and return yes/no for the MCU.
"""
from __future__ import annotations

import threading
from typing import Optional

import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image

from vlm_vision.srv import CheckObject
from vlm_vision.vlm_pipeline import build_backend, describe_image_bgr
from vlm_vision.vlm_yes_no import parse_yes_no


class VlmVisionNode(Node):
    def __init__(self) -> None:
        super().__init__('vlm_vision')

        self.declare_parameter('image_topic', '/camera/image_raw')
        self.declare_parameter(
            'prompt_template',
            'Is there an {object} in this image? You must answer with only the word yes or the word no.',
        )
        self.declare_parameter('inference_timeout', 60)

        self._bridge = CvBridge()
        self._frame_lock = threading.Lock()
        self._last_bgr: Optional[np.ndarray] = None

        self._backend = None
        try:
            self._backend = build_backend()
            self.get_logger().info('VLM backend initialized.')
        except Exception as e:
            self.get_logger().error(f'VLM backend failed to load (will retry on first call): {e}')

        self._busy = threading.Lock()

        topic = self.get_parameter('image_topic').get_parameter_value().string_value
        self.create_subscription(Image, topic, self._on_image, 1)

        self.create_service(CheckObject, 'vlm/check_object', self._on_check_object)

        self.get_logger().info(
            f'vlm_vision ready. Subscribing to {topic!r}; call service vlm/check_object (CheckObject).'
        )

    def _on_image(self, msg: Image) -> None:
        try:
            bgr = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().warn(f'cv_bridge failed: {e}')
            return
        with self._frame_lock:
            self._last_bgr = bgr

    def _on_check_object(
        self,
        request: CheckObject.Request,
        response: CheckObject.Response,
    ) -> CheckObject.Response:
        name = (request.object_name or '').strip()
        if not name:
            response.success = False
            response.present = False
            response.yes_no = ''
            response.raw_answer = ''
            response.message = 'object_name is empty'
            return response

        if not self._busy.acquire(blocking=False):
            response.success = False
            response.present = False
            response.yes_no = ''
            response.raw_answer = ''
            response.message = 'busy (another check in progress)'
            return response

        try:
            with self._frame_lock:
                frame = None if self._last_bgr is None else self._last_bgr.copy()
            if frame is None:
                response.success = False
                response.present = False
                response.yes_no = ''
                response.raw_answer = ''
                response.message = 'no camera frame yet'
                return response

            if self._backend is None:
                try:
                    self._backend = build_backend()
                except Exception as e:
                    response.success = False
                    response.present = False
                    response.yes_no = ''
                    response.raw_answer = ''
                    response.message = f'backend init failed: {e}'
                    return response

            tmpl = self.get_parameter('prompt_template').get_parameter_value().string_value
            try:
                prompt = tmpl.format(object=name)
            except KeyError as e:
                response.success = False
                response.present = False
                response.yes_no = ''
                response.raw_answer = ''
                response.message = f'prompt_template must include {{object}} placeholder: {e}'
                return response

            timeout = self.get_parameter('inference_timeout').get_parameter_value().integer_value
            self.get_logger().info(f'CheckObject object={name!r} prompt={prompt!r}')

            out = describe_image_bgr(self._backend, frame, prompt, timeout)
            raw = out.get('answer', '') or ''
            parsed, reason = parse_yes_no(raw)

            if parsed is None:
                response.success = False
                response.present = False
                response.yes_no = ''
                response.raw_answer = raw
                response.message = f'could not parse yes/no ({reason})'
                return response

            response.success = True
            response.present = parsed
            response.yes_no = 'yes' if parsed else 'no'
            response.raw_answer = raw
            response.message = reason
            return response

        except Exception as e:
            self.get_logger().error(f'CheckObject failed: {e}')
            response.success = False
            response.present = False
            response.yes_no = ''
            response.raw_answer = ''
            response.message = str(e)
            return response
        finally:
            self._busy.release()

    def destroy_node(self) -> None:
        if self._backend is not None:
            try:
                self._backend.close()
            except Exception:
                pass
        super().destroy_node()


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
