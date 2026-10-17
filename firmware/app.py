"""演示和互动循环，以及退出时的硬件释放。"""
import time
from servo import SmoothServo
from sensors import StableInput
from behavior import choose_action
from faces import draw_face

from config import (
    CENTER_NS,
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
        ("第一只：向左", PAN_LEFT_NS, CENTER_NS),
        ("第一只：回中", CENTER_NS, CENTER_NS),
        ("第一只：向右", PAN_RIGHT_NS, CENTER_NS),
        ("第一只：回中", CENTER_NS, CENTER_NS),
        ("第二只：低头", CENTER_NS, TILT_DOWN_NS),
        ("第二只：抬回中位", CENTER_NS, CENTER_NS),
    )
    for message, pan_target, tilt_target in actions:
        print(message)
        move_and_wait(pan, tilt, pan_target, tilt_target)
    print("演示完成，现在保持中位。按 Thonny 红色停止按钮结束。")
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
    touch = StableInput(TOUCH_PIN, 1)
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
    last_near_target = CENTER_NS
    last_blink = time.ticks_ms()
    blink_until = None
    shown = None
    previous_mode = "standalone"
    while True:
        now = time.ticks_ms()
        for line in link.read_lines():
            controller.receive(line, now)
        centered = (pan.current == CENTER_NS and tilt.current == CENTER_NS)
        mode = controller.update(now, centered)
        if mode != previous_mode:
            last_seen_at = None
            previous_mode = mode
        touched = touch.read(now)
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

        if mode == "centering":
            expression, pan_target, tilt_target = "normal", CENTER_NS, CENTER_NS
        elif mode == "ros2":
            action = controller.action
            expression = "touched" if action == "bow" else (
                "normal" if action == "idle" else "near")
            pan_target = (PAN_LEFT_NS if action == "look_left" else
                          PAN_RIGHT_NS if action == "look_right" else CENTER_NS)
            tilt_target = TILT_DOWN_NS if action == "bow" else CENTER_NS

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
        display = (expression, mode)
        if display != shown:
            draw_face(oled, expression, mode)
            shown = display

        if time.ticks_diff(now, last_report) >= TELEMETRY_INTERVAL_MS:
            link.send({"v": 1, "touch": touched, "left": left, "right": right,
                       "mode": mode})
            last_report = now
        time.sleep_ms(5)



def main():
    if MODE not in ("demo", "interaction", "standalone"):
        raise ValueError('MODE 只能填 "demo"、"interaction" 或 "standalone"')
    if PAN_DIRECTION not in (-1, 1) or TILT_DIRECTION not in (-1, 1):
        raise ValueError("方向只能填 1 或 -1")
    if not (0 < PAN_RANGE_NS <= 100000 and 0 < TILT_RANGE_NS <= 100000):
        raise ValueError("先保持已测试的小范围：范围应大于 0，且不超过 100000")
    if STEP_NS <= 0 or STEP_INTERVAL_MS <= 0 or RAMP_STEP_NS <= 0:
        raise ValueError("每步幅度、起步增量和间隔必须大于 0")

    pan = None
    tilt = None
    try:
        print("启动时先回中。第一次指令不知道舵机原位置，不能保证慢慢回中。")
        print("先卸下头壳试转；装着头壳时，停止程序前请扶住。")
        # 依次启动，减少两只同时起动带来的瞬时电流；中位持续保持。
        pan = SmoothServo(PAN_PIN, CENTER_NS - PAN_RANGE_NS,
                          CENTER_NS + PAN_RANGE_NS)
        time.sleep_ms(700)
        tilt = SmoothServo(TILT_PIN, CENTER_NS - TILT_RANGE_NS,
                           CENTER_NS + TILT_RANGE_NS)
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

