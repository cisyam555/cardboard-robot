"""GPIO5 左右，GPIO6 上下。仅测试两只舵机，不需要屏幕或传感器。

先将 firmware/config.py、firmware/servo.py 上传开发板根目录。
在 Thonny 停止原 main.py 后运行本文件。动作只演示一遍，结束回中保持。
方向按安装校准；脉宽并非角度，不保证复现参考视频的实际转角。
"""
import time
from config import (
    CENTER_NS, PAN_PIN, TILT_PIN, PAN_RANGE_NS, TILT_RANGE_NS,
    PAN_LEFT_NS, PAN_RIGHT_NS, TILT_UP_NS, TILT_DOWN_NS,
)
from servo import SmoothServo


def pose(pan, tilt, horizontal, vertical, hold_ms=500):
    """双轴同时更新：先平滑到位，再短暂停留。"""
    pan.set_target(horizontal)
    tilt.set_target(vertical)
    while pan.current != pan.target or tilt.current != tilt.target:
        now = time.ticks_ms()
        pan.update(now)
        tilt.update(now)
        time.sleep_ms(5)
    # 演示用停顿；正式互动循环没有这个长等待。
    time.sleep_ms(hold_ms)


def main():
    if PAN_PIN != 5 or TILT_PIN != 6:
        raise ValueError("本演示要求 config.py 中 PAN_PIN=5、TILT_PIN=6")
    if not (0 < PAN_RANGE_NS <= 100000 and 0 < TILT_RANGE_NS <= 100000):
        raise ValueError("先保持已经测试过的 100000ns 以内小幅动作范围")
    pan = None
    tilt = None
    try:
        pan = SmoothServo(PAN_PIN, CENTER_NS-PAN_RANGE_NS, CENTER_NS+PAN_RANGE_NS)
        time.sleep_ms(700)
        tilt = SmoothServo(TILT_PIN, CENTER_NS-TILT_RANGE_NS, CENTER_NS+TILT_RANGE_NS)
        time.sleep_ms(700)
        actions = (
            ("左看", PAN_LEFT_NS, CENTER_NS),
            ("右看", PAN_RIGHT_NS, CENTER_NS),
            ("回中", CENTER_NS, CENTER_NS),
            ("抬头", CENTER_NS, TILT_UP_NS),
            ("低头", CENTER_NS, TILT_DOWN_NS),
            ("回中", CENTER_NS, CENTER_NS),
            ("左上看：两轴联动", PAN_LEFT_NS, TILT_UP_NS),
            ("右上看：两轴联动", PAN_RIGHT_NS, TILT_UP_NS),
            ("低头：模拟摸头反应", CENTER_NS, TILT_DOWN_NS),
            ("回中", CENTER_NS, CENTER_NS),
        )
        for label, horizontal, vertical in actions:
            print(label)
            pose(pan, tilt, horizontal, vertical)
        print("演示结束，保持中位。扶住头部后再按停止；停止将释放舵机。")
        while True:
            time.sleep_ms(100)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if tilt is not None:
                tilt.close()
        finally:
            if pan is not None:
                pan.close()


if __name__ == '__main__':
    main()
