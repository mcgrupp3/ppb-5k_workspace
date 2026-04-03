#!/usr/bin/env python3
"""Start vlm_vision node; robot calls ``vlm/check_object`` (CheckObject) with ``object_name``."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'image_topic',
            default_value='/camera/image_raw',
            description='sensor_msgs/Image topic (buffered until check_object is called)',
        ),
        Node(
            package='vlm_vision',
            executable='vlm_vision_node',
            name='vlm_vision',
            parameters=[{
                'image_topic': LaunchConfiguration('image_topic'),
                'inference_timeout': 60,
            }],
            output='screen',
        ),
    ])
