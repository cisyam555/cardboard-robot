from machine import Pin
import time

# 只用 USB 供电：模块 VCC -> 开发板 3.3，GND -> G，OUT -> GPIO4。
# 先单独测试一块红外模块，屏幕和其他模块暂时断开。
sensor = Pin(4, Pin.IN, Pin.PULL_UP)
last_value = None

print("红外测试开始：用手在两个探头前方约 2～5 厘米处靠近、移开。")
print("常见模块检测到物体时 OUT=0，未检测到时 OUT=1。")
print("观察实际变化；点击 Thonny 红色停止按钮可结束。")

while True:
    value = sensor.value()
    # 只有信号变化时才打印，方便对照手的位置。
    if value != last_value:
        if value == 0:
            print("OUT=0：检测到物体")
        else:
            print("OUT=1：没有检测到物体")
        last_value = value
    time.sleep(0.05)
