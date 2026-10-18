"""统一启动两个 ROS2 节点；参数由模拟/实物入口复用。"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # Launch 参数来自命令行，例如 return_delay_ms:=800。
    # 它们先是文本；ParameterValue 明确转换成节点需要的 bool / int。
    definitions = (
        ("simulate", "false", "使用协议模拟数据；false 时打开真实串口"),
        ("port", "/dev/ttyACM0", "ESP32 串口；实物建议使用 /dev/serial/by-id/ 路径"),
        ("baud", "115200", "串口波特率"),
        ("sim_left", "false", "模拟左红外输入，可运行时用 ros2 param set 修改"),
        ("sim_right", "false", "模拟右红外输入"),
        ("sim_touch", "false", "模拟触摸输入"),
        ("return_delay_ms", "400", "物体离开后保持方向的毫秒数"),
        ("sensor_timeout_ms", "500", "决策节点允许的传感器消息最大间隔（毫秒）"),
    )
    arguments = [DeclareLaunchArgument(name, default_value=default, description=description)
                 for name, default, description in definitions]
    arguments.append(DeclareLaunchArgument(
        "log_level", default_value="info", choices=["debug", "info", "warn", "error", "fatal"],
        description="两个节点的日志级别"))

    def parameter(name, value_type):
        return ParameterValue(LaunchConfiguration(name), value_type=value_type)

    # 桥接节点：传感器 -> ROS2 话题；ROS2 动作 -> USB/模拟器。
    bridge = Node(
        package="cardboard_robot", executable="hardware_bridge", name="hardware_bridge",
        output="screen", emulate_tty=True,
        parameters=[{
            "simulate": parameter("simulate", bool),
            "port": LaunchConfiguration("port"),
            "baud": parameter("baud", int),
            "sim_left": parameter("sim_left", bool),
            "sim_right": parameter("sim_right", bool),
            "sim_touch": parameter("sim_touch", bool),
        }],
        arguments=["--ros-args", "--log-level", LaunchConfiguration("log_level")],
    )
    # 决策节点只订阅消息并发布动作，不直接打开 GPIO 或串口。
    controller = Node(
        package="cardboard_robot", executable="behavior_controller", name="behavior_controller",
        output="screen", emulate_tty=True,
        parameters=[{
            "return_delay_ms": parameter("return_delay_ms", int),
            "sensor_timeout_ms": parameter("sensor_timeout_ms", int),
        }],
        arguments=["--ros-args", "--log-level", LaunchConfiguration("log_level")],
    )
    return LaunchDescription(arguments + [
        LogInfo(msg=["Cardboard Robot: simulate=", LaunchConfiguration("simulate"),
                     "; request ROS2 control with /robot/set_ros2 after messages arrive."]),
        bridge,
        controller,
    ])
