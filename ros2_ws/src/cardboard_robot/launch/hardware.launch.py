"""实物入口：经 USB 连接已运行 MicroPython 正式程序的 ESP32。"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    defaults = {
        "port": "/dev/ttyACM0", "baud": "115200",
        "return_delay_ms": "400", "sensor_timeout_ms": "500", "log_level": "info",
    }
    arguments = [DeclareLaunchArgument(name, default_value=value)
                 for name, value in defaults.items()]
    return LaunchDescription(arguments + [IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([
            FindPackageShare("cardboard_robot"), "launch", "robot.launch.py"])),
        launch_arguments={
            "simulate": "false",
            **{name: LaunchConfiguration(name) for name in defaults},
        }.items(),
    )])
