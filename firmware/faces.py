"""SSD1306 表情绘制，不负责初始化屏幕。"""

def rounded_eye(oled, x, y, width, height, radius=8):
    """逐行画圆角眼睛；眼睛形状与前面的 oled_face.py 一致。"""
    radius = min(radius, width // 2, height // 2)
    for row in range(height):
        inset = 0
        if radius > 1:
            if row < radius:
                dy = radius - 1 - row
                inset = radius - 1 - int(((radius - 1) ** 2 - dy ** 2) ** 0.5)
            elif row >= height - radius:
                dy = row - (height - radius)
                inset = radius - 1 - int(((radius - 1) ** 2 - dy ** 2) ** 0.5)
        oled.hline(x + inset, y + row, width - 2 * inset, 1)



def thick_line(oled, points, thickness=2):
    """沿几个坐标连接线段，组成嘴巴或其他线条。"""
    for offset in range(thickness):
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            oled.line(x1, y1 + offset, x2, y2 + offset, 1)



def draw_touch_face(oled):
    """触摸表情：平上沿、圆下沿的半垂眼睛，加一张小撇嘴。"""
    for x in (31, 75):
        # 眼睛上半部是平顶矩形，下半部是半圆。
        for row in range(9):
            oled.hline(x, 21 + row, 22, 1)
        for row in range(11):
            inset = 10 - int((100 - row * row) ** 0.5)
            oled.hline(x + inset, 30 + row, 22 - 2 * inset, 1)

    # 中间高、两端低，形成图片中的小撇嘴。
    mouth = ((58, 40), (59, 38), (61, 37), (63, 36),
             (65, 36), (67, 37), (69, 38), (70, 40))
    thick_line(oled, mouth, 3)



def filled_oval(oled, center_x, center_y, radius_x, radius_y, color):
    """逐行填充椭圆；1 点亮，0 擦黑。"""
    for dy in range(-radius_y, radius_y + 1):
        half_width = int(radius_x * (1 - (dy / (radius_y + 0.5)) ** 2) ** 0.5 + 0.5)
        oled.hline(center_x - half_width, center_y + dy,
                   half_width * 2 + 1, color)



def draw_near_face(oled):
    """靠近表情：带小亮点的椭圆眼睛，加弯弯的笑嘴。"""
    for center_x in (40, 88):
        # 先画白色大椭圆，再擦黑中间，留下白色眼圈。
        filled_oval(oled, center_x, 29, 11, 14, 1)
        filled_oval(oled, center_x, 29, 7, 10, 0)
        # 左上角添一个白色亮点。
        filled_oval(oled, center_x - 5, 22, 3, 3, 1)

    mouth = ((57, 41), (59, 44), (62, 45),
             (66, 45), (69, 44), (71, 41))
    thick_line(oled, mouth, 3)



def draw_face(oled, expression):
    """屏幕只显示表情；调试电平和模式留在 USB 串口。"""
    oled.fill(0)
    if expression == "touched":
        draw_touch_face(oled)
    elif expression == "near":
        draw_near_face(oled)
    else:
        height = 2 if expression == "closed" else 32
        y = 29 - height // 2
        rounded_eye(oled, 28, y, 24, height)
        rounded_eye(oled, 76, y, 24, height)
        mouth = ((55, 48), (59, 50), (64, 51), (69, 50), (73, 48))
        thick_line(oled, mouth)
    oled.show()
