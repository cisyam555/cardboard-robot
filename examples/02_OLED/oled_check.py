from machine import Pin, I2C
import time
import ssd1306


# 只增加错误提示，显示命令仍使用原来的 SSD1306 驱动。
class CheckedOLED(ssd1306.SSD1306_I2C):
    def write_cmd(self, cmd):
        try:
            super().write_cmd(cmd)
        except OSError:
            print("出错位置：发送命令", hex(cmd))
            raise

    def write_data(self, buf):
        try:
            super().write_data(buf)
        except OSError:
            print("出错位置：发送画面，字节数", len(buf))
            raise


print("开始 OLED 检查：改用硬件 I2C，引脚保持 SDA=0、SCL=1")
try:
    i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=100000)
    time.sleep_ms(300)
    addresses = i2c.scan()
    print("扫描结果：", addresses)
    if 60 not in addresses:
        print("没有找到地址 60。请先断开 USB，再检查接线和焊点。")
    else:
        print("开始初始化屏幕……")
        oled = CheckedOLED(128, 64, i2c, addr=0x3C)
        oled.fill(0)
        oled.text("Hello Robot!", 0, 0, 1)
        oled.show()
        print("完成：请观察屏幕是否显示 Hello Robot!")
except OSError as error:
    print("检查未通过：", error)
    print("请保留以上输出，特别是扫描结果和出错位置。")
