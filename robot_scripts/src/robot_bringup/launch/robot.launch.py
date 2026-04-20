#!/usr/bin/env python3
"""
Robot Bringup Launch File
Starts all nodes for manual teleoperation with LiDAR and Foxglove visualization
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():

    nav2_params = os.path.join(
        get_package_share_directory('robot_bringup'), 'config', 'nav2_params.yaml'
    )

    # ── Launch arguments ──────────────────────────────────────────────────────
    input_mode_arg = DeclareLaunchArgument(
        'input_mode',
        default_value='xbox',
        description='Input mode: xbox or keyboard'
    )

    mode_arg = DeclareLaunchArgument(
        'mode',
        default_value='manual',
        description='Operation mode: manual | autonomous'
    )

    is_manual = IfCondition(PythonExpression(
        ["'", LaunchConfiguration('mode'), "' == 'manual'"]
    ))
    is_auto = IfCondition(PythonExpression(
        ["'", LaunchConfiguration('mode'), "' == 'autonomous'"]
    ))

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
        executable='manual',
        name='manual',
        parameters=[{
            'max_speed': 0.8,
            'deadzone':  0.1,
            'alpha':     0.4,
            'send_hz':   20.0,
        }],
        output='screen',
        condition=is_manual,
    )

    autonomous_node = Node(
        package='movement',
        executable='autonomous',
        name='autonomous',
        parameters=[{'max_speed': 0.8}],
        output='screen',
        condition=is_auto,
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
        arguments=['--ros-args', '--log-level', 'warn'],
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

    # IMU publisher — MPU6050 → /imu/data_raw
    imu_node = Node(
        package='imu_handler',
        executable='mpu6050_publisher',
        name='mpu6050_publisher',
        output='screen',
    )

    # Static transform — where IMU sits relative to base_link
    imu_transform = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='imu_transform',
        arguments=['0', '0', '0', '0', '0', '0', 'base_link', 'imu_link'],
        output='screen',
    )

    # Madgwick filter — /imu/data_raw → /imu/data (adds orientation)
    imu_filter_node = Node(
        package='imu_filter_madgwick',
        executable='imu_filter_madgwick_node',
        name='imu_filter_madgwick',
        parameters=[{
            'use_mag':    False,
            'publish_tf': False,
            'gain':       0.1,
            'zeta':       0.0,
        }],
        remappings=[('/imu/data_in', '/imu/data_raw')],
        output='screen',
    )

    # Scan + IMU sync — /scan + /imu/data → /scan/synced + /imu/synced
    scan_imu_sync_node = Node(
        package='imu_handler',
        executable='scan_imu_sync',
        name='scan_imu_sync',
        output='screen',
    )

    # ICP odometry — /scan/synced + /imu/synced → /odom + TF odom→base_link
    icp_odom_node = Node(
        package='rtabmap_odom',
        executable='icp_odometry',
        name='icp_odometry',
        parameters=[{
            'frame_id':               'base_link',
            'odom_frame_id':          'odom',
            'publish_tf':             True,
            'queue_size':             10,
            'publish_null_when_lost': True,
            'wait_for_transform':     0.5,
            'Icp/MaxTranslation':     '0.3',   # was 0.5 — tighter limit catches resets earlier
            'Icp/MaxRotation':        '0.3',   # was 0.5
            'Icp/CorrespondenceRatio': '0.07', # was 0.1 — more tolerant of partial scans
            'Odom/ResetCountdown':    '1',
        }],
        remappings=[
            ('/imu',  '/imu/synced'),
            ('/scan', '/scan/synced'),
        ],
        arguments=['--ros-args', '--log-level', 'warn'],
        output='screen',
    )

    # RTAB-Map SLAM — /scan/synced + /imu/synced → /map + TF map→odom
    rtabmap_slam_node = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap_slam',
        parameters=[{
            'frame_id':              'base_link',
            'odom_frame_id':         'odom',
            'subscribe_depth':       False,
            'subscribe_rgb':         False,
            'subscribe_scan':        True,
            'subscribe_imu':         True,
            'wait_for_transform':    0.5,
            'approx_sync':           True,
            'Mem/IncrementalMemory': 'true',
            'Vis/MaxFeatures':       '0',
        }],
        remappings=[
            ('/imu',  '/imu/synced'),
            ('/scan', '/scan/synced'),
        ],
        arguments=['--delete_db_on_start', '--ros-args', '--log-level', 'warn'],
        output='screen',
    )

    # ── Nav2 stack ────────────────────────────────────────────────────────────

    lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        parameters=[{
            'use_sim_time': False,
            'autostart':    True,
            'node_names': [
                'planner_server',
                'controller_server',
                'bt_navigator',
                'behavior_server',
            ],
        }],
        output='screen',
    )

    planner_server = Node(
        package='nav2_planner',
        executable='planner_server',
        name='planner_server',
        parameters=[nav2_params],
        output='screen',
    )

    controller_server = Node(
        package='nav2_controller',
        executable='controller_server',
        name='controller_server',
        parameters=[nav2_params],
        output='screen',
    )

    bt_navigator = Node(
        package='nav2_bt_navigator',
        executable='bt_navigator',
        name='bt_navigator',
        parameters=[nav2_params],
        output='screen',
    )

    behavior_server = Node(
        package='nav2_behaviors',
        executable='behavior_server',
        name='behavior_server',
        parameters=[nav2_params],
        output='screen',
    )

    return LaunchDescription([
        input_mode_arg,
        mode_arg,
        joystick_node,
        movement_node,
        autonomous_node,
        lidar_node,
        lidar_transform,
        foxglove_node,
        imu_node,
        imu_transform,
        imu_filter_node,
        scan_imu_sync_node,
        icp_odom_node,
        rtabmap_slam_node,
        lifecycle_manager,
        planner_server,
        controller_server,
        bt_navigator,
        behavior_server,
    ])