#!/usr/bin/env python3
"""
Pi 5 Bringup Launch File
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():

    vlm_vision_node = Node(
        package='vision_models',
        executable='vlm_vision_node',
        name='vlm_vision_node',
        parameters=[{
            'zmq_host': 'localhost',
            'zmq_port': 5555,
            'zmq_timeout_ms': 8000,
        }],
        output='screen',
    )

    return LaunchDescription([
        vlm_vision_node,
    ])