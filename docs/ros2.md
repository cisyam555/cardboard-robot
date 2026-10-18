# ROS2 运行与源码说明

项目主页展示整体架构和快速演示；本文解释启动入口、节点接口、控制时序与排错。现场讲解可以按 [演示流程](ros2_demo.md) 操作，硬件下载见 [硬件指南](hardware.md)。

## 1. 环境与构建

开发环境为 Ubuntu 24.04、ROS2 Jazzy、Python 3。电脑运行 `rclpy` 节点，ESP32 运行 MicroPython；设备通过 USB JSON 行协议接入。

在仓库根目录：

```bash
source /opt/ros/jazzy/setup.bash
cd ros2_ws
colcon build --symlink-install --packages-select cardboard_robot
cd ..
source tools/ros2_env.bash
```

每个终端先进入同一仓库，再 `source tools/ros2_env.bash`。该脚本加载已安装工作空间、移除旧的 `ROS_LOCALHOST_ONLY`，使用 `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` 和默认通信域 74，仅影响当前终端。

需要与另一个本机项目分开时，可以在所有相关终端先设置相同的 `CARDBOARD_ROS_DOMAIN_ID`，再 source。通信域用于发现分组，不是安全隔离或权限控制。学习默认仅在本机发现；跨电脑通信需要另外配置。

## 2. 三个启动入口

先停止旧的一组节点，再执行新的启动命令。同一通信域中不要同时启动模拟与实物入口。

```bash
# 模拟：只启动软件链路，不打开真实串口。
ros2 launch cardboard_robot sim.launch.py

# 实物：串口按实际设备选择。
ros2 launch cardboard_robot hardware.launch.py port:=/dev/ttyACM0

# 兼容旧命令的统一入口，默认 simulate=false。
ros2 launch cardboard_robot robot.launch.py simulate:=true
```

`sim.launch.py` 和 `hardware.launch.py` 使用 `IncludeLaunchDescription` 复用 `robot.launch.py`。统一入口使用 `DeclareLaunchArgument` 声明配置、`LaunchConfiguration` 获取值，再通过 `Node(parameters=...)` 传给节点。

```bash
ros2 launch cardboard_robot sim.launch.py --show-args
ros2 launch cardboard_robot sim.launch.py sim_left:=true return_delay_ms:=800 log_level:=info
```

`ParameterValue` 显式转换布尔值和整数。单独传入的串口路径保持字符串，支持含空格的文件系统路径。日志级别传给 ROS 日志系统。

### 启动参数与节点参数

| 配置 | 启动参数 | 节点参数 | 运行时修改 |
| --- | --- | --- | --- |
| 模拟 / 实物 | `simulate`；专用入口固定选择 | `/hardware_bridge simulate` | 修改后需重新启动 |
| 串口 | `port`、`baud` | `/hardware_bridge port/baud` | 需重新启动 |
| 模拟输入 | `sim_left/right/touch` | `/hardware_bridge sim_left/right/touch` | 支持 |
| 返回等待 | `return_delay_ms` | `/behavior_controller return_delay_ms` | 支持 |
| 输入过期 | `sensor_timeout_ms` | `/behavior_controller sensor_timeout_ms` | 支持 |
| 日志级别 | `log_level` | ROS 日志配置 | 本项目不提供此项的动态节点参数 |

`ros2 param set` 能改变某个已声明值，不代表业务代码一定立即重新配置资源。串口与模拟选择在节点启动时读取，因此修改它们仍需重新启动。返回等待与模拟输入在定时器循环中读取，可以立即用于后续决策。

## 3. 节点与话题

### hardware_bridge

- 读取串口，或生成模拟输入；校验收到的快照。
- 发布 `/robot/sensors` 及单独的触摸、左右红外话题。
- 订阅 `/robot/action`，把动作编码为 USB 命令。
- 提供 `/robot/set_ros2` 服务，发布模式和连接状态。
- 每约 100ms 执行一次，检查传感器和动作的新鲜度。

### behavior_controller

- 订阅同次采样的 `/robot/sensors` 完整快照。
- 每约 50ms 根据规则发布 `/robot/action`。
- 触摸优先；双红外选择 `look_center`；物体离开后等待 `return_delay_ms` 再返回。
- 输入超过 `sensor_timeout_ms` 没有更新时停止发布动作，让桥接检测到过期并退出接管。

| 话题 | 消息类型 | 内容 |
| --- | --- | --- |
| `/robot/sensors` | `std_msgs/msg/String` | JSON：`v/touch/left/right/mode`；实物可带 raw 和脉宽字段 |
| `/robot/touch` | `std_msgs/msg/Bool` | 是否触摸 |
| `/robot/ir/left`、`/robot/ir/right` | `std_msgs/msg/Bool` | 是否检测到物体，不是距离 |
| `/robot/action` | `std_msgs/msg/String` | `idle/look_left/look_right/look_center/bow` |
| `/robot/mode` | `std_msgs/msg/String` | `standalone/centering/ros2/disconnected` |
| `/robot/connected` | `std_msgs/msg/Bool` | 最近 0.5 秒内是否收到有效数据 |

