from machine import Pin, I2C
import ssd1306

# 沿用已经成功显示的硬件 I2C 配置，接线不用改变。
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=100000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

oled.fill(0)  # 先把画面清成黑色。

# fill_rect(x, y, 宽, 高, 颜色)：从左上角坐标开始画实心矩形。
# 屏幕左上角是 (0, 0)，x 向右增加，y 向下增加；1 是亮，0 是灭。
oled.fill_rect(24, 20, 28, 24, 1)  # 左眼。
oled.fill_rect(76, 20, 28, 24, 1)  # 右眼。

oled.show()  # 将两只眼睛发送到屏幕。
print("双眼画面已发送，请观察屏幕。")
