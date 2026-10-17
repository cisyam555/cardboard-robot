from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("port", default_value="/dev/ttyACM0"),
        DeclareLaunchArgument("simulate", default_value="false"),
        Node(package="cardboard_robot", executable="hardware_bridge", output="screen",
             parameters=[{"port": LaunchConfiguration("port"),
                          "simulate": ParameterValue(LaunchConfiguration("simulate"), value_type=bool)}]),
        Node(package="cardboard_robot", executable="behavior_controller", output="screen"),
    ])
