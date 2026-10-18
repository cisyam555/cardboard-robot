"""输入到表情和目标脉宽的映射；触摸优先。"""
import time

from config import (
    PAN_HOME_NS,
    TILT_HOME_NS,
    TILT_NEAR_NS,
    PAN_LEFT_NS,
    PAN_RIGHT_NS,
    TILT_DOWN_NS,
)


class TouchLatch:
    """短暂轻触也保留低头和表情；持续触摸时不断延长保持时间。"""

    def __init__(self, hold_ms):
        self.hold_ms = hold_ms
        self.last_touch_at = None

    def update(self, detected, now):
        if detected:
            self.last_touch_at = now
            return True
        return (self.last_touch_at is not None and
                time.ticks_diff(now, self.last_touch_at) < self.hold_ms)


def choose_action(touched, left, right):
    """只负责决定目标；实际怎么慢慢走，由 SmoothServo 负责。"""
    if touched:
        # 摸头优先：回默认左右朝向并低头；持续摸着就保持，不来回摇晃。
        return "touched", PAN_HOME_NS, TILT_DOWN_NS
    if left and not right:
        return "near", PAN_LEFT_NS, TILT_NEAR_NS
    if right and not left:
        return "near", PAN_RIGHT_NS, TILT_NEAR_NS
    if left and right:
        # 两边都有物体时无法判定偏向哪边，选择默认朝向。
        return "near", PAN_HOME_NS, TILT_NEAR_NS
    return "normal", PAN_HOME_NS, TILT_HOME_NS
