"""USB transport, sensor topics, explicit mode service, freshness watchdog."""
import json
import time
import signal
import serial
import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from std_msgs.msg import Bool, String
from std_srvs.srv import SetBool
from .core import ACTIONS, SimulationPort, command, parse_telemetry


class HardwareBridge(Node):
    def __init__(self):
        super().__init__("hardware_bridge")
        for name, value in (("port", "/dev/ttyACM0"), ("baud", 115200),
                            ("simulate", False), ("sim_touch", False),
                            ("sim_left", False), ("sim_right", False)):
            self.declare_parameter(name, value)
        self.simulate = self.get_parameter("simulate").value
        self.port = None
        self.enabled = False
        self.last_sensor = None
        self.last_action = None
        self.action = "idle"
        self.last_open = -10.0
        self.buffer = bytearray()
        self.dropping = False
        self.last_mode = None
        self.snapshot_pub = self.create_publisher(String, "/robot/sensors", 1)
        self.sensor_pubs = {key: self.create_publisher(Bool, topic, 1) for key, topic in (
            ("touch", "/robot/touch"), ("left", "/robot/ir/left"),
            ("right", "/robot/ir/right"))}
        self.mode_pub = self.create_publisher(String, "/robot/mode", 1)
        self.connected_pub = self.create_publisher(Bool, "/robot/connected", 1)
        self.create_subscription(String, "/robot/action", self.on_action, 1)
        self.create_service(SetBool, "/robot/set_ros2", self.set_mode)
        self.create_timer(0.1, self.tick)
        self.get_logger().info("Simulation enabled" if self.simulate else
                               "Waiting for ESP32; close Thonny before connecting")

    def on_action(self, msg):
        if msg.data in ACTIONS:
            self.action = msg.data
            self.last_action = time.monotonic()

    def fresh(self, now):
        return (self.last_sensor is not None and self.last_action is not None
                and now - self.last_sensor < 0.5 and now - self.last_action < 0.5)

    def set_mode(self, request, response):
        if request.data and (self.port is None or not self.fresh(time.monotonic())):
            response.success = False
            response.message = "Need fresh ESP32 telemetry and a running behavior controller"
            return response
        self.enabled = request.data
        response.success = True
        response.message = "ROS2 requested; check /robot/mode for acknowledgement" if self.enabled else "Standalone requested"
        return response

    def accept(self, line, now):
        data = parse_telemetry(line)
        if data is None:
            return
        self.last_sensor = now
        self.snapshot_pub.publish(String(data=json.dumps(data)))
        for key, publisher in self.sensor_pubs.items():
            publisher.publish(Bool(data=data[key]))
        self.mode_pub.publish(String(data=data["mode"]))
        if data["mode"] != self.last_mode:
            self.get_logger().info("Board mode: " + data["mode"])
            self.last_mode = data["mode"]

    def read_serial(self, now):
        for byte in self.port.read(min(self.port.in_waiting, 4096)):
            if byte == 10:
                if not self.dropping:
                    self.accept(self.buffer.decode("ascii", errors="replace").rstrip("\r"), now)
                self.buffer.clear()
                self.dropping = False
            elif not self.dropping:
                self.buffer.append(byte)
                if len(self.buffer) > 512:
                    self.buffer.clear()
                    self.dropping = True

    def tick(self):
        now = time.monotonic()
        try:
            if self.port is None and now - self.last_open >= 2:
                self.last_open = now
                if self.simulate:
                    self.port = SimulationPort()
                else:
                    # Set control lines before open to avoid an intentional reset.
                    port = serial.Serial(port=None, baudrate=self.get_parameter("baud").value,
                                         timeout=0, write_timeout=0.05, exclusive=True)
                    port.dtr = False
                    port.rts = False
                    port.port = self.get_parameter("port").value
                    port.open()
                    self.port = port
            if self.port is not None:
                if self.simulate:
                    self.accept("@" + json.dumps({"v": 1, "mode": self.port.mode,
                        **{key: self.get_parameter("sim_" + key).value
                           for key in ("touch", "left", "right")}}), now)
                else:
                    self.read_serial(now)
                if self.enabled and not self.fresh(now):
                    self.enabled = False
                    self.get_logger().warning("Stale sensors/actions; returning to standalone")
                payload = command("ros2" if self.enabled else "standalone",
                                  self.action if self.enabled else "idle")
                if self.port.write(payload) != len(payload):
                    raise serial.SerialTimeoutException("Partial serial write")
                if self.simulate and self.enabled:
                    if self.action != getattr(self, "logged_action", None):
                        self.get_logger().info("SIM action: " + self.action)
                        self.logged_action = self.action
        except (OSError, serial.SerialException) as error:
            self.get_logger().warning("Serial unavailable: " + str(error))
            self.enabled = False
            if self.port is not None:
                self.port.close()
            self.port = None
            self.last_sensor = None
            self.last_action = None
            self.buffer.clear()
            self.dropping = False
        connected = self.last_sensor is not None and now - self.last_sensor < 0.5
        self.connected_pub.publish(Bool(data=connected))
        if not connected:
            self.mode_pub.publish(String(data="disconnected"))

    def close(self):
        if self.port is not None:
            try:
                self.port.write(command("standalone"))
            except (OSError, serial.SerialException):
                pass  # Board watchdog handles abrupt disconnects.
            finally:
                self.port.close()


def main(args=None):
    rclpy.init(args=args)
    node = HardwareBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # launch may forward a second SIGINT while resources are closing.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
