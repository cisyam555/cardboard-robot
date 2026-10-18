# ROS2 展示与讲解：从输入到转头指令

目标是展示你理解并能操作 ROS2 的节点、话题、服务、参数和 Launch。先使用模拟演示，熟悉后换实物；模拟阶段关注消息与状态，实物阶段观察相同链路如何驱动头部和表情。

## 展示前

按 README 构建。准备两个终端，均进入仓库根目录并执行 `source tools/ros2_env.bash`。每个场景结束再推进下一步，避免一口气复制全部命令。

终端 A：

```bash
ros2 launch cardboard_robot sim.launch.py
```

后续检查在终端 B；终端 A 用来观察节点日志。以下模拟参数只在模拟入口下生效。

## 场景一：证明有两个分工明确的节点

```bash
ros2 node list
ros2 node info /hardware_bridge
ros2 topic list -t
```

可讲：

> 我把硬件接入与行为决策拆成两个 ROS2 节点。桥接节点负责数据转换和串口，决策节点通过话题接收传感器信息、输出动作。这样可以先模拟再接实物，决策代码共用。

如果已安装 `rqt_graph`，在另一个加载相同环境的终端运行它，展示 `/robot/sensors` 和 `/robot/action` 连接两个节点的关系。CLI 检查也能展示相同接口。

## 场景二：区分“服务接受请求”和“实际模式”

```bash
ros2 topic echo /robot/mode std_msgs/msg/String --once
ros2 service type /robot/set_ros2
ros2 service call /robot/set_ros2 std_srvs/srv/SetBool '{data: true}'
ros2 topic echo /robot/mode std_msgs/msg/String --once
```

预期：初始 `standalone`，服务成功后模式为 `ros2`。

可讲：

> 这里用服务实现一次请求与响应，用话题持续广播当前状态。服务成功代表请求被接受，模式话题才是状态确认。接管服务和状态观察各有职责。

## 场景三：展示感知到决策的消息链路

```bash
ros2 param set /hardware_bridge sim_left true
ros2 topic echo /robot/sensors std_msgs/msg/String --once
ros2 topic echo /robot/action std_msgs/msg/String --once
```

预期快照中 `left` 为 `true`，动作变为 `look_left`；终端 A 可看到 `SIM action: look_left`。若恰好读到更新前样本，再读一次。

可讲：

> 我通过节点参数模拟左侧有物体。桥接发布完整传感器快照，决策节点的订阅回调保存它，再由定时器生成左转动作。桥接订阅动作后转换成设备指令。

## 场景四：展示规则优先级

保持左侧输入，增加触摸：

```bash
ros2 param set /hardware_bridge sim_touch true
ros2 topic echo /robot/action std_msgs/msg/String --once
```

预期为 `bow`。可讲：

> 这是基于规则的决策，触摸优先于左右红外，所以两个输入同时存在时选择低头。传感器接入和优先级规则分别放在不同模块，规则也有电脑端测试。

复原输入：

```bash
ros2 param set /hardware_bridge sim_touch false
ros2 param set /hardware_bridge sim_left false
```

等待原来的 0.4 秒返回延时后，动作应恢复为 `idle`。

## 场景五：展示参数与定时器

```bash
ros2 param get /behavior_controller return_delay_ms
ros2 param set /behavior_controller return_delay_ms 1000
ros2 topic hz /robot/action
```

查看频率后按 Ctrl+C，停止查看不会停止启动终端里的节点。

可讲：

> 节点用 Timer 周期工作：决策约 20Hz，桥接约 10Hz。我可以运行时把物体消失后的等待时间改为 1 秒，不用改源码或重启节点。实际话题频率会受电脑负载影响。

可再次把左输入设为 `true`，随后设回 `false`，持续查看动作话题，观察返回 `idle` 的等待时间。

## 场景六：展示退出和异常回退设计

```bash
ros2 service call /robot/set_ros2 std_srvs/srv/SetBool '{data: false}'
ros2 topic echo /robot/mode std_msgs/msg/String --once
```

预期模式为 `standalone`。

可讲：

> 系统保留 ESP32 独立模式。主动退出会回到独立控制；传感器或决策消息长期不更新时，也会取消 ROS2 接管。自动集成测试会单独停止决策节点，验证这个回退逻辑。

要展示自动回退检查，在不与演示冲突的独立通信域执行：

```bash
ROS_DOMAIN_ID=85 python3 tools/check_ros2.py
```

它会自行启动和清理测试进程，不需要手工结束某个不确定 PID。

## 场景七：说明 Launch 不是单纯“运行脚本”

先在终端 A 按 Ctrl+C 停止原启动，再运行：

```bash
ros2 launch cardboard_robot sim.launch.py sim_left:=true return_delay_ms:=800
```

终端 B 检查：

```bash
ros2 param get /hardware_bridge sim_left
ros2 param get /behavior_controller return_delay_ms
```

预期分别为 `true` 和 `800`。可讲：

> Launch 同时组织两个节点、传递参数和设置日志。我用模拟和实物两个入口复用统一启动文件；启动参数经过类型转换后成为节点参数。后续运行时参数修改是另外一条机制。

## 换实物展示

先停止模拟。关闭 Thonny，按硬件指南完成供电和 USB 数据连接：

```bash
ros2 launch cardboard_robot hardware.launch.py port:=/dev/ttyACM0
```

等传感器数据出现后，再调用接管服务。通过遮挡左、右红外与真实触摸展示动作，使用 `/robot/sensors`、`/robot/action`、`/robot/mode` 说明每一层发生了什么。实物入口不使用模拟输入。

可以这样介绍整个项目：

> 我用一个双舵机纸壳机器人实践 ROS2 的感知、决策和执行流程。电脑端使用两个 Python 节点，通过话题交换传感器与动作，通过服务切换控制模式，用参数调整行为，用 Launch 组织程序。ESP32 负责传感器、舵机和平滑动作，通过 USB 协议接入。展示重点是节点协作和可观察的控制流程。

SG90 没有真实角度反馈；协议模拟不验证机械状态，实物测试也应如实区分命令值与观察到的动作。
