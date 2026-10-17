from machine import Pin, I2C, PWM
import ssd1306
import time

IR_ACTIVE_LEVEL = 0
LEFT_IR_PIN = 4
RIGHT_IR_PIN = 3
PAN_PIN = 5
TILT_PIN = 6
SERVO_CENTER_NS = 1500000
# 两个位置先用于验证转动方向，装好头部后再按实际方向对调。
PAN_LEFT_NS = 1400000
PAN_RIGHT_NS = 1600000
SERVO_TOUCH_NS = 1600000
TILT_TOUCH_NS = 1400000
SERVO_MOVE_MS = 600

# 开发板由 USB 供电；两只普通位置型 SG90 由外部电源板绿色 5V 供电。
# 两只舵机的红线 -> 绿色 5V，棕/黑线 -> 黑色 GND。
# 第一只（以后转头）信号线 -> GPIO5；第二只（以后点头）信号线 -> GPIO6。
# 外部电源板黑色 GND -> 面包板第 25 排，与开发板 G 共地。
# 外部电源板的 5V、VIN 不连接开发板；先不安装舵盘或纸壳机构。
# 测试时可沿用面包板分线；装机时可按同目录《不用面包板接线说明.md》
# 把屏幕、触摸、两块红外的 VCC 全部改接电源板黄色 3.3V。
# 改接后不再使用开发板 3.3 引脚分电，也不连接两块板的 3.3V 输出。
# OLED SDA -> GPIO0，SCL -> GPIO1；触摸 SIG -> GPIO10。
# 左红外 OUT -> GPIO4，右红外 OUT -> GPIO3。
# 两块红外 VCC 都用 3.3V；GND 与开发板共地。
# 所有 GND 接电源板黑色 GND；插针不够时使用同电位 GND 分线器。
# 面对屏幕时，把 GPIO4 模块放在你的左边，GPIO3 模块放在你的右边。
# 常见红外避障模块：检测到物体时为 0。若实测相反，仅修改下面常量。
# ssd1306.py 继续使用已经保存在开发板上的文件。


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


def update_servo(servo, target, previous_target, stop_at, now):
    """目标改变时转动，600 毫秒后停止脉冲；不阻塞传感器读取。"""
    if target != previous_target:
        servo.duty_ns(target)
        previous_target = target
        stop_at = time.ticks_add(now, SERVO_MOVE_MS)
    if stop_at is not None and time.ticks_diff(now, stop_at) >= 0:
        servo.duty_u16(0)
        stop_at = None
    return previous_target, stop_at


def run_interaction(oled, touch, infrared_left, infrared_right, pan, tilt):
    # 记录上次画面，仅在表情变化时刷新屏幕。
    shown = None
    last_inputs = None
    last_blink = time.ticks_ms()
    blink_until = None
    pan_target = SERVO_CENTER_NS
    tilt_target = SERVO_CENTER_NS
    pan_stop_at = None
    tilt_stop_at = None

    while True:
        now = time.ticks_ms()
        touched = touch.value() == 1  # 已实测：摸到为 1，松开为 0。

        left_near = infrared_left.value() == IR_ACTIVE_LEVEL
        right_near = infrared_right.value() == IR_ACTIVE_LEVEL
        near = left_near or right_near

        # 同时触发时：触摸优先，其次是靠近，平时自动眨眼。
        if touched:
            expression = "touched"
            blink_until = None
            last_blink = now
        elif near:
            expression = "near"
            blink_until = None
            last_blink = now
        elif blink_until is not None:
            if time.ticks_diff(now, blink_until) < 0:
                expression = "closed"
            else:
                expression = "normal"
                blink_until = None
        elif time.ticks_diff(now, last_blink) >= 3000:
            expression = "closed"
            blink_until = time.ticks_add(now, 200)
            last_blink = now
        else:
            expression = "normal"

        # 表情和转动共用同一组感应结果：触摸优先于红外靠近。
        # 只在目标位置变化时发出新指令，保持手不动不会反复转动。
        if touched:
            target = SERVO_TOUCH_NS
        elif left_near and not right_near:
            target = PAN_LEFT_NS
        elif right_near and not left_near:
            target = PAN_RIGHT_NS
        else:
            # 两边同时检测到，或两边都没有检测到，都回中。
            target = SERVO_CENTER_NS

        # 第一只负责左右转头；第二只只在触摸时小幅转动。
        tilt_position = TILT_TOUCH_NS if touched else SERVO_CENTER_NS
        pan_target, pan_stop_at = update_servo(
            pan, target, pan_target, pan_stop_at, now)
        tilt_target, tilt_stop_at = update_servo(
            tilt, tilt_position, tilt_target, tilt_stop_at, now)

        if expression != shown:
            draw_face(oled, expression)
            shown = expression

        inputs = (touched, left_near, right_near)
        if inputs != last_inputs:
            if touched:
                print("摸到了：半垂眼睛和小撇嘴；第一只转头，第二只小幅转动")
            elif left_near and right_near:
                print("左右都检测到：亮眼微笑；转头舵机回中")
            elif left_near:
                print("左红外检测到：亮眼微笑；转头舵机转向位置 A")
            elif right_near:
                print("右红外检测到：亮眼微笑；转头舵机转向位置 B")
            else:
                print("没有触摸或靠近：普通表情，自动眨眼；两只舵机回中")
            last_inputs = inputs

        # 只短暂停顿，避免用几秒钟的 sleep 阻挡触摸读取。
        time.sleep_ms(20)


def main():
    pan_signal = Pin(PAN_PIN, Pin.OUT, value=0)
    tilt_signal = Pin(TILT_PIN, Pin.OUT, value=0)
    pan = None
    tilt = None
    try:
        i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=100000)
        oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
        touch = Pin(10, Pin.IN)
        infrared_left = Pin(LEFT_IR_PIN, Pin.IN, Pin.PULL_UP)
        infrared_right = Pin(RIGHT_IR_PIN, Pin.IN, Pin.PULL_UP)
        draw_face(oled, "normal")
        print("两只舵机依次回中；先不装舵盘和纸壳，手离开传感器，等待 3 秒。")

        # 依次回中，避免两只舵机同时开始回中。
        # 先创建 PWM，再设置脉宽，沿用已实测成功的初始化方式。
        pan = PWM(pan_signal, freq=50, duty_u16=0)
        pan.duty_ns(SERVO_CENTER_NS)
        time.sleep_ms(1000)
        pan.duty_u16(0)

        tilt = PWM(tilt_signal, freq=50, duty_u16=0)
        tilt.duty_ns(SERVO_CENTER_NS)
        time.sleep_ms(1000)
        tilt.duty_u16(0)
        time.sleep_ms(1000)
        print("开始：左红外对应位置 A，右红外对应位置 B，两边同时触发或都移开时回中。")
        print("先验证两个转动方向，安装头部后再校准实际左右。触摸时两只舵机转动。")
        run_interaction(oled, touch, infrared_left, infrared_right, pan, tilt)
    finally:
        # 停止程序或报错时，释放两路 PWM 并拉低两根信号线。
        try:
            try:
                if tilt is not None:
                    tilt.deinit()
            finally:
                if pan is not None:
                    pan.deinit()
        finally:
            pan_signal.init(Pin.OUT, value=0)
            tilt_signal.init(Pin.OUT, value=0)
        print("控制已停止。改接线前，先拔外接电源，再拔 USB。")


if __name__ == "__main__":
    main()
