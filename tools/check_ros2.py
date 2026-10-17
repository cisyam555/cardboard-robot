"""DDS integration check after building and sourcing the ROS2 workspace.

Uses two real ROS2 nodes and the protocol simulator; no physical hardware.
Run: python3 tools/check_ros2.py
"""
import os
import signal
import subprocess
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rcl_interfaces.srv import SetParameters
from std_msgs.msg import String
from std_srvs.srv import SetBool


def main():
    use_serial = "--serial" in sys.argv
    board = None
    if use_serial:
        from serial_fixture import SerialBoard
        board = SerialBoard()
    rclpy.init(args=[])
    bridge_args = (["--ros-args", "-p", "port:=" + board.path] if board else
                   ["--ros-args", "-p", "simulate:=true"])
    processes = [subprocess.Popen(
        ['ros2', 'run', 'cardboard_robot', executable, *extra],
        start_new_session=True)
        for executable, extra in (
            ('hardware_bridge', bridge_args),
            ('behavior_controller', []))]
    node = Node('cardboard_integration_check')
    seen = {'action': None, 'mode': None}
    subscriptions = []
    for key in seen:
        subscriptions.append(node.create_subscription(
            String, '/robot/'+key,
            lambda msg, key=key: seen.__setitem__(key, msg.data), 1))

    def until(predicate, timeout=10):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            if predicate():
                return
        raise AssertionError('ROS2 integration timed out: '+str(seen))

    def call(client, request):
        assert client.wait_for_service(timeout_sec=10), 'Service missing'
        future = client.call_async(request)
        until(future.done)
        return future.result()

    try:
        switch = node.create_client(SetBool, '/robot/set_ros2')
        params = node.create_client(SetParameters, '/hardware_bridge/set_parameters')
        until(lambda: seen['action'] == 'idle' and seen['mode'] == 'standalone')
        assert call(switch, SetBool.Request(data=True)).success
        until(lambda: seen['mode'] == 'ros2')
        for parameter, expected in (('sim_left', 'look_left'), ('sim_touch', 'bow')):
            if board:
                board.inputs[parameter.removeprefix("sim_")] = True
            else:
                request = SetParameters.Request(parameters=[
                    Parameter(parameter, value=True).to_parameter_msg()])
                assert all(r.successful for r in call(params, request).results)
            until(lambda: seen['action'] == expected)
            if board:
                until(lambda: board.control.action == expected and board.control.mode == 'ros2')
        assert call(switch, SetBool.Request(data=False)).success
        until(lambda: seen['mode'] == 'standalone')
        assert call(switch, SetBool.Request(data=True)).success
        until(lambda: seen['mode'] == 'ros2')
        # Stop the controller, not the bridge: stale actions must leave ROS2 mode.
        os.killpg(processes[1].pid, signal.SIGINT)
        until(lambda: seen['mode'] == 'standalone')
        assert not call(switch, SetBool.Request(data=True)).success
        print(('PTY serial + firmware' if board else 'Simulator') +
              ' ROS2 DDS integration OK: mode service, left, touch priority, stale-action fallback')
    finally:
        node.destroy_node()
        rclpy.shutdown()
        for process in processes:
            try:
                os.killpg(process.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        if board:
            board.close()


if __name__ == '__main__':
    main()
