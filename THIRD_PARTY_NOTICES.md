# 文件来源与第三方许可

## SSD1306 驱动

- 文件：`firmware/ssd1306.py`
- 来源：MicroPython 官方 micropython-lib
- 上游：https://github.com/micropython/micropython-lib/blob/master/micropython/drivers/display/ssd1306/ssd1306.py
- 本地来源记录：原 `学习代码/02_OLED/说明.txt`；复制时保留原文件内容。
- 上游 LICENSE 表示未单独声明的文件采用 MIT；该模块 manifest 未单独指定其他许可证。
- 完整上游许可及版权声明保存在 [docs/micropython-lib-LICENSE.txt](docs/micropython-lib-LICENSE.txt)。该文件含上游其他模块所用许可，不表示本仓库使用了所有这些模块。

## 项目代码

`examples/` 收录原学习目录中的自行编写脚本；`firmware/` 由 `examples/11_视频转头/robot_video_turn.py` 按职责拆分，保留原控制逻辑。示例中的 `ssd1306` 导入统一使用正式目录下的驱动。正式程序仅依赖 MicroPython 内置模块与此驱动。

没有收录标注“仅限购买者个人使用，请勿转发转载”的原资料包及其解压副本、测试工具、原版编译固件、裁切模板、图片。仓库中的历史文字说明可能提及这些材料，不代表仓库提供它们。

除上述第三方驱动外，自编代码暂未授予统一开源许可证；GitHub 公开可见与授予开源许可是不同事项。许可证由维护者后续决定。
