"""Host tests for decisions, timing, PWM limits and exception cleanup."""
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "firmware"))


class FakePin:
    OUT, IN, PULL_UP = 1, 2, 3

    def __init__(self, number, *args, value=0):
        self.number = number
        self.level = value

    def value(self):
        return self.level

    def init(self, *args, value=0):
        self.level = value


class FakePWM:
    fail = False
    instances = []

    def __init__(self, pin, **kwargs):
        self.closed = False
        self.pulses = []
        self.instances.append(self)

    def duty_ns(self, value):
        if self.fail:
            raise OSError("injected PWM failure")
        self.pulses.append(value)

    def deinit(self):
        self.closed = True


machine = types.ModuleType("machine")
machine.Pin, machine.PWM = FakePin, FakePWM
# Real MicroPython has a much longer tick period; a short one exercises wraparound.
PERIOD = 1024
clock = types.SimpleNamespace(
    ticks_ms=lambda: 0,
    ticks_add=lambda value, delta: (value + delta) % PERIOD,
    ticks_diff=lambda a, b: (a - b + PERIOD // 2) % PERIOD - PERIOD // 2,
    sleep_ms=lambda value: None,
)
with patch.dict(sys.modules, {"machine": machine}):
    config = importlib.import_module("config")
    behavior = importlib.import_module("behavior")
    sensors = importlib.import_module("sensors")
    servo = importlib.import_module("servo")
    app = importlib.import_module("app")


class ControlTests(unittest.TestCase):
    def test_all_input_combinations(self):
        for touch in (False, True):
            for left in (False, True):
                for right in (False, True):
                    expected = (
                        ("touched", config.CENTER_NS, config.TILT_DOWN_NS) if touch else
                        ("near", config.PAN_LEFT_NS, config.CENTER_NS) if left and not right else
                        ("near", config.PAN_RIGHT_NS, config.CENTER_NS) if right and not left else
                        ("near", config.CENTER_NS, config.CENTER_NS) if left and right else
                        ("normal", config.CENTER_NS, config.CENTER_NS)
                    )
                    with self.subTest(touch=touch, left=left, right=right):
                        self.assertEqual(behavior.choose_action(touch, left, right), expected)

    def test_debounce_rejects_short_pulse_and_accepts_stable_signal(self):
        with patch.object(sensors, "time", clock):
            sensor = sensors.StableInput(10, 1)
            sensor.pin.level = 1
            self.assertFalse(sensor.read(10))
            sensor.pin.level = 0
            self.assertFalse(sensor.read(30))
            sensor.pin.level = 1
            self.assertFalse(sensor.read(40))
            self.assertFalse(sensor.read(99))
            self.assertTrue(sensor.read(100))
            sensor.pin.level = 0
            self.assertTrue(sensor.read(110))
            self.assertFalse(sensor.read(170))

    def test_debounce_active_low_and_tick_wrap(self):
        with patch.object(sensors, "time", clock):
            sensor = sensors.StableInput(4, 0, pull_up=True)
            sensor.pin.level = 1
            sensor.read(900)
            sensor.pin.level = 0
            self.assertFalse(sensor.read(1000))
            self.assertFalse(sensor.read(35))
            self.assertTrue(sensor.read(36))

    def test_servo_moves_at_intervals_clamps_and_does_not_overshoot(self):
        with patch.object(servo, "time", clock):
            motor = servo.SmoothServo(5, 1400000, 1600000)
            motor.set_target(9999999)
            self.assertEqual(motor.target, 1600000)
            motor.update(0)
            self.assertEqual(motor.current, 1501000)
            motor.update(19)
            self.assertEqual(motor.current, 1501000)
            for now in range(20, 801, 20):
                motor.update(now)
            self.assertEqual(motor.current, 1600000)
            motor.set_target(1599000)
            motor.update(820)
            self.assertEqual(motor.current, 1599000)
            motor.set_target(-1)
            self.assertEqual(motor.target, 1400000)
            motor.close()
            self.assertTrue(motor.pwm.closed)
            self.assertEqual(motor.pin.level, 0)

    def test_servo_update_across_tick_wrap(self):
        with patch.object(servo, "time", clock):
            motor = servo.SmoothServo(5, 1400000, 1600000)
            motor.set_target(1600000)
            motor.next_step = 1010
            motor.update(1010)
            self.assertEqual(motor.current, 1501000)
            motor.update(5)
            self.assertEqual(motor.current, 1501000)
            motor.update(6)
            self.assertEqual(motor.current, 1503000)
            motor.close()

    def test_soft_start_slow_finish_and_reverse(self):
        with patch.object(servo, "time", clock):
            motor = servo.SmoothServo(5, 1400000, 1600000)
            motor.set_target(1600000)
            positions = [motor.current]
            for now in range(0, 801, 20):
                motor.update(now)
                positions.append(motor.current)
            steps = [b-a for a, b in zip(positions, positions[1:]) if b != a]
            self.assertEqual(steps[:4], [1000, 2000, 3000, 4000])
            self.assertTrue(all(0 < step <= config.STEP_NS for step in steps))
            self.assertLess(steps[-1], config.STEP_NS)
            self.assertEqual(motor.current, 1600000)
            motor.set_target(1400000)
            motor.update(820)
            self.assertEqual(motor.current, 1599000)
            motor.update(840)
            self.assertEqual(motor.current, 1597000)
            # Reverse a moving servo without carrying over the previous step size.
            motor.set_target(1600000)
            motor.update(860)
            self.assertEqual(motor.current, 1598000)
            motor.close()

    def test_constructor_failure_releases_pwm(self):
        with patch.object(servo, "time", clock), patch.object(FakePWM, "fail", True):
            with self.assertRaises(OSError):
                servo.SmoothServo(5, 1400000, 1600000)
            self.assertTrue(FakePWM.instances[-1].closed)

    def test_main_releases_both_servos_on_application_error(self):
        with patch.object(servo, "time", clock), patch.object(app, "time", clock), \
                patch.object(app, "MODE", "demo"), \
                patch.object(app, "run_demo", side_effect=OSError("injected app failure")):
            with self.assertRaises(OSError):
                app.main()
            self.assertTrue(all(m.closed for m in FakePWM.instances[-2:]))

    def test_main_cleans_up_pan_when_second_servo_fails(self):
        motor = types.SimpleNamespace(close=lambda: None)
        from unittest.mock import Mock
        motor.close = Mock()
        with patch.object(app, "time", clock), \
                patch.object(app, "SmoothServo", side_effect=[motor, OSError("tilt failed")]):
            with self.assertRaises(OSError):
                app.main()
            motor.close.assert_called_once()

    def test_invalid_mode_does_not_start_motors(self):
        with patch.object(app, "MODE", "invalid"), patch.object(app, "SmoothServo") as motor:
            with self.assertRaises(ValueError):
                app.main()
            motor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
