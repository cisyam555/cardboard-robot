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
        self.pin_number = pin.number
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
                        ("touched", config.PAN_HOME_NS, config.TILT_DOWN_NS) if touch else
                        ("near", config.PAN_LEFT_NS, config.TILT_NEAR_NS) if left and not right else
                        ("near", config.PAN_RIGHT_NS, config.TILT_NEAR_NS) if right and not left else
                        ("near", config.PAN_HOME_NS, config.TILT_NEAR_NS) if left and right else
                        ("normal", config.PAN_HOME_NS, config.TILT_HOME_NS)
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

    def test_raw_touch_level_is_not_hidden_by_debounce(self):
        with patch.object(sensors, "time", clock):
            sensor = sensors.StableInput(10, 1)
            sensor.pin.level = 1
            self.assertFalse(sensor.read(10))
            self.assertEqual(sensor.raw_level, 1)
            self.assertTrue(sensor.read(70))
            sensor.pin.level = 0
            self.assertTrue(sensor.read(71))
            self.assertEqual(sensor.raw_level, 0)

    def test_touch_feedback_lasts_after_release_and_handles_tick_wrap(self):
        with patch.object(behavior, "time", clock):
            feedback = behavior.TouchLatch(200)
            self.assertFalse(feedback.update(False, 900))
            self.assertTrue(feedback.update(True, 1000))
            self.assertTrue(feedback.update(False, 175))
            self.assertFalse(feedback.update(False, 176))
            self.assertTrue(feedback.update(True, 200))
            self.assertTrue(feedback.update(True, 350))
            self.assertTrue(feedback.update(False, 549))
            self.assertFalse(feedback.update(False, 550))

    def test_short_touch_completes_bow_even_with_ir_triggered(self):
        from unittest.mock import Mock
        import remote
        state = {"now": 0}
        def sleep_ms(duration):
            state["now"] += duration
            if state["now"] >= 2800:
                raise KeyboardInterrupt
        timer = types.SimpleNamespace(
            ticks_ms=lambda: state["now"],
            ticks_add=lambda a, b: a + b,
            ticks_diff=lambda a, b: a - b,
            sleep_ms=sleep_ms,
        )
        samples = []
        with patch.object(app, "time", timer), patch.object(servo, "time", timer), \
                patch.object(sensors, "time", timer), patch.object(behavior, "time", timer), \
                patch.object(remote, "time", timer), patch.object(app, "draw_face") as draw:
            pan = servo.SmoothServo(5, 1200000, 1800000)
            tilt = servo.SmoothServo(6, config.TILT_MIN_NS, config.TILT_MAX_NS)
            touch = sensors.StableInput(10, 1)
            touch.pin.value = lambda: int(100 <= state["now"] < 200)
            left = sensors.StableInput(4, 0)
            left.pin.value = lambda: 0
            right = sensors.StableInput(3, 0)
            right.pin.value = lambda: 1
            link = Mock()
            link.read_lines.return_value = []
            link.send.side_effect = lambda data: samples.append((state["now"], dict(data)))
            try:
                with self.assertRaises(KeyboardInterrupt):
                    app._interaction_loop(pan, tilt, object(), touch, left, right,
                                          remote.ModeController(), link, 0)
                self.assertTrue(any(300 <= t <= 1000 and d["touch"] and
                                    d["touch_raw"] == 0 for t, d in samples))
                self.assertTrue(any(d["tilt_ns"] == config.TILT_DOWN_NS for _, d in samples))
                self.assertTrue(any(t >= 1400 and not d["touch"] for t, d in samples))
                self.assertEqual(samples[-1][1]["tilt_ns"], config.TILT_NEAR_NS)
                self.assertTrue(any(call.args[1] == "touched" for call in draw.call_args_list))
            finally:
                tilt.close()
                pan.close()

    def test_ir_lifts_while_turning_and_returns_home_after_delay(self):
        from unittest.mock import Mock
        import remote
        state = {"now": 0}

        def sleep_ms(duration):
            state["now"] += duration
            if state["now"] >= 3000:
                raise KeyboardInterrupt

        timer = types.SimpleNamespace(
            ticks_ms=lambda: state["now"], ticks_add=lambda a, b: a + b,
            ticks_diff=lambda a, b: a - b, sleep_ms=sleep_ms)
        samples = []
        with patch.object(app, "time", timer), patch.object(servo, "time", timer), \
                patch.object(sensors, "time", timer), patch.object(behavior, "time", timer), \
                patch.object(remote, "time", timer), patch.object(app, "draw_face") as draw:
            pan = servo.SmoothServo(5, 1200000, 1800000, initial=config.PAN_HOME_NS)
            tilt = servo.SmoothServo(6, config.TILT_MIN_NS, config.TILT_MAX_NS,
                                     initial=config.TILT_HOME_NS)
            touch = sensors.StableInput(10, 1)
            left = sensors.StableInput(4, 0)
            right = sensors.StableInput(3, 0)
            left.pin.value = lambda: int(not 100 <= state["now"] < 400)
            right.pin.value = lambda: int(not 1400 <= state["now"] < 1700)
            link = Mock()
            link.read_lines.return_value = []
            link.send.side_effect = lambda data: samples.append((state["now"], dict(data)))
            try:
                with self.assertRaises(KeyboardInterrupt):
                    app._interaction_loop(pan, tilt, object(), touch, left, right,
                                          remote.ModeController(), link, 0)
                readings = dict(samples)
                self.assertEqual(readings[600]["tilt_ns"], config.TILT_NEAR_NS)
                self.assertLess(readings[600]["pan_ns"], config.PAN_HOME_NS)
                self.assertEqual(readings[1300]["tilt_ns"], config.TILT_HOME_NS)
                self.assertEqual(readings[1900]["tilt_ns"], config.TILT_NEAR_NS)
                self.assertGreater(readings[1900]["pan_ns"], config.PAN_HOME_NS)
                self.assertEqual(readings[2800]["tilt_ns"], config.TILT_HOME_NS)
                self.assertEqual(readings[2900]["pan_ns"], config.PAN_HOME_NS)
                self.assertTrue(all(config.TILT_MIN_NS <= p <= config.TILT_MAX_NS
                                    for p in tilt.pwm.pulses))
                self.assertTrue(all(len(call.args) == 2 for call in draw.call_args_list))
            finally:
                tilt.close()
                pan.close()

    def test_invalid_near_lift_does_not_start_pwm(self):
        with patch.object(app, "TILT_NEAR_EXTRA_NS", 20001), \
                patch.object(app, "SmoothServo") as motor:
            with self.assertRaises(ValueError):
                app.main()
            motor.assert_not_called()

    def test_expanded_pan_range_is_reachable_without_overshoot(self):
        with patch.object(servo, "time", clock):
            motor = servo.SmoothServo(5, 1200000, 1800000)
            motor.set_target(1800000)
            for n in range(120):
                motor.update((20 * n) % PERIOD)
            self.assertEqual(motor.current, 1800000)
            motor.set_target(1200000)
            for n in range(120, 330):
                motor.update((20 * n) % PERIOD)
            self.assertEqual(motor.current, 1200000)
            self.assertTrue(all(1200000 <= p <= 1800000 for p in motor.pwm.pulses))
            motor.close()

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

    def test_main_cleans_up_first_servo_when_second_servo_fails(self):
        motor = types.SimpleNamespace(close=lambda: None)
        from unittest.mock import Mock
        motor.close = Mock()
        with patch.object(app, "time", clock), \
                patch.object(app, "SmoothServo", side_effect=[motor, OSError("tilt failed")]):
            with self.assertRaises(OSError):
                app.main()
            motor.close.assert_called_once()

    def test_boot_raises_head_then_uses_separate_pan_home(self):
        before = len(FakePWM.instances)
        with patch.object(servo, "time", clock), patch.object(app, "time", clock), \
                patch.object(app, "MODE", "standalone"), \
                patch.object(app, "run_interaction", side_effect=KeyboardInterrupt):
            app.main()
        motors = FakePWM.instances[before:]
        self.assertEqual([m.pin_number for m in motors], [config.TILT_PIN, config.PAN_PIN])
        self.assertEqual([m.pulses for m in motors], [[config.TILT_HOME_NS], [config.PAN_HOME_NS]])
        self.assertTrue(all(m.closed for m in motors))

    def test_invalid_home_does_not_start_pwm(self):
        with patch.object(app, "PAN_HOME_NS", 1900000), patch.object(app, "SmoothServo") as motor:
            with self.assertRaises(ValueError):
                app.main()
            motor.assert_not_called()

    def test_servo_rejects_initial_position_outside_limits(self):
        before = len(FakePWM.instances)
        with self.assertRaises(ValueError):
            servo.SmoothServo(6, 1400000, 1600000, initial=1700000)
        self.assertEqual(len(FakePWM.instances), before)

    def test_invalid_mode_does_not_start_motors(self):
        with patch.object(app, "MODE", "invalid"), patch.object(app, "SmoothServo") as motor:
            with self.assertRaises(ValueError):
                app.main()
            motor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
