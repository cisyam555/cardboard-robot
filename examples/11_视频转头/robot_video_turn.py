"""ESP32-C3 小纸壳机器人：平滑转头、摸头低头。

先用 MODE = "demo" 看动作，再改成 "interaction" 测红外和触摸。
这是按视频动作思路写的 MicroPython 程序，不是视频作者的源码。
"""

from machine import Pin, PWM
import time


# ==================== 1. 你可以修改的设置 ====================

# demo：不用屏幕和传感器，自动演示一次，随后保持中位，等待你按停止。
# interaction：左右红外控制转头，触摸控制低头，屏幕显示之前选好的表情。
MODE = "demo"

PAN_PIN = 5                  # 第一只舵机的信号线：负责左右转头。
TILT_PIN = 6                 # 第二只舵机的信号线：负责低头、抬回。
LEFT_IR_PIN = 4              # 面对屏幕时，你左边的红外模块 OUT。
RIGHT_IR_PIN = 3             # 面对屏幕时，你右边的红外模块 OUT。
TOUCH_PIN = 10               # 触摸模块 SIG：已测到摸到是 1，松开是 0。
IR_ACTIVE_LEVEL = 0          # 常见避障模块检测到物体时输出 0。

CENTER_NS = 1500000          # 1500000 纳秒 = 1.5 毫秒，是先前用过的中位。
PAN_RANGE_NS = 100000        # 先沿用 1.4～1.6 毫秒的小范围，不直接大角度转。
TILT_RANGE_NS = 100000       # 低头同样先小幅试转，避免头壳撞到身体。
PAN_DIRECTION = 1           # 如果左右反了，只把这里改成 -1。
TILT_DIRECTION = -1         # 如果本该低头却抬头，只把这里改成 1。

# 这些数值是“脉冲宽度”，不是角度。实际角度取决于舵机和安装方向。
PAN_LEFT_NS = CENTER_NS - PAN_DIRECTION * PAN_RANGE_NS
PAN_RIGHT_NS = CENTER_NS + PAN_DIRECTION * PAN_RANGE_NS
TILT_DOWN_NS = CENTER_NS + TILT_DIRECTION * TILT_RANGE_NS

STEP_INTERVAL_MS = 20        # 大约每 20 毫秒走一小步。
STEP_NS = 4000              # 每步最多改变 4000 纳秒，100000 纳秒约需 0.5 秒。
INPUT_STABLE_MS = 60         # 输入持续 60 毫秒才承认，减少边缘检测时来回抖动。
RETURN_DELAY_MS = 400        # 手短暂离开检测区时先等一下，再回中。

# 供电沿用已经接好的方式，不需要重新接线：
# 两只舵机红线 -> 电源板绿色 5V；棕/黑线 -> 黑色 GND。
# ESP32 的 G -> 同一电源板黑色 GND，保证信号有共同的电压参考。
# 屏幕/触摸/红外 VCC -> 黄色 3.3V；各自 GND -> 黑色 GND。
# OLED SDA -> GPIO0，SCL -> GPIO1；红色 VIN 是原始 12V，不能接模块。
# 调试时 ESP32 用 USB 供电，其 5V、3.3 引脚不接外部电源输出。


# ==================== 2. 为什么舵机会转、怎样慢慢转 ====================

class SmoothServo:
    """用逐步改变脉宽的方式转动普通位置型 SG90。"""

    def __init__(self, pin_number, minimum, maximum):
        self.minimum = minimum
        self.maximum = maximum
        self.current = CENTER_NS
        self.target = CENTER_NS
        self.next_step = time.ticks_ms()
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
            return
        if remaining > 0:
            self.current += min(STEP_NS, remaining)
        else:
            self.current -= min(STEP_NS, -remaining)
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


# ==================== 3. 自动演示：先看清两只舵机的动作 ====================

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


# ==================== 4. 屏幕：保留你之前选择的三种表情 ====================

# 表情绘制函数在下面；互动模式才会创建 OLED，演示模式不依赖屏幕。


