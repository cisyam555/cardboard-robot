"""数字输入稳定检测。"""
from machine import Pin
import time

from config import (
    INPUT_STABLE_MS,
)

class StableInput:
    """等信号连续稳定一小段时间，才更新检测结果。"""

    def __init__(self, pin_number, active_level, pull_up=False):
        if pull_up:
            self.pin = Pin(pin_number, Pin.IN, Pin.PULL_UP)
        else:
            self.pin = Pin(pin_number, Pin.IN)
        self.active_level = active_level
        self.value = False
        self.candidate = False
        self.changed_at = time.ticks_ms()

    def read(self, now):
        active = self.pin.value() == self.active_level
        if active != self.candidate:
            self.candidate = active
            self.changed_at = now
        if time.ticks_diff(now, self.changed_at) >= INPUT_STABLE_MS:
            self.value = self.candidate
        return self.value

