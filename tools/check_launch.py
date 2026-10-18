"""ROS2 实际启动检查：验证 launch 参数、消息、服务与动态参数。

先构建并 source 工作空间，在没有其他机器人节点的通信域运行：
    ROS_DOMAIN_ID=84 python3 tools/check_launch.py
只启动 sim.launch.py；hardware.launch.py 仅解析 --show-args，不打开串口。
"""
import os
import signal
import subprocess
import time

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rcl_interfaces.srv import GetParameters, SetParameters
from std_msgs.msg import String
from std_srvs.srv import SetBool


def main():
    # 验证两个入口可被安装后的 ROS2 找到；--show-args 不启动硬件。
    for entry in ("sim.launch.py", "hardware.launch.py"):
        subprocess.run(["ros2", "launch", "cardboard_robot", entry, "--show-args"],
                       check=True, capture_output=True, text=True, timeout=15)
    rclpy.init(args=[])
    node = Node("cardboard_launch_check")
    seen = {"mode": None, "action": None}
    subscriptions = [node.create_subscription(
        String, "/robot/" + key,
        lambda msg, key=key: seen.__setitem__(key, msg.data), 1) for key in seen]
    process = None

    def until(predicate, timeout=12):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            if predicate():
                return
            if process is not None and process.poll() is not None:
                raise AssertionError("launch 提前退出")
        raise AssertionError("等待 ROS2 消息超时：" + repr(seen))

    def call(client, request):
        assert client.wait_for_service(timeout_sec=10), client.srv_name
        future = client.call_async(request)
        until(future.done)
        return future.result()

    def get_parameters(target, names):
        return call(node.create_client(GetParameters, target + "/get_parameters"),
                    GetParameters.Request(names=names)).values

    def set_parameter(target, name, value):
        response = call(node.create_client(SetParameters, target + "/set_parameters"),
                        SetParameters.Request(parameters=[
                            Parameter(name, value=value).to_parameter_msg()]))
        assert all(item.successful for item in response.results)

    try:
        process = subprocess.Popen([
            "ros2", "launch", "cardboard_robot", "sim.launch.py",
            "sim_left:=true", "return_delay_ms:=800", "sensor_timeout_ms:=750",
        ], start_new_session=True)
        until(lambda: seen == {"mode": "standalone", "action": "look_left"})
        bridge_values = get_parameters("/hardware_bridge", ["simulate", "sim_left", "baud"])
        assert bridge_values[0].bool_value is True
        assert bridge_values[1].bool_value is True
        assert bridge_values[2].integer_value == 115200
        control_values = get_parameters("/behavior_controller", ["return_delay_ms", "sensor_timeout_ms"])
        assert [value.integer_value for value in control_values] == [800, 750]

        switch = node.create_client(SetBool, "/robot/set_ros2")
        assert call(switch, SetBool.Request(data=True)).success
        until(lambda: seen["mode"] == "ros2")
        set_parameter("/hardware_bridge", "sim_right", True)
        until(lambda: seen["action"] == "look_center")
        set_parameter("/hardware_bridge", "sim_left", False)
        until(lambda: seen["action"] == "look_right")
        set_parameter("/hardware_bridge", "sim_touch", True)
        until(lambda: seen["action"] == "bow")
        set_parameter("/hardware_bridge", "sim_touch", False)
        set_parameter("/hardware_bridge", "sim_right", False)
        until(lambda: seen["action"] == "idle")
        # 决策参数运行时改变，无需重新 launch。
        set_parameter("/behavior_controller", "return_delay_ms", 1000)
        assert get_parameters("/behavior_controller", ["return_delay_ms"])[0].integer_value == 1000
        assert call(switch, SetBool.Request(data=False)).success
        until(lambda: seen["mode"] == "standalone")
        print("Launch integration OK: installed entrypoints, typed arguments, topics, "
              "mode service, input priority, runtime parameters and standalone return")
    finally:
        if process is not None and process.poll() is None:
            try:
                # launch 和它启动的子进程都属于该独立进程组。
                os.killpg(process.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=6)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=3)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
