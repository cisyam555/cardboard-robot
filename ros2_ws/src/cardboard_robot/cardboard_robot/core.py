"""Hardware independent protocol validation and reactive behavior."""
import json

ACTIONS = ("idle", "look_left", "look_right", "look_center", "bow")
MODES = ("standalone", "centering", "ros2")


def parse_telemetry(line):
    try:
        if not line.startswith("@"):
            return None
        data = json.loads(line[1:])
        if not isinstance(data, dict) or data.get("v") != 1:
            return None
        if data.get("mode") not in MODES:
            return None
        if not all(type(data.get(key)) is bool for key in ("touch", "left", "right")):
            return None
        return data
    except (ValueError, TypeError):
        return None


def command(mode, action="idle"):
    if mode not in ("standalone", "ros2") or action not in ACTIONS:
        raise ValueError("Invalid robot command")
    return (json.dumps({"v": 1, "mode": mode, "action": action}) + "\n").encode("ascii")


class Policy:
    def __init__(self):
        self.last_seen = None
        self.last_action = "idle"

    def choose(self, touch, left, right, now, delay):
        if left or right:
            self.last_seen = now
            self.last_action = ("look_center" if left and right else
                                "look_left" if left else "look_right")
        if touch:
            return "bow"
        if left or right:
            return self.last_action
        if self.last_seen is not None and now - self.last_seen < delay:
            return self.last_action
        return "idle"


class SimulationPort:
    """Protocol-only simulation: no mechanics, PWM or electrical validation."""
    def __init__(self):
        self.mode = "standalone"
        self.action = "idle"

    def write(self, payload):
        data = json.loads(payload)
        self.mode = data["mode"]
        self.action = data["action"]
        return len(payload)

    def close(self):
        pass
