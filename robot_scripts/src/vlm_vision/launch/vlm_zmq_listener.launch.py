#!/usr/bin/env python3
"""ZMQ bridge: REP on Pi 5 -> ``/vlm/check_object``. Start after ``vlm_vision`` and camera."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'zmq_bind',
            default_value='tcp://*:5559',
            description='Address for ZMQ REP bind (Pi 4 connects here)',
        ),
        DeclareLaunchArgument(
            'service',
            default_value='/vlm/check_object',
            description='CheckObject service name',
        ),
        Node(
            package='vlm_vision',
            executable='vlm_zmq_listener',
            name='vlm_zmq_listener',
            arguments=[
                '--bind', LaunchConfiguration('zmq_bind'),
                '--service', LaunchConfiguration('service'),
            ],
            output='screen',
        ),
    ])
