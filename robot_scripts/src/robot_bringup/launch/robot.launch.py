#!/usr/bin/env python3
"""
Robot Bringup Launch File
Starts all nodes for manual teleoperation with LiDAR and Foxglove visualization
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    # ── Launch arguments ──────────────────────────────────────────────────────
    input_mode_arg = DeclareLaunchArgument(
        'input_mode',
        default_value='xbox',
        description='Input mode: xbox or keyboard'
    )

    # ── Nodes ─────────────────────────────────────────────────────────────────

    joystick_node = Node(
        package='joystick_control',
        executable='joystick_node',
        name='joystick_node',
        parameters=[{
            'input_mode': LaunchConfiguration('input_mode'),
            'publish_rate': 100.0,
        }],
        output='screen',
    )

    movement_node = Node(
        package='movement',
        executable='manual_control',
        name='manual_control',
        parameters=[{
            'max_speed': 0.8,
            'deadzone':  0.1,
            'alpha':     0.4,
            'send_hz':   20.0,
        }],
        output='screen',
    )

    lidar_node = Node(
        package='ldlidar_stl_ros2',
        executable='ldlidar_stl_ros2_node',
        name='ldlidar_node',
        parameters=[{
            'product_name': 'LDLiDAR_LD19',
            'topic_name':   'scan',
            'port_name':    '/dev/ttyAMA4',
            'frame_id':     'base_laser',
            'serial_baudrate': 230400,
        }],
        output='screen',
    )

    # 180° yaw rotation — LiDAR cable faces rear
    lidar_transform = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='lidar_transform',
        arguments=['0', '0', '0', '3.14159', '0', '0', 'base_link', 'base_laser'],
        output='screen',
    )

    foxglove_node = Node(
        package='foxglove_bridge',
        executable='foxglove_bridge',
        name='foxglove_bridge',
        parameters=[{
            'port': 8765,
        }],
        output='screen',
    )

    return LaunchDescription([
        input_mode_arg,
        joystick_node,
        movement_node,
        lidar_node,
        lidar_transform,
        foxglove_node,
    ])