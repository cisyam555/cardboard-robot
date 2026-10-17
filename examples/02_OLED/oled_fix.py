# 02 OLED 排错第二步：扫描能过、显示失败时，换通信速度逐个试
# 用法：拔掉 USB 等 5 秒再插回（给屏幕彻底断一次电），然后运行本文件，
#       把 Shell 里从 “---- 频率” 到 “测试结束” 的全部文字发给我。

from machine import Pin, SoftI2C
from ssd1306 import SSD1306_I2C
import time

for freq in (100000, 50000, 20000, 10000):
    print("---- 频率", freq)
    try:
        i2c = SoftI2C(sda=Pin(0), scl=Pin(1), freq=freq)
        found = i2c.scan()
        print("扫描结果：", found)

        if 60 not in found:
            print("屏幕这次没回应，换下一个频率再试")
            continue

        oled = SSD1306_I2C(128, 64, i2c, addr=0x3C)
        oled.fill(0)
        oled.text("Hello Robot!", 0, 0)
        oled.show()
        print("成功！屏幕应该出字了，可用的频率是：", freq)
        break
    except Exception as e:
        print("这个频率失败：", e)

print("测试结束")
