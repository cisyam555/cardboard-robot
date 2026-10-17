from machine import Pin, I2C
import ssd1306
import time


def rounded_eye(oled, x, y, width, height, radius=8):
    """逐行画实心圆角眼睛，兼容没有圆角绘图函数的 SSD1306 驱动。"""
    radius = min(radius, width // 2, height // 2)
    for row in range(height):
        # 中间的行画满；顶部和底部的行左右缩进，形成圆角。
        inset = 0
        if radius > 1:
            if row < radius:
                dy = radius - 1 - row
                inset = radius - 1 - int(((radius - 1) ** 2 - dy ** 2) ** 0.5)
            elif row >= height - radius:
                dy = row - (height - radius)
                inset = radius - 1 - int(((radius - 1) ** 2 - dy ** 2) ** 0.5)
        oled.hline(x + inset, y + row, width - 2 * inset, 1)


def draw_face(oled, eye_height=32):
    """画图片中的大眼睛和小笑嘴；eye_height 越小，眼睛越扁。"""
    oled.fill(0)

    # 眼睛高 32 像素时，从第 13 行开始画；眨眼时保持中心位置不变。
    y = 29 - eye_height // 2
    rounded_eye(oled, 28, y, 24, eye_height)  # 左眼：宽 24 像素。
    rounded_eye(oled, 76, y, 24, eye_height)  # 右眼。

    # 用几小段线拼出向上翘的小笑嘴，画两遍使线条厚 2 像素。
    points = ((55, 48), (59, 50), (64, 51), (69, 50), (73, 48))
    for offset in (0, 1):
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            oled.line(x1, y1 + offset, x2, y2 + offset, 1)

    oled.show()


def main():
    # 硬件 I2C：SDA -> 0，SCL -> 1。屏幕使用 3.3V，GND 与开发板共地。
    # 当前装机接法：VCC -> 电源板黄色 3.3V；GND -> 电源板黑色 GND。
    i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=100000)
    oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
    print("圆角眼睛和笑嘴：睁眼 2.5 秒，闭眼 0.12 秒。红色停止按钮可结束。")

    while True:
        draw_face(oled, 32)  # 睁眼：高 32 像素。
        time.sleep(2.5)
        draw_face(oled, 2)   # 闭眼：变成两条细线；笑嘴保持不变。
        time.sleep(0.12)


if __name__ == "__main__":
    main()
