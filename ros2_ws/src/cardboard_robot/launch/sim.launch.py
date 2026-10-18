"""学习入口：仅模拟传感器和协议，不打开真实串口。"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Include 复用统一启动文件，避免维护两份节点配置。
    defaults = {
        "sim_left": "false", "sim_right": "false", "sim_touch": "false",
        "return_delay_ms": "400", "sensor_timeout_ms": "500", "log_level": "info",
    }
    arguments = [DeclareLaunchArgument(name, default_value=value)
                 for name, value in defaults.items()]
    return LaunchDescription(arguments + [IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([
            FindPackageShare("cardboard_robot"), "launch", "robot.launch.py"])),
        launch_arguments={
            "simulate": "true",
            **{name: LaunchConfiguration(name) for name in defaults},
        }.items(),
    )])
