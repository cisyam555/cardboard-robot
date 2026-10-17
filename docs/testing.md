# 模块测试顺序

这些是开发板上的人工硬件测试，与 `tests/` 中电脑自动测试不同。每次只运行一个脚本；OLED 相关脚本需先把 `firmware/ssd1306.py` 上传到设备根目录。例子中的引脚和参数各自独立，不读取正式程序的 config.py。

| 顺序 | 目录 / 入口 | 检查内容 |
| --- | --- | --- |
| 1 | `examples/02_OLED/oled_contact.py` | 连续扫描通常应稳定看到十进制 60 |
| 2 | `examples/02_OLED/oled_hello.py` | 显示 Hello Robot! |
| 3 | `examples/02_OLED/oled_eyes.py`、`oled_blink.py`、`oled_face.py` | 双眼、眨眼、圆角表情 |
| 排错 | `oled_test.py`、`oled_check.py`、`oled_fix.py` | 软件 I2C 显示、硬件 I2C 排错、尝试不同频率 |
| 4 | `examples/03_红外/ir_test.py` | 检测到物体通常为 0，移开为 1；两块分别测试 |
| 5 | `examples/04_舵机/servo_test.py` | GPIO5 空载回中及小幅运动 |
| 6 | `examples/05_触摸表情/touch_face.py` | 触摸变化切换表情 |
| 7 | `examples/06_触摸红外表情/touch_ir_face.py` | 触摸、红外共同控制表情 |
| 8 | `examples/07_表情舵机联动/robot_one_servo.py` | 单舵机和表情联动 |
| 9 | `examples/08_双舵机联动/robot_two_servos.py` | 双舵机联动 |
| 10 | `examples/09_双红外左右联动/robot_left_right.py` | 左右红外方向对应 |
| 安装前 | `examples/10_机械组装/servo_center.py` | 两舵机依次回中，断电后装舵盘 |
| 11 | `examples/11_视频转头/robot_video_turn.py` | 单文件 demo / interaction，平滑运动 |
| 12 | `firmware/main.py` 及所有模块 | 当前正式模块版本 |

触摸输入没有单独的旧测试脚本，可在第 6 步验证其输出。旧例子可能包含阻塞等待、不同保持策略；正式程序的行为以 README 为准。

建议记录：固件版本、供电电压、模块型号、每个脚本的现象、报错和方向校准结果。当前没有对拆分后的程序进行实物测试，不把电脑测试通过作为硬件验收。
