# 02 OLED 排错第三步：连续扫描 20 次，看连接是不是"时好时坏"
# 用法：运行后看下面每一行的结果。
#   - 如果 20 行全是 [60]        -> 线是稳的，问题在通信速度，跑 oled_fix.py
#   - 如果偶尔出现 []            -> 就是杜邦线虚接，需要重新插紧或换线
#   - 如果出现很多地址（比如一长串数字）-> SDA 可能被短路到地，先拔线检查

from machine import Pin, SoftI2C
import time

i2c = SoftI2C(sda=Pin(0), scl=Pin(1), freq=100000)

ok = 0
for i in range(20):
    found = i2c.scan()
    print("第", i + 1, "次：", found)
    if 60 in found:
        ok = ok + 1
    time.sleep(0.3)

print("20 次里有", ok, "次找到了屏幕 60")