def rounded_eye(oled, x, y, width, height, radius=8):
    """逐行画圆角眼睛；眼睛形状与前面的 oled_face.py 一致。"""
    radius = min(radius, width // 2, height // 2)
    for row in range(height):
        inset = 0
        if radius > 1:
            if row < radius:
                dy = radius - 1 - row
                inset = radius - 1 - int(((radius - 1) ** 2 - dy ** 2) ** 0.5)
            elif row >= height - radius:
                dy = row - (height - radius)
                inset = radius - 1 - int(((radius - 1) ** 2 - dy ** 2) ** 0.5)
        oled.hline(x + inset, y + row, width - 2 * inset, 1)


def thick_line(oled, points, thickness=2):
    """沿几个坐标连接线段，组成嘴巴或其他线条。"""
    for offset in range(thickness):
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            oled.line(x1, y1 + offset, x2, y2 + offset, 1)


def draw_touch_face(oled):
    """触摸表情：平上沿、圆下沿的半垂眼睛，加一张小撇嘴。"""
    for x in (31, 75):
        # 眼睛上半部是平顶矩形，下半部是半圆。
        for row in range(9):
            oled.hline(x, 21 + row, 22, 1)
        for row in range(11):
            inset = 10 - int((100 - row * row) ** 0.5)
            oled.hline(x + inset, 30 + row, 22 - 2 * inset, 1)

    # 中间高、两端低，形成图片中的小撇嘴。
    mouth = ((58, 40), (59, 38), (61, 37), (63, 36),
             (65, 36), (67, 37), (69, 38), (70, 40))
    thick_line(oled, mouth, 3)


def filled_oval(oled, center_x, center_y, radius_x, radius_y, color):
    """逐行填充椭圆；1 点亮，0 擦黑。"""
    for dy in range(-radius_y, radius_y + 1):
        half_width = int(radius_x * (1 - (dy / (radius_y + 0.5)) ** 2) ** 0.5 + 0.5)
        oled.hline(center_x - half_width, center_y + dy,
                   half_width * 2 + 1, color)


def draw_near_face(oled):
    """靠近表情：带小亮点的椭圆眼睛，加弯弯的笑嘴。"""
    for center_x in (40, 88):
        # 先画白色大椭圆，再擦黑中间，留下白色眼圈。
        filled_oval(oled, center_x, 29, 11, 14, 1)
        filled_oval(oled, center_x, 29, 7, 10, 0)
        # 左上角添一个白色亮点。
        filled_oval(oled, center_x - 5, 22, 3, 3, 1)

    mouth = ((57, 41), (59, 44), (62, 45),
             (66, 45), (69, 44), (71, 41))
    thick_line(oled, mouth, 3)


def draw_face(oled, expression):
    oled.fill(0)
    if expression == "touched":
        draw_touch_face(oled)
    elif expression == "near":
        draw_near_face(oled)
    else:
        height = 2 if expression == "closed" else 32
        y = 29 - height // 2
        rounded_eye(oled, 28, y, 24, height)
        rounded_eye(oled, 76, y, 24, height)
        mouth = ((55, 48), (59, 50), (64, 51), (69, 50), (73, 48))
        thick_line(oled, mouth)
    oled.show()


# ==================== 5. 互动循环：同时读输入、动舵机、画表情 ====================

def run_interaction(pan, tilt):
    # 延迟导入：自动演示只需要舵机，不需要接屏幕或上传屏幕驱动。
    from machine import I2C
    import ssd1306

    i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=100000)
    if 0x3C not in i2c.scan():
        raise OSError("未找到地址 60 的屏幕，请断电检查屏幕接线和供电。")
    oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
    touch = StableInput(TOUCH_PIN, 1)
    left_ir = StableInput(LEFT_IR_PIN, IR_ACTIVE_LEVEL, pull_up=True)
    right_ir = StableInput(RIGHT_IR_PIN, IR_ACTIVE_LEVEL, pull_up=True)

    last_seen_at = None
    last_near_target = CENTER_NS
    last_blink = time.ticks_ms()
    blink_until = None
    shown = None
    previous_inputs = None
    print("互动开始：左红外转左，右红外转右，摸头低头。")

    while True:
        now = time.ticks_ms()
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

        inputs = (touched, left, right)
        if inputs != previous_inputs:
            print("触摸:", int(touched), "左红外:", int(left),
                  "右红外:", int(right))
            previous_inputs = inputs
        time.sleep_ms(5)


def main():
    if MODE not in ("demo", "interaction"):
        raise ValueError('MODE 只能填 "demo" 或 "interaction"')
    if PAN_DIRECTION not in (-1, 1) or TILT_DIRECTION not in (-1, 1):
        raise ValueError("方向只能填 1 或 -1")
    if not (0 < PAN_RANGE_NS <= 100000 and 0 < TILT_RANGE_NS <= 100000):
        raise ValueError("先保持已测试的小范围：范围应大于 0，且不超过 100000")
    if STEP_NS <= 0 or STEP_INTERVAL_MS <= 0:
        raise ValueError("每步幅度和间隔必须大于 0")

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


if __name__ == "__main__":
    main()

