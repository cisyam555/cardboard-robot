"""输入到表情和目标脉宽的映射；触摸优先。"""

from config import (
    CENTER_NS,
    PAN_LEFT_NS,
    PAN_RIGHT_NS,
    TILT_DOWN_NS,
)

def choose_action(touched, left, right):
    """只负责决定目标；实际怎么慢慢走，由 SmoothServo 负责。"""
    if touched:
        # 摸头优先：朝向中间、低头；持续摸着就保持，不来回摇晃。
        return "touched", CENTER_NS, TILT_DOWN_NS
    if left and not right:
        return "near", PAN_LEFT_NS, CENTER_NS
    if right and not left:
        return "near", PAN_RIGHT_NS, CENTER_NS
    if left and right:
        # 两边都有物体时无法判定偏向哪边，选择朝中间看。
        return "near", CENTER_NS, CENTER_NS
    return "normal", CENTER_NS, CENTER_NS

