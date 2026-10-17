from machine import Pin, PWM
import time

# 安装舵盘前使用。接线不变：转头信号 GPIO5，低头信号 GPIO6。
# 开发板用 USB 供电；舵机用电源板绿色 5V，两者 GND 相连。
# 只发送中位指令，不读取红外和触摸，结束后不会自动再转动。
CENTER_NS = 1500000


def main():
    pan_signal = Pin(5, Pin.OUT, value=0)
    tilt_signal = Pin(6, Pin.OUT, value=0)
    pan = None
    tilt = None
    try:
        print("两只舵机依次回中。先不装舵盘和纸壳，保持输出轴自由。")
        pan = PWM(pan_signal, freq=50, duty_u16=0)
        print("第一只 GPIO5：回到中间。")
        pan.duty_ns(CENTER_NS)
        time.sleep_ms(1000)
        pan.duty_u16(0)

        tilt = PWM(tilt_signal, freq=50, duty_u16=0)
        print("第二只 GPIO6：回到中间。")
        tilt.duty_ns(CENTER_NS)
        time.sleep_ms(1000)
        tilt.duty_u16(0)
    finally:
        try:
            try:
                if tilt is not None:
                    tilt.deinit()
            finally:
                if pan is not None:
                    pan.deinit()
        finally:
            pan_signal.init(Pin.OUT, value=0)
            tilt_signal.init(Pin.OUT, value=0)

    print("回中指令已完成，程序结束。")
    print("先拔外接适配器电源，再拔 USB，然后安装舵盘。不要用手拧动输出轴。")


if __name__ == "__main__":
    main()