话题使用深度 1 的默认可靠、易失 QoS，意图是及时处理最新状态。模式持续发布，正常情况下新订阅者也会收到后续样本；没有输出时应检查节点、通信域和发现设置，不要直接认定“只发布了一次”。

```bash
ros2 node info /hardware_bridge
ros2 topic info /robot/sensors --verbose
ros2 topic echo /robot/sensors std_msgs/msg/String --once
ros2 topic hz /robot/action
```

## 4. 服务与模式切换

```bash
ros2 service call /robot/set_ros2 std_srvs/srv/SetBool '{data: true}'
ros2 topic echo /robot/mode std_msgs/msg/String --once
```

请求 `true` 表示接管，`false` 表示退出。服务成功只代表请求被接受；以模式话题确认。

实物状态机：

```text
standalone -> centering -> ros2
ros2 -> centering -> standalone
```

`centering` 期间先回默认姿势，动作指令到位后交接。协议模拟器只切换协议状态，不计算机械运动时间，因此可直接看到 `ros2` 或 `standalone`。这个状态机是应用逻辑，不是 ROS2 Lifecycle 节点。

接管要求桥接有新鲜的传感器与决策数据；不满足会返回失败原因。桥接约 0.5 秒收不到新鲜输入/动作时取消接管；固件约 1 秒收不到有效命令时也会退出。重新连接或决策恢复后需重新请求接管。

## 5. 模拟输入与动态参数

```bash
ros2 param set /hardware_bridge sim_left true
ros2 param set /hardware_bridge sim_touch true
ros2 topic echo /robot/action std_msgs/msg/String --once
```

左输入存在时输出 `look_left`；再加入触摸后应输出 `bow`。参数更新与消息传播是异步的，偶尔读到更新前的样本时，稍后再读取。

```bash
ros2 param set /hardware_bridge sim_touch false
ros2 param set /hardware_bridge sim_left false
ros2 param set /behavior_controller return_delay_ms 1000
ros2 param get /behavior_controller return_delay_ms
```

延时参数只改变 ROS2 决策模式的返回等待；ESP32 独立模式仍使用其 `firmware/config.py` 设置。模拟参数不会替换真实机器人上的传感器输入。

## 6. USB 协议与实物

先确认 ESP32 根目录保存全部 9 个正式文件，独立互动正常；关闭 Thonny并停止模拟后接入电脑。

```bash
ls /dev/serial/by-id/
ros2 launch cardboard_robot hardware.launch.py port:=/dev/ttyACM0
```

优先选稳定的 by-id 路径。串口权限不足时配置用户设备权限，不用 `sudo ros2` 绕过。GPIO 与供电见 [接线说明](wiring.md)。USB 接电脑时不同时从外部给 ESP32 USB 接口或供电排针再送电；舵机继续用原稳压电源并共地。

设备上行是以 `@` 开头的 JSON 行；桥接发给设备的命令示例：

```json
{"v": 1, "mode": "ros2", "action": "look_left"}
```

设备遥测中的触摸和左右状态必须是布尔值。解析器限制行长度，校验版本、模式和字段类型。桥接使用接收端单调时钟判断消息是否过期，不依赖两端系统时间同步。本版没有设备时间戳或序列号，不要把历史传感器日志回放到真实控制链路当作新输入。

ESP32 的 USB REPL 与运行通信共用串口，不能同时打开 Thonny、监视器和桥接。ROS2 不会上传固件；更新设备代码时先停止桥接，再用 Thonny 操作。Ctrl+C 正常关闭桥接会尽力发送退出命令，突然断开则由固件超时处理。

## 7. 排查话题没有输出

1. 确认启动终端还在运行，且无启动异常。
2. 各终端 source 同一个 `tools/ros2_env.bash`，确认 `echo "$ROS_DOMAIN_ID"` 一致。
3. 用 `ros2 node list` 查看两个节点，再用 `ros2 topic list -t` 查看话题。
4. 用明确类型读取：`ros2 topic echo /robot/mode std_msgs/msg/String --once`。
5. 若新订阅者仍发现不到节点，停止这组模拟，用统一环境重新启动；不要同时保留旧的多组节点。

`ROS_LOCALHOST_ONLY` 在 Jazzy 中属于旧设置；本项目学习脚本使用新的发现范围设置。此前观测到原节点运行但新订阅者发现不到的现象，没有据此确认唯一根因。统一环境在独立通信域中的模拟集成检查已通过。

## 8. 代码阅读与测试

阅读顺序：`launch/robot.launch.py` → `bridge.py` → `behavior.py` → `core.py` → `firmware/remote.py`。先理解节点的输入输出，再看串口编码和状态交接。

```bash
python3 tools/check_syntax.py
python3 -m unittest discover -s tests -v
source tools/ros2_env.bash
ROS_DOMAIN_ID=84 python3 tools/check_launch.py
ROS_DOMAIN_ID=85 python3 tools/check_ros2.py
ROS_DOMAIN_ID=86 python3 tools/check_ros2.py --serial
```

最后三项运行真实 ROS2 进程并自动清理测试节点。`check_launch.py` 验证启动入口、参数与互动流程；`check_ros2.py` 验证模式及停止决策后的回退；`--serial` 用伪终端串口运行固件解析器和模式状态机，不操作真实 GPIO、OLED 或舵机。结果应与真实硬件验证分别记录。
