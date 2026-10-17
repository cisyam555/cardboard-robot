# ROS2 无按钮双模式：运行与演示

## 系统和学习目标

ESP32-C3 运行 MicroPython，负责输入消抖、舵机 PWM、限幅和平滑运动、OLED。
Ubuntu 24.04 + ROS2 Jazzy 运行两个 Python 节点：

```text
触摸/左右红外 → ESP32 → USB JSON 行 → hardware_bridge
                                     ↓ /robot/sensors
                               behavior_controller
                                     ↓ /robot/action
舵机/OLED ← ESP32 ← USB JSON 行 ← hardware_bridge
```

这是基于规则的具身交互原型，没有模型训练、人脸识别、导航或关节角度反馈。
SG90 的指令脉宽不是测量角度。模拟模式仅验证消息链路，不模拟机械运动。

## 1. 更新开发板（只需首次或改固件时）

1. 先卸下头壳或确认动作空间，断电改线；原有接线不变，无需按钮。
2. 用 Thonny 把 `firmware/` 中全部 **9 个 .py 文件**上传到开发板根目录。
3. `config.py` 默认 `MODE = "standalone"`。第一次空载检查可先用 `"demo"`；
   确认方向后再改回 `"standalone"`。`"interaction"` 是独立互动的兼容名称。
4. 重启后默认独立互动，OLED 左上角 `LOCAL`。不接电脑、只供电也可使用。
5. 使用 ROS2 前关闭 Thonny，释放串口。ROS2 不会自动上传固件。

USB 使用 MicroPython 的 `sys.stdin/sys.stdout`（REPL 同一串口）。仅适用于该固件
将 REPL 暴露在当前 USB 串口的配置，实际板型仍需验证。不要同时打开串口监视器、
Thonny 和 ROS2 桥接。程序保留 Ctrl+C 中断能力；上传更新前先停止 ROS2，再用
Thonny 的停止按钮中断。如果 `main.py` 自动启动，连接后先停止，再修改文件。

如果上电回中后没有 `LOCAL`，先检查屏幕/传感器连接和报错，不要直接切 ROS2。
若该 MicroPython 固件没有可轮询的 USB REPL，需要改用其支持的串口驱动；
不要在不核对空闲引脚的情况下增加 UART 接线。

## 2. 构建电脑端 ROS2 功能包

在项目根目录打开终端。以下命令中 `$PWD` 表示当前项目目录：

```bash
source /opt/ros/jazzy/setup.bash
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
```

依赖：`rclpy`、`std_msgs`、`std_srvs`、`launch_ros`、`python3-serial`、colcon。
如果缺少依赖，Ubuntu 中安装对应 Jazzy 包和 `python3-serial`。
当前开发电脑已具备这些依赖。

后面每个新终端都先执行下面两行（路径按实际克隆位置调整）：

```bash
source /opt/ros/jazzy/setup.bash
source ~/桌面/纸壳机器人/cardboard-robot/ros2_ws/install/setup.bash
```

## 3. 没接机器人，也能先学 ROS2

终端 A 启动协议模拟：

```bash
ros2 launch cardboard_robot robot.launch.py simulate:=true
```

终端 B 请求 ROS2 接管：

```bash
ros2 service call /robot/set_ros2 std_srvs/srv/SetBool '{data: true}'
```

成功应答代表已接受请求；看 `/robot/mode` 确认状态，而不是仅看服务结果。

```bash
ros2 topic echo /robot/mode
```

终端 C 模拟手出现在左侧，然后模拟摸头：

```bash
ros2 param set /hardware_bridge sim_left true
ros2 param set /hardware_bridge sim_touch true
```

桥接日志依次显示 `SIM action: look_left`、`SIM action: bow`。
取消触摸后会回到左转；两个输入都取消，约 0.4 秒后回中：

```bash
ros2 param set /hardware_bridge sim_touch false
ros2 param set /hardware_bridge sim_left false
```

模拟模式不连接 ESP32，也不会让真实舵机移动。停止模拟后才能启动真实连接；
一次只运行一组桥接/决策节点。

## 4. 连接真实机器人并切换

确认固件已更新、USB 连接、Thonny 已关闭，查看设备：

```bash
ls /dev/serial/by-id/
```

优先使用稳定的 `/dev/serial/by-id/...` 路径；没有时按实际选择 `/dev/ttyACM0`
或 `/dev/ttyUSB0`。下面的设备名是例子，不保证每台电脑一致：

```bash
ros2 launch cardboard_robot robot.launch.py port:=/dev/ttyACM0
```

启动桥接本身仍为独立模式，不会自动接管。等待传感器数据：

```bash
ros2 topic echo /robot/sensors
```

然后在另一终端切换：

