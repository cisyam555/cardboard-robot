from machine import Pin, I2C
import ssd1306
import time

# 接线保持不变：GND -> G，VCC -> 3.3，SCL -> 1，SDA -> 0。
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=100000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)


def draw_eyes(height):
    # height 决定眼睛高度；保持眼睛的中心在同一水平线上。
    y = 32 - height // 2
    oled.fill(0)
    oled.fill_rect(24, y, 28, height, 1)
    oled.fill_rect(76, y, 28, height, 1)
    oled.show()


print("开始眨眼。点击 Thonny 红色停止按钮即可停止程序。")

while True:
    draw_eyes(24)       # 睁眼：画两个高 24 像素的矩形。
    time.sleep(2)      # 保持睁眼 2 秒。
    draw_eyes(2)        # 闭眼：把矩形压成高 2 像素的细线。
    time.sleep(0.15)   # 保持闭眼 0.15 秒，然后重新睁眼。
