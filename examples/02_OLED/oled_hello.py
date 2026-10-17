from machine import Pin, I2C
import ssd1306

# SDA 是数据线，SCL 是时钟线；引脚与刚才扫描时相同。
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=100000)

# 128×64 是本次测试的屏幕分辨率；0x3C 就是扫描到的十进制 60。
oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

oled.fill(0)  # 清空画面缓冲区。
oled.text("Hello Robot!", 0, 0, 1)  # 在左上角写入英文文字。
oled.show()  # 把缓冲区中的画面发送给屏幕。
print("显示指令已发送，请观察屏幕。")