```bash
# 进入 ROS2 控制：屏幕先 WAIT 回中，再 ROS2
ros2 service call /robot/set_ros2 std_srvs/srv/SetBool '{data: true}'

# 回到独立互动：屏幕先 WAIT 回中，再 LOCAL
ros2 service call /robot/set_ros2 std_srvs/srv/SetBool '{data: false}'
```

没有新鲜的传感器数据或决策消息时，接管请求会被拒绝并说明原因。
桥接端 0.5 秒没有新鲜输入/动作就取消接管；固件 1 秒没有有效命令也会
退出 ROS2。退出先平滑回中，再恢复独立互动。这个回中过程可能约需 0.5 秒，
实际受循环执行时间影响；回中判定基于指令值，并非真实角度测量。
重新连接或决策恢复后需要再次显式请求接管，不会自动重入。
Ctrl+C 停止桥接时会尽力发送退出命令；强制断开由开发板超时处理。

`/robot/connected` 表示近期是否收到有效开发板消息；USB 插着但程序未运行不算连接。
串口权限不足时需由用户配置设备权限（通常是 dialout 组并重新登录），不要用
`sudo ros2` 绕过，也不要在两个程序中同时打开串口。

## 5. 话题、服务和参数

| 接口 | 类型 | 用途 |
| --- | --- | --- |
| `/robot/sensors` | std_msgs/String | 同次采样的 JSON：v、touch、left、right、mode |
| `/robot/touch` | std_msgs/Bool | 触摸状态 |
| `/robot/ir/left`、`/robot/ir/right` | std_msgs/Bool | 红外有无检测，不是距离 |
| `/robot/action` | std_msgs/String | idle/look_left/look_right/look_center/bow |
| `/robot/mode` | std_msgs/String | standalone/centering/ros2；桥接失联时为 disconnected |
| `/robot/connected` | std_msgs/Bool | 开发板消息是否新鲜 |
| `/robot/set_ros2` | std_srvs/SetBool | true 请求接管，false 请求独立模式 |

决策节点使用完整快照话题，避免左右状态分开到达造成同次采样混淆。
使用接收端单调时钟检测新鲜度，无需电脑与 ESP32 时钟同步。v=1 是协议版本。
本版没有设备时间戳与序列号；日志回放可用于观察和离线分析，不应连接真实桥接
当作实时传感器源，否则旧记录会被视为新接收的数据。

```bash
ros2 node list
ros2 topic echo /robot/action
ros2 topic hz /robot/sensors
ros2 param set /behavior_controller return_delay_ms 600
rqt_graph
```

决策默认每 50ms 发布一次；传感器和桥接命令每 100ms 一次。
`return_delay_ms` 控制目标消失后延迟回中，默认为 400。
`sim_touch/sim_left/sim_right` 仅在模拟模式下生效。

## 6. 对照源码学习

1. `bridge.py`：Node、publisher/subscriber、SetBool 服务、串口、连接状态和超时。
2. `behavior.py`：订阅回调保存快照，timer 周期决策，参数控制回中延迟。
3. `core.py`：纯函数协议检查和行为规则；触摸优先，双红外同时触发朝中间。
4. `robot.launch.py`：一条命令启动两个节点，传入设备或模拟参数。
5. `firmware/remote.py`：有界串口解析、接管与回中状态机、命令超时。
6. `firmware/app.py`：共享原有传感器和执行器，两种模式只改变动作来源。

可以这样讲解演示：

> 机器人默认由 ESP32 独立互动。ROS2 通过服务请求接管，桥接节点发布真实
> 传感器快照，决策节点订阅后周期发布动作，再由桥接送给 ESP32 执行。
> 两种模式共用底层驱动，切换先回中，通信超时会回到独立模式。
> 这实现了基于规则的感知—决策—行动循环，未实现视觉学习或关节位置反馈。

## 7. 检查与验证边界

项目根目录运行普通 Python 检查：

```bash
python3 tools/check_syntax.py
python3 -m unittest discover -s tests -v
```

构建并 source ROS2 工作空间后，在无其他同名节点的环境运行真实 DDS 集成检查：

```bash
ROS_DOMAIN_ID=74 python3 tools/check_ros2.py
# 用操作系统伪终端连接真实固件解析器/状态机，验证 pyserial 链路
ROS_DOMAIN_ID=74 python3 tools/check_ros2.py --serial
```

检查两个独立 ROS2 进程的传感器、动作、切换服务、触摸优先和决策停止后回退。
另有模式状态机测试覆盖回中等待、计数回绕、无效命令不续期和输入长度限制。
本次开发没有连接 ESP32：USB 固件兼容、OLED、供电和机械动作仍需实物验证。
