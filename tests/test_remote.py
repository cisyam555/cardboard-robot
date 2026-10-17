"""Mode transitions, malformed traffic, watchdog, and host/firmware parity."""
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "firmware"))
import remote

spec = importlib.util.spec_from_file_location(
    "ros_core", ROOT / "ros2_ws/src/cardboard_robot/cardboard_robot/core.py")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
clock = types.SimpleNamespace(ticks_diff=lambda a, b: (a-b+32768) % 65536-32768)


class RemoteTests(unittest.TestCase):
    def test_handover_waits_for_center_and_exit_returns_local(self):
        control = remote.ModeController()
        self.assertEqual(control.mode, "standalone")
        control.receive(core.command("ros2", "bow").decode(), 0)
        with patch.object(remote, "time", clock):
            self.assertEqual(control.update(10, False), "centering")
            # Heartbeats do not restart the transition.
            control.receive(core.command("ros2", "look_left").decode(), 20)
            self.assertEqual(control.update(30, True), "ros2")
            self.assertEqual(control.action, "look_left")
            control.receive(core.command("standalone").decode(), 40)
            self.assertEqual(control.update(50, False), "centering")
            self.assertEqual(control.update(60, True), "standalone")

    def test_timeout_during_transition_and_after_wrap(self):
        for centered in (False, True):
            control = remote.ModeController()
            control.receive(core.command("ros2", "bow").decode(), 65000)
            with patch.object(remote, "time", clock):
                control.update(65010, centered)
                self.assertEqual(control.update(463, False),
                                 "ros2" if centered else "centering")
                self.assertEqual(control.update(464, False), "centering")
                self.assertEqual(control.requested, "standalone")
                self.assertEqual(control.update(465, True), "standalone")

    def test_invalid_commands_do_not_renew_watchdog(self):
        control = remote.ModeController()
        for line in ('null', '[]', '{}', 'bad', '{"v":1,"mode":"other"}',
                     '{"v":1,"mode":"ros2","action":"run"}',
                     '{"v":1,"mode":"ros2","action":[]}'):
            self.assertFalse(control.receive(line, 100))
            self.assertIsNone(control.last_command)

    def test_fragmented_and_oversized_lines_recover(self):
        buffer = remote.LineBuffer()
        self.assertEqual(buffer.feed('hel'), [])
        self.assertEqual(buffer.feed('lo\nbye\n'), ['hello', 'bye'])
        self.assertEqual(buffer.feed('x'*10000), [])
        self.assertEqual(buffer.text, '')
        self.assertEqual(buffer.feed('\n{}\n'), ['{}'])

    def test_telemetry_requires_complete_typed_snapshot(self):
        good = {"v": 1, "touch": False, "left": True, "right": False,
                "mode": "standalone"}
        self.assertEqual(core.parse_telemetry('@'+json.dumps(good)), good)
        for text in ('boot log', '@null', '@[]', '@{}', '@bad'):
            self.assertIsNone(core.parse_telemetry(text))
        good['left'] = 1
        self.assertIsNone(core.parse_telemetry('@'+json.dumps(good)))

    def test_all_behavior_rules_match_firmware(self):
        import behavior
        import config
        expected = {
            ('normal', config.CENTER_NS, config.CENTER_NS): 'idle',
            ('touched', config.CENTER_NS, config.TILT_DOWN_NS): 'bow',
            ('near', config.PAN_LEFT_NS, config.CENTER_NS): 'look_left',
            ('near', config.PAN_RIGHT_NS, config.CENTER_NS): 'look_right',
            ('near', config.CENTER_NS, config.CENTER_NS): 'look_center',
        }
        for touch, left, right in itertools.product((False, True), repeat=3):
            action = core.Policy().choose(touch, left, right, 0, 0.4)
            self.assertEqual(action, expected[behavior.choose_action(touch, left, right)])

    def test_policy_remembers_direction_even_during_touch(self):
        policy = core.Policy()
        self.assertEqual(policy.choose(True, True, False, 0, 0.4), 'bow')
        self.assertEqual(policy.choose(False, False, False, 0.39, 0.4), 'look_left')
        self.assertEqual(policy.choose(False, False, False, 0.4, 0.4), 'idle')

    def test_usb_io_failure_does_not_stop_local_control(self):
        from unittest.mock import Mock
        link = remote.USBLink.__new__(remote.USBLink)
        link.sys = types.SimpleNamespace(stdout=Mock())
        link.sys.stdout.write.side_effect = OSError("USB disconnected")
        self.assertFalse(link.send({"v": 1}))
        link.poll = Mock()
        link.poll.poll.side_effect = OSError("USB disconnected")
        self.assertEqual(link.read_lines(), [])
