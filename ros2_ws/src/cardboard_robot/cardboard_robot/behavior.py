"""Subscribe to a complete sensor snapshot; publish actions at 20Hz."""
import time
import signal
import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from std_msgs.msg import String
from .core import Policy, parse_telemetry


class BehaviorController(Node):
    def __init__(self):
        super().__init__("behavior_controller")
        self.declare_parameter("return_delay_ms", 400)
        self.declare_parameter("sensor_timeout_ms", 500)
        self.policy = Policy()
        self.snapshot = None
        self.received = None
        self.publisher = self.create_publisher(String, "/robot/action", 1)
        self.create_subscription(String, "/robot/sensors", self.sensors, 1)
        self.create_timer(0.05, self.tick)

    def sensors(self, msg):
        data = parse_telemetry("@" + msg.data)
        if data is not None:
            self.snapshot = data
            self.received = time.monotonic()

    def tick(self):
        now = time.monotonic()
        timeout = max(0.1, self.get_parameter("sensor_timeout_ms").value / 1000)
        if self.received is None or now - self.received >= timeout:
            # Silence lets the bridge detect controller/input loss and leave ROS2.
            self.policy = Policy()
            return
        s = self.snapshot
        delay = max(0, self.get_parameter("return_delay_ms").value / 1000)
        action = self.policy.choose(s["touch"], s["left"], s["right"], now, delay)
        self.publisher.publish(String(data=action))


def main(args=None):
    rclpy.init(args=args)
    node = BehaviorController()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # launch may forward a second SIGINT while resources are closing.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
