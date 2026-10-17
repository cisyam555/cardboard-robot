# 小纸壳机器人 · Cardboard Robot

基于 **ESP32-C3 SuperMini + MicroPython** 的桌面互动机器人。使用 OLED 表情、双红外检测、触摸输入和两只 SG90 舵机，实现平滑转头与摸头低头。

本项目记录从单模块测试到完整联动的开发过程。正式程序由最新学习版本拆分而来，默认使用小幅动作演示模式；尚未在实物上验证拆分后的版本。

## 项目结构

```text
firmware/                  正式程序：上传其中所有 .py 到开发板根目录
  main.py                  上电入口
  config.py                引脚、模式、动作幅度和速度
  app.py                   演示、互动循环及退出清理
  servo.py                 舵机 PWM 与平滑步进
  sensors.py               传感器输入消抖
  behavior.py              触摸与红外的动作优先级
  faces.py                 OLED 表情绘制
  ssd1306.py               MicroPython 官方 OLED 驱动
examples/                  全部现有独立测试和学习脚本
  02_OLED/                 显示、眨眼、表情、接线排错
  03_红外/                 单红外输入测试
  04_舵机/                 单舵机小幅测试
  05_触摸表情/             触摸与 OLED 联动
  06_触摸红外表情/         触摸、红外、OLED 联动
  07_表情舵机联动/         单舵机联动
  08_双舵机联动/           双舵机联动
  09_双红外左右联动/       左右红外方向控制
  10_机械组装/             安装前舵机回中
  11_视频转头/             正式程序拆分前的完整学习版本
tests/                    电脑端逻辑测试，无需连接硬件
tools/check_syntax.py     全部 Python 源码语法检查
docs/                     接线、模块测试、运行、上传说明
```

## 硬件与接线

| 模块 | 信号引脚 | 供电 |
| --- | --- | --- |
| SSD1306 OLED 128×64，地址 0x3C | SDA GPIO0；SCL GPIO1 | 3.3V |
| 左红外（面对机器人时的左侧） | OUT GPIO4 | 3.3V |
| 右红外 | OUT GPIO3 | 3.3V |
| 触摸模块 | SIG GPIO10 | 3.3V |
| 水平 SG90 | GPIO5 | 外部稳压 5V |
| 俯仰 SG90 | GPIO6 | 外部稳压 5V |

所有 GND 共地。调试时开发板用 USB 供电，外部 5V 不同时连接开发板 5V；外部电源的 VIN 不能直接给模块供电。改线、装舵盘前断开外部电源和 USB。详见 [接线说明](docs/wiring.md)。

## 快速运行

1. 在 ESP32-C3 上安装 MicroPython。固件请从 [MicroPython 官方下载页](https://micropython.org/download/ESP32_GENERIC_C3/) 获取；本仓库不附带固件二进制。
2. 用 Thonny 选择 MicroPython (ESP32) 和开发板串口。
3. 先单独运行 `examples/` 内的测试。使用 OLED 的例子均需先将 `firmware/ssd1306.py` 保存到开发板根目录。
4. 测试通过后，将 `firmware/` 内的 **全部 8 个 .py 文件** 平铺保存到开发板根目录，不是只复制 `main.py`。
5. `config.py` 默认 `MODE = "demo"`：两只舵机依次回中，执行一次小幅演示，随后保持中位。先空载测试。
6. 验证方向后，停止程序，把开发板上的 `config.py` 改为 `MODE = "interaction"`，重启开发板。

互动模式：左红外触发转左，右红外触发转右，同时触发回中；手移开约 0.4 秒后回中；摸头优先回中并低头。空闲时屏幕眨眼。左右反了改 `PAN_DIRECTION`；低头方向反了改 `TILT_DIRECTION`。

`main.py` 保存到设备后会在重启时自动运行。第一次调试可暂不保存它，上传其余文件后，在 Thonny 打开电脑上的 `firmware/main.py` 按 F5。修改配置或模块后重启，避免使用导入缓存。

动作范围默认 1.4～1.6ms，50Hz PWM。脉宽不等于角度，SG90 没有位置反馈。停止程序后会释放舵机，应先扶住头壳。扩大范围前需要机械校准。

## 测试与开发

电脑端使用 Python 3，无需安装第三方依赖：

```bash
python3 tools/check_syntax.py
python3 -m unittest discover -s tests -v
```

GitHub Actions 会自动执行以上检查。电脑测试覆盖控制优先级、消抖、平滑限幅及异常清理；不代表串口、供电、OLED 或机械实测通过。`machine`、`framebuf`、`micropython` 是开发板提供的模块，不能用普通电脑 Python 直接执行正式固件。

- [模块测试顺序](docs/testing.md)
- [GitHub 上传说明](docs/github.md)
- [文件来源与第三方驱动许可](THIRD_PARTY_NOTICES.md)

## 收录范围

收录当前自行编写的全部 17 个测试和学习脚本，并保留历史版本便于比较。旧脚本各自独立运行，不作为正式程序的依赖。历史说明中的“本目录”“资料包”等按原学习环境理解，以本 README 和 docs 为当前使用依据。

购买资料包标注禁止转载，因此原版网页测试工具、私有固件、购买资料及未核实来源的插图不在此仓库中。原目录文件保持原样。SSD1306 驱动独立遵循其上游许可。本项目自编代码暂未指定开源许可证，后续由维护者选择。
