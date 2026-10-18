"""演示和互动循环，以及退出时的硬件释放。"""
import time
from servo import SmoothServo
from sensors import StableInput
from behavior import choose_action, TouchLatch
from faces import draw_face

from config import (
    CENTER_NS,
    PAN_HOME_NS,
    TILT_HOME_NS,
    TILT_NEAR_EXTRA_NS,
    TILT_NEAR_NS,
    TILT_MIN_NS,
    TILT_MAX_NS,
    IR_ACTIVE_LEVEL,
    LEFT_IR_PIN,
    MODE,
    OLED_SDA_PIN,
    OLED_SCL_PIN,
    OLED_FREQ,
    OLED_ADDRESS,
    PAN_DIRECTION,
    PAN_LEFT_NS,
    PAN_PIN,
    PAN_RANGE_NS,
    PAN_RIGHT_NS,
    RETURN_DELAY_MS,
    RIGHT_IR_PIN,
    STEP_INTERVAL_MS,
    STEP_NS,
    RAMP_STEP_NS,
    TILT_DIRECTION,
    TILT_DOWN_NS,
    TILT_PIN,
    TILT_RANGE_NS,
    TOUCH_PIN,
    TOUCH_ACTIVE_LEVEL,
    TOUCH_HOLD_MS,
    REMOTE_TIMEOUT_MS,
    TELEMETRY_INTERVAL_MS,
)

def move_and_wait(pan, tilt, pan_target, tilt_target):
    pan.set_target(pan_target)
    tilt.set_target(tilt_target)
    while pan.current != pan.target or tilt.current != tilt.target:
        now = time.ticks_ms()
        pan.update(now)
        tilt.update(now)
        time.sleep_ms(5)
    # 演示时停一下，让你看清位置。互动模式里不用这个长等待。
    time.sleep_ms(700)



def run_demo(pan, tilt):
    print("开始小幅演示；方向名称需要按实际安装确认。")
    actions = (
        ("第一只：向左", PAN_LEFT_NS, TILT_HOME_NS),
        ("第一只：回默认位置", PAN_HOME_NS, TILT_HOME_NS),
        ("第一只：向右", PAN_RIGHT_NS, TILT_HOME_NS),
        ("第一只：回默认位置", PAN_HOME_NS, TILT_HOME_NS),
        ("第二只：低头", PAN_HOME_NS, TILT_DOWN_NS),
        ("第二只：抬回默认位置", PAN_HOME_NS, TILT_HOME_NS),
    )
    for message, pan_target, tilt_target in actions:
        print(message)
        move_and_wait(pan, tilt, pan_target, tilt_target)
    print("演示完成，现在保持抬头、略朝右的默认位置。按 Thonny 红色停止按钮结束。")
    print("如果已安装头壳，停止前先扶住；停止会释放舵机。")
    while True:
        time.sleep_ms(100)



def run_interaction(pan, tilt):
    # 延迟导入：自动演示只需要舵机，不需要接屏幕或上传屏幕驱动。
    from machine import Pin, I2C
    import ssd1306

    i2c = I2C(0, sda=Pin(OLED_SDA_PIN), scl=Pin(OLED_SCL_PIN), freq=OLED_FREQ)
    if OLED_ADDRESS not in i2c.scan():
        raise OSError("未找到地址 60 的屏幕，请断电检查屏幕接线和供电。")
    oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=OLED_ADDRESS)
    touch = StableInput(TOUCH_PIN, TOUCH_ACTIVE_LEVEL)
    left_ir = StableInput(LEFT_IR_PIN, IR_ACTIVE_LEVEL, pull_up=True)
    right_ir = StableInput(RIGHT_IR_PIN, IR_ACTIVE_LEVEL, pull_up=True)

    from remote import ModeController, USBLink
    controller = ModeController(REMOTE_TIMEOUT_MS)
    link = USBLink()
    last_report = time.ticks_ms()
    print("互动开始：左红外转左，右红外转右，摸头低头。")

    try:
        _interaction_loop(pan, tilt, oled, touch, left_ir, right_ir,
                          controller, link, last_report)
    finally:
        link.close()


