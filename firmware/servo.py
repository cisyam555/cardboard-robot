"""SG90 PWM 控制与平滑步进。"""
from machine import Pin, PWM
import time

from config import (
    CENTER_NS,
    STEP_INTERVAL_MS,
    STEP_NS,
    RAMP_STEP_NS,
)

class SmoothServo:
    """用逐步改变脉宽的方式转动普通位置型 SG90。"""

    def __init__(self, pin_number, minimum, maximum):
        self.minimum = minimum
        self.maximum = maximum
        self.current = CENTER_NS
        self.target = CENTER_NS
        self.next_step = time.ticks_ms()
        self.step = 0
        self.direction = 0
        self.pwm = None
        self.pin = Pin(pin_number, Pin.OUT, value=0)
        try:
            # 普通 SG90 常用 50Hz：每秒发 50 个脉冲，一个周期约 20 毫秒。
            # 脉冲的“高电平持续多久”决定目标位置；频率不是转动速度。
            # 先创建 PWM 再设 duty_ns，避开这块板此前出现的 PWM is inactive。
            self.pwm = PWM(self.pin, freq=50, duty_u16=0)
            self.pwm.duty_ns(CENTER_NS)
        except BaseException:
            # 即使构造中途报错，也要关掉已经创建的 PWM。
            self.close()
            raise

    def set_target(self, target):
        # 限制软件允许的范围，防止其他逻辑无意间给出过大的目标。
        # 这不能检测机械卡住，安装时仍要先检查间隙。
        self.target = max(self.minimum, min(self.maximum, target))

    def update(self, now):
        # ticks_diff 可以正确处理运行时间计数回绕，不能直接用 now > deadline。
        if time.ticks_diff(now, self.next_step) < 0:
            return
        self.next_step = time.ticks_add(now, STEP_INTERVAL_MS)

        remaining = self.target - self.current
        if remaining == 0:
            self.step = 0
            self.direction = 0
            return
        direction = 1 if remaining > 0 else -1
        if direction != self.direction:
            # 中途改变方向时，从小步幅重新起动。
            self.step = 0
        self.direction = direction
        # 起动逐渐增加步幅；接近目标时逐渐减小步幅。
        # 至少走一个 ramp 步长，最后一步精确到目标，避免无限接近。
        desired = min(STEP_NS, max(RAMP_STEP_NS, abs(remaining) // 4))
        self.step = min(desired, self.step + RAMP_STEP_NS)
        self.current += direction * min(self.step, abs(remaining))
        self.pwm.duty_ns(self.current)

        # 旧测试程序转完就停止脉冲；挂上头壳后可能下垂。
        # 这里让硬件 PWM 持续输出，舵机会尽力保持位置，不必反复写同一个数。
        # current 只是程序发出的指令，不是读回的真实角度；SG90 没有反馈线。

    def close(self):
        try:
            if self.pwm is not None:
                self.pwm.deinit()
        finally:
            self.pin.init(Pin.OUT, value=0)

