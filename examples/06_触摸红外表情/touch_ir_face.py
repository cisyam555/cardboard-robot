from machine import Pin, I2C
import ssd1306
import time

IR_ACTIVE_LEVEL = 0

# 本步骤只使用 USB 供电，外部电源板和舵机不接。
# 用面包板把开发板的 3.3V 分给 OLED VCC 和触摸 VCC；
# 把开发板的 GND 分给 OLED GND 和触摸 GND。两组电源孔互不相连。
# OLED SDA -> GPIO0，SCL -> GPIO1；触摸 SIG -> GPIO10。
# 一块红外模块 VCC -> 同一组 3.3V，GND -> 同一组 GND，OUT -> GPIO4。
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


def run_interaction(oled, touch, infrared):
    # 记录上次画面，仅在表情变化时刷新屏幕。
    shown = None
    last_inputs = None
    last_blink = time.ticks_ms()
    blink_until = None

    while True:
        now = time.ticks_ms()
        touched = touch.value() == 1  # 已实测：摸到为 1，松开为 0。

        near = infrared.value() == IR_ACTIVE_LEVEL

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

        if expression != shown:
            draw_face(oled, expression)
            shown = expression

        inputs = (touched, near)
        if inputs != last_inputs:
            if touched:
                print("摸到了：半垂眼睛和小撇嘴")
            elif near:
                print("检测到靠近：亮眼微笑")
            else:
                print("没有触摸或靠近：普通表情，自动眨眼")
            last_inputs = inputs

        # 只短暂停顿，避免用几秒钟的 sleep 阻挡触摸读取。
        time.sleep_ms(20)


def main():
    i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=100000)
    oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
    touch = Pin(10, Pin.IN)
    infrared = Pin(4, Pin.IN, Pin.PULL_UP)
    print("触摸＋红外组合测试。手先离开触摸模块和红外探头，等待 2 秒。")
    draw_face(oled, "normal")
    time.sleep_ms(2000)
    run_interaction(oled, touch, infrared)


if __name__ == "__main__":
    main()
