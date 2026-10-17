# 02 OLED 第一步：让屏幕显示文字
# 接线：OLED GND→G，VCC→3.3，SCL→1，SDA→0
# 注意：运行前必须先把 ssd1306.py 存到开发板里

from machine import Pin, SoftI2C
from ssd1306 import SSD1306_I2C
import time

# 1. 打开屏幕的通信口（和扫描测试用的是同样的引脚）
i2c = SoftI2C(sda=Pin(0), scl=Pin(1), freq=100000)

# 2. 认领这块屏幕：宽128、高64、地址60(0x3C)
oled = SSD1306_I2C(128, 64, i2c)

while True:
    # 第一种画面：文字分别在左上角和左下角
    oled.fill(0)                      # 清屏，全黑
    oled.text("HELLO", 0, 0)          # 左上角
    oled.text("ZHI KE ROBOT", 0, 56)  # 左下角（第56行，最下面一行）
    oled.show()                       # 把画面真正送到屏幕
    time.sleep(2)

    # 第二种画面：文字在屏幕中间
    oled.fill(0)                      # 每次重画前都要清屏，否则会叠字
    oled.text("HELLO", 0, 28)         # 第28行，中间
    oled.show()
    time.sleep(2)