def _interaction_loop(pan, tilt, oled, touch, left_ir, right_ir,
                      controller, link, last_report):
    last_seen_at = None
    last_near_target = PAN_HOME_NS
    last_blink = time.ticks_ms()
    blink_until = None
    shown = None
    previous_mode = "standalone"
    touch_feedback = TouchLatch(TOUCH_HOLD_MS)
    while True:
        now = time.ticks_ms()
        for line in link.read_lines():
            controller.receive(line, now)
        centered = (pan.current == PAN_HOME_NS and tilt.current == TILT_HOME_NS)
        mode = controller.update(now, centered)
        if mode != previous_mode:
            last_seen_at = None
            previous_mode = mode
        # 读取真实触摸，再延长反馈。松手后也能看到完整低头，而不是立刻抬回。
        touched = touch_feedback.update(touch.read(now), now)
        left = left_ir.read(now)
        right = right_ir.read(now)
        expression, pan_target, tilt_target = choose_action(touched, left, right)

        if left or right:
            # 即使正在摸头，也记录最近的红外方向；触摸仍然具有最高优先级。
            last_seen_at = now
            _, last_near_target, _ = choose_action(False, left, right)
        elif not touched and last_seen_at is not None:
            if time.ticks_diff(now, last_seen_at) < RETURN_DELAY_MS:
                expression = "near"
                pan_target = last_near_target
                tilt_target = TILT_NEAR_NS

        if mode == "centering":
            expression, pan_target, tilt_target = "normal", PAN_HOME_NS, TILT_HOME_NS
        elif mode == "ros2":
            action = controller.action
            expression = "touched" if action == "bow" else (
                "normal" if action == "idle" else "near")
            pan_target = (PAN_LEFT_NS if action == "look_left" else
                          PAN_RIGHT_NS if action == "look_right" else PAN_HOME_NS)
            tilt_target = (TILT_DOWN_NS if action == "bow" else
                           TILT_HOME_NS if action == "idle" else TILT_NEAR_NS)

        # 每次循环只向目标走一小步，不用 sleep(1) 等待整个动作做完。
        # 因此向左转到一半时，右边检测到手，也能及时修改目标。
        pan.set_target(pan_target)
        tilt.set_target(tilt_target)
        pan.update(now)
        tilt.update(now)

        if expression != "normal":
            last_blink = now
            blink_until = None
        elif blink_until is not None:
            if time.ticks_diff(now, blink_until) < 0:
                expression = "closed"
            else:
                blink_until = None
        elif time.ticks_diff(now, last_blink) >= 3000:
            expression = "closed"
            blink_until = time.ticks_add(now, 180)
            last_blink = now

        # I2C 刷屏也会占时间，只在表情改变时画，避免拖慢舵机更新。
        if expression != shown:
            draw_face(oled, expression)
            shown = expression

        if time.ticks_diff(now, last_report) >= TELEMETRY_INTERVAL_MS:
            link.send({"v": 1, "touch": touched, "left": left, "right": right,
                       "mode": mode, "touch_raw": touch.raw_level,
                       "left_raw": left_ir.raw_level, "right_raw": right_ir.raw_level,
                       "pan_ns": pan.current, "tilt_ns": tilt.current})
            last_report = now
        time.sleep_ms(5)



def main():
    if MODE not in ("demo", "interaction", "standalone"):
        raise ValueError('MODE 只能填 "demo"、"interaction" 或 "standalone"')
    if PAN_DIRECTION not in (-1, 1) or TILT_DIRECTION not in (-1, 1):
        raise ValueError("方向只能填 1 或 -1")
    if not (0 < PAN_RANGE_NS <= 400000 and 0 < TILT_RANGE_NS <= 100000):
        raise ValueError("水平范围应在 1～400000ns；俯仰保持 1～100000ns")
    if TOUCH_ACTIVE_LEVEL not in (0, 1) or not 0 <= TOUCH_HOLD_MS <= 3000:
        raise ValueError("触摸有效电平只能为 0/1，反馈保持时间为 0～3000ms")
    if STEP_NS <= 0 or STEP_INTERVAL_MS <= 0 or RAMP_STEP_NS <= 0:
        raise ValueError("每步幅度、起步增量和间隔必须大于 0")
    if not (CENTER_NS - PAN_RANGE_NS <= PAN_HOME_NS <= CENTER_NS + PAN_RANGE_NS and
            CENTER_NS - TILT_RANGE_NS <= TILT_HOME_NS <= CENTER_NS + TILT_RANGE_NS):
        raise ValueError("默认姿势必须位于现有舵机活动范围内")
    if not 0 <= TILT_NEAR_EXTRA_NS <= 20000:
        raise ValueError("感应额外抬头幅度只能为 0～20000ns；实际安装间隙仍需检查")
    if not (CENTER_NS - TILT_RANGE_NS - 20000 <= TILT_MIN_NS <=
            min(TILT_HOME_NS, TILT_DOWN_NS, TILT_NEAR_NS) and
            max(TILT_HOME_NS, TILT_DOWN_NS, TILT_NEAR_NS) <= TILT_MAX_NS <=
            CENTER_NS + TILT_RANGE_NS + 20000):
        raise ValueError("俯仰目标超出本次配置范围")

    pan = None
    tilt = None
    try:
        print("启动默认姿势：抬头、略朝右。第一次指令不知道原位置，不能保证缓慢到位。")
        print("默认水平/俯仰脉宽:", PAN_HOME_NS, TILT_HOME_NS)
        print("水平脉宽范围:", CENTER_NS - PAN_RANGE_NS, CENTER_NS + PAN_RANGE_NS)
        print("确保纸壳和线没有卡住；停止程序前请扶住头部。")
        # 先抬头，再略朝右；两轴分别使用自己的默认位置，并持续保持。
        tilt = SmoothServo(TILT_PIN, TILT_MIN_NS, TILT_MAX_NS, initial=TILT_HOME_NS)
        time.sleep_ms(700)
        pan = SmoothServo(PAN_PIN, CENTER_NS - PAN_RANGE_NS,
                          CENTER_NS + PAN_RANGE_NS, initial=PAN_HOME_NS)
        time.sleep_ms(700)
        if MODE == "demo":
            run_demo(pan, tilt)
        else:
            run_interaction(pan, tilt)
    except KeyboardInterrupt:
        print("收到停止指令。")
    finally:
        # 正常停止、Ctrl+C 或中途报错，都尝试关闭两只舵机的输出。
        # 释放后不会主动锁住头部，这和“回中”是两回事。
        try:
            if tilt is not None:
                tilt.close()
        finally:
            if pan is not None:
                pan.close()
        print("PWM 已停止。调整接线或装舵盘前，拔外接电源，再拔 USB。")
