"""硬件接线和动作参数；改动后重启程序生效。"""

# demo：不用屏幕和传感器，自动演示一次，随后保持中位，等待你按停止。
# standalone：上电独立互动，并监听 USB 上的 ROS2 模式命令。
# interaction 保留为 standalone 的兼容名称。demo 仍可用于空载演示。
MODE = "standalone"

PAN_PIN = 5                  # 第一只舵机的信号线：负责左右转头。
TILT_PIN = 6                 # 第二只舵机的信号线：负责低头、抬回。
LEFT_IR_PIN = 4              # 面对屏幕时，你左边的红外模块 OUT。
RIGHT_IR_PIN = 3             # 面对屏幕时，你右边的红外模块 OUT。
TOUCH_PIN = 10               # 触摸模块 SIG：已测到摸到是 1，松开是 0。
IR_ACTIVE_LEVEL = 0          # 常见避障模块检测到物体时输出 0。

CENTER_NS = 1500000          # 1500000 纳秒 = 1.5 毫秒，是先前用过的中位。
PAN_RANGE_NS = 300000        # 左右幅度扩大到原来的 3 倍：1.2～1.8 毫秒。
TILT_RANGE_NS = 100000       # 低头同样先小幅试转，避免头壳撞到身体。
PAN_DIRECTION = 1           # 如果左右反了，只把这里改成 -1。
TILT_DIRECTION = -1         # 如果本该低头却抬头，只把这里改成 1。

# 这些数值是“脉冲宽度”，不是角度。实际角度取决于舵机和安装方向。
PAN_LEFT_NS = CENTER_NS - PAN_DIRECTION * PAN_RANGE_NS
PAN_RIGHT_NS = CENTER_NS + PAN_DIRECTION * PAN_RANGE_NS
TILT_DOWN_NS = CENTER_NS + TILT_DIRECTION * TILT_RANGE_NS
TILT_UP_NS = CENTER_NS - TILT_DIRECTION * TILT_RANGE_NS

# 安装后的默认姿势：面对屏幕时略朝右、抬高头部。
# 仅调整默认位置；左右红外目标和触摸低头目标仍沿用上面的数值。
PAN_HOME_OFFSET_NS = 60000   # 向右偏一点；约为当前单侧转头幅度的五分之一。
TILT_HOME_LIFT_NS = 100000   # 沿用刚才抬头测试的幅度，不超出已用范围。
PAN_HOME_NS = CENTER_NS + PAN_DIRECTION * PAN_HOME_OFFSET_NS
TILT_HOME_NS = CENTER_NS - TILT_DIRECTION * TILT_HOME_LIFT_NS

# 红外检测到物体时，在默认姿势上再略抬头；不是角度值。
# 新增的 20000ns 尚需检查安装间隙后实测，不能靠软件判断机械是否卡住。
TILT_NEAR_EXTRA_NS = 20000
TILT_NEAR_NS = TILT_HOME_NS - TILT_DIRECTION * TILT_NEAR_EXTRA_NS
TILT_MIN_NS = min(TILT_DOWN_NS, TILT_UP_NS, TILT_NEAR_NS)
TILT_MAX_NS = max(TILT_DOWN_NS, TILT_UP_NS, TILT_NEAR_NS)

STEP_INTERVAL_MS = 20        # 大约每 20 毫秒走一小步。
STEP_NS = 4000              # 每步最多改变 4000 纳秒；含柔和起停时耗时更长。
RAMP_STEP_NS = 1000         # 每次更新最多增加的步幅，减少突然起动。
INPUT_STABLE_MS = 60         # 输入持续 60 毫秒才承认，减少边缘检测时来回抖动。
RETURN_DELAY_MS = 400        # 手短暂离开检测区时先等一下，再回中。
TOUCH_ACTIVE_LEVEL = 1       # 已确认 TTP223：摸到是 1，松开是 0。
TOUCH_HOLD_MS = 1000         # 轻触后继续低头/显示表情 1 秒，避免短按动作看不清。
# 屏幕只绘制表情；输入电平和运行模式仍通过 USB 回传，不占用屏幕。

# 供电沿用已经接好的方式，不需要重新接线：
# 两只舵机红线 -> 电源板绿色 5V；棕/黑线 -> 黑色 GND。
# ESP32 的 G -> 同一电源板黑色 GND，保证信号有共同的电压参考。
# 屏幕/触摸/红外 VCC -> 黄色 3.3V；各自 GND -> 黑色 GND。
# OLED SDA -> GPIO0，SCL -> GPIO1；红色 VIN 是原始 12V，不能接模块。
# 调试时 ESP32 用 USB 供电，其 5V、3.3 引脚不接外部电源输出。



# OLED I2C 配置
OLED_SDA_PIN = 0
OLED_SCL_PIN = 1
OLED_FREQ = 100000
OLED_ADDRESS = 0x3C

# ROS2 无按钮切换：仅有效命令续期；断线先回中，再恢复独立互动。
REMOTE_TIMEOUT_MS = 1000
TELEMETRY_INTERVAL_MS = 100
