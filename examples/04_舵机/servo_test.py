from machine import Pin, PWM
import time

# 只测一个普通位置型 SG90，先不安装摇臂和机器人机构。
# 舵机红线 -> 外部电源板绿色 5V，棕/黑线 -> 电源板黑色 GND。
# 舵机橙/黄信号线 -> ESP32-C3 GPIO5。
# ESP32-C3 G 必须额外连到电源板黑色 GND，形成公共地线。
# ESP32-C3 通过 USB 供电；外部电源板的 5V 不连接开发板。

servo = None
try:
    # 先启动 PWM，再设置脉冲宽度。
    # 当前固件在构造函数中传 duty_ns 时会过早校验尚未启用的定时器。
    # duty_u16=0 让刚创建的输出先保持低电平，避免默认占空比产生过长脉冲。
    servo = PWM(Pin(5), freq=50, duty_u16=0)
    # 每秒 50 个脉冲。1500000 纳秒 = 1500 微秒，是常见 SG90 的中间位置。
    servo.duty_ns(1500000)
    print("舵机回到中间位置；初次回中可能转动较多，请保持输出轴无负载。")
    time.sleep(1)

    # 小幅改变脉冲宽度，实际转角随舵机而异，不测试两端极限位置。
    for _ in range(2):
        print("向一边小幅转动")
        servo.duty_ns(1400000)
        time.sleep(1)
        print("向另一边小幅转动")
        servo.duty_ns(1600000)
        time.sleep(1)

    print("回到中间位置")
    servo.duty_ns(1500000)
    time.sleep(1)
finally:
    if servo is not None:
        servo.deinit()  # 测完关闭控制脉冲，不再持续保持位置。
    Pin(5, Pin.OUT, value=0)

print("测试完成：先拔掉外部适配器电源，再拔 USB，之后才更改接线。")
