"""USB JSON-line protocol and mode handover; no hardware imports."""
import json
import time

ACTIONS = ("idle", "look_left", "look_right", "look_center", "bow")


class LineBuffer:
    """Bound input memory and discard oversized records until newline."""
    def __init__(self):
        self.text = ""
        self.overflow = False

    def feed(self, text):
        lines = []
        for char in text:
            if char == "\n":
                if not self.overflow:
                    lines.append(self.text)
                self.text = ""
                self.overflow = False
            elif not self.overflow:
                self.text += char
                if len(self.text) > 256:
                    self.text = ""
                    self.overflow = True
        return lines


class ModeController:
    def __init__(self, timeout_ms=1000):
        self.mode = "standalone"
        self.requested = "standalone"
        self.action = "idle"
        self.last_command = None
        self.timeout_ms = timeout_ms

    def receive(self, line, now):
        try:
            data = json.loads(line)
            if not isinstance(data, dict) or data.get("v") != 1:
                return False
            mode = data.get("mode")
            action = data.get("action", "idle")
            if mode not in ("standalone", "ros2") or action not in ACTIONS:
                return False
        except (ValueError, TypeError):
            return False
        self.last_command = now
        if mode != self.requested:
            self.requested = mode
            self.mode = "centering"
        self.action = action
        return True

    def update(self, now, centered):
        if self.requested == "ros2" and (
            self.last_command is None or
            time.ticks_diff(now, self.last_command) >= self.timeout_ms
        ):
            self.requested = "standalone"
            self.mode = "centering"
            self.action = "idle"
        if self.mode == "centering" and centered:
            self.mode = self.requested
        return self.mode


class USBLink:
    """MicroPython USB REPL stream; Thonny must release the port first."""
    def __init__(self):
        import sys
        import select
        self.sys = sys
        self.poll = select.poll()
        self.poll.register(sys.stdin, select.POLLIN)
        self.buffer = LineBuffer()

    def read_lines(self):
        lines = []
        # Limit work per cycle so flooding cannot starve servo updates.
        for _ in range(128):
            try:
                if not self.poll.poll(0):
                    break
                char = self.sys.stdin.read(1)
            except OSError:
                # USB loss must not stop local sensing/motion; watchdog exits ROS2.
                break
            if not char:
                break
            lines.extend(self.buffer.feed(char))
        return lines

    def send(self, payload):
        try:
            self.sys.stdout.write("@" + json.dumps(payload) + "\n")
            return True
        except OSError:
            return False

    def close(self):
        self.poll.unregister(self.sys.stdin)
