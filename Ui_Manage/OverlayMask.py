import sys
import logging
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont, QPen

from Ui_Manage.WindowManager import WinControl
from config_manager import config_manager

# 配置日志
logger = logging.getLogger(__name__)

class OverlayMask(QWidget):
    """遮罩层窗口，用于显示检测区域"""
    
    # 添加区域调整信号
    region_adjusted = pyqtSignal(str, int, int, int, int)
    
    def __init__(self, parent=None):
        """初始化遮罩层窗口"""
        super(OverlayMask, self).__init__(parent)
        
        # 设置窗口属性
        self.setWindowFlags(
            Qt.FramelessWindowHint |  # 无边框
            Qt.WindowStaysOnTopHint | # 置顶
            Qt.Tool                   # 工具窗口
        )
        self.setAttribute(Qt.WA_TranslucentBackground)  # 透明背景
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # 显示时不获取焦点
        
        # 在Windows系统上添加额外的窗口标志，解决显示问题
        if sys.platform == 'win32':
            import ctypes
            # 设置窗口为工具窗口，使其不在任务栏显示
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_TRANSPARENT = 0x00000020
            hwnd = self.winId()
            style = ctypes.windll.user32.GetWindowLongW(int(hwnd), GWL_EXSTYLE)
            style = style | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(int(hwnd), GWL_EXSTYLE, style)
        
        # 初始配置
        self.hwnd = None
        self.game_rect = None
        self.mask_opacity = 0.6  # 增加默认透明度
        
        # 初始化显示状态 - 修改为默认不显示
        self.show_ocr_area = False
        self.show_area_detection = False
        
        # 保存区域信息
        self.ocr_region = None
        self.area_region = None
        
        # 钓鱼机器人引用
        self.fishing_bot = None
        
        # 添加拖拽调整区域的状态变量
        self.dragging = False
        self.dragging_region = None  # 'ocr' 或 'area'
        self.drag_start_pos = None
        self.drag_edge = None  # 'topleft', 'topright', 'bottomleft', 'bottomright', 'move'
        self.drag_original_rect = None
        
        # 启用鼠标事件
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
    
    def set_game_hwnd(self, hwnd):
        """设置游戏窗口句柄"""
        self.hwnd = hwnd
        self.update_position()
    
    def set_fishing_bot(self, fishing_bot):
        """设置钓鱼机器人引用"""
        self.fishing_bot = fishing_bot
        
        # 从钓鱼机器人获取区域信息
        try:
            if hasattr(fishing_bot, 'temp_capture') and fishing_bot.temp_capture:
                if hasattr(fishing_bot.temp_capture, 'capture_region') and fishing_bot.temp_capture.capture_region:
                    self.ocr_region = fishing_bot.temp_capture.capture_region
                    logger.info(f"从钓鱼机器人获取OCR区域: {self.ocr_region}")
                    
            if hasattr(fishing_bot, 'area_capture') and fishing_bot.area_capture:
                if hasattr(fishing_bot.area_capture, 'capture_region') and fishing_bot.area_capture.capture_region:
                    self.area_region = fishing_bot.area_capture.capture_region
                    logger.info(f"从钓鱼机器人获取面积区域: {self.area_region}")
                    
            # 更新窗口位置以确保遮罩位置正确
            self.update_position()
        except Exception as e:
            logger.error(f"更新区域出错: {e}")
    
    def update_position(self):
        """更新遮罩位置以覆盖游戏窗口"""
        if not self.hwnd:
            logger.info("没有找到游戏窗口句柄，使用屏幕坐标")
            # 即使没有窗口句柄，也设置一个合理的位置和大小
            self.game_rect = (100, 100, 1400, 800)
            self.setGeometry(
                self.game_rect[0], self.game_rect[1],
                self.game_rect[2], self.game_rect[3]
            )
            return
            
        # 获取游戏窗口位置和大小
        window_rect = WinControl.get_window_rect(self.hwnd)
        if window_rect:
            # 获取窗口左上角坐标和尺寸
            x, y, width, height = window_rect

            # 保存游戏窗口矩形
            self.game_rect = (x, y, width, height)

            # 设置遮罩窗口位置和大小
            self.setGeometry(x, y, width, height)
            logger.debug(f"遮罩窗口位置已更新: ({x}, {y}, {width}x{height})")
        else:
            logger.warning("无法获取游戏窗口位置，使用默认位置")
            # 设置默认位置和大小
            self.game_rect = (100, 100, 1400, 800)
            self.setGeometry(
                self.game_rect[0], self.game_rect[1],
                self.game_rect[2], self.game_rect[3]
            )
    
    def set_opacity(self, opacity):
        """设置遮罩透明度"""
        self.mask_opacity = opacity / 100
        self.update()
    
    def set_show_ocr(self, show):
        """设置是否显示模板识别区域"""
        self.show_ocr_area = show
        # 如果两个区域都不显示，则完全隐藏遮罩层
        if not self.show_ocr_area and not self.show_area_detection:
            self.hide()
        elif show:
            self.show()
        self.update()

    def set_show_area(self, show):
        """设置是否显示面积检测区域"""
        self.show_area_detection = show
        # 如果两个区域都不显示，则完全隐藏遮罩层
        if not self.show_ocr_area and not self.show_area_detection:
            self.hide()
        elif show:
            self.show()
        self.update()

    def hide_completely(self):
        """完全隐藏遮罩层，确保不会干扰图像识别"""
        self.show_ocr_area = False
        self.show_area_detection = False
        self.hide()
        logger.info("遮罩层已完全隐藏，不会干扰图像识别功能")

    def show_conditionally(self):
        """根据设置条件性显示遮罩层"""
        if self.show_ocr_area or self.show_area_detection:
            self.show()
            self.update()
        else:
            self.hide()
    
    def get_handle_size(self):
        """获取调整区域手柄大小"""
        return 12  # 增大手柄尺寸

    def paintEvent(self, event):
        """绘制事件，绘制检测区域"""
        super(OverlayMask, self).paintEvent(event)

        # 如果窗口不可见或两个区域都不显示，则不绘制任何内容
        if not self.isVisible() or (not self.show_ocr_area and not self.show_area_detection):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        try:
            # 绘制模板识别区域
            if self.show_ocr_area and self.ocr_region:
                # 计算相对于遮罩窗口的坐标
                if self.game_rect:
                    x_offset = self.ocr_region[0] - self.game_rect[0]
                    y_offset = self.ocr_region[1] - self.game_rect[1]
                else:
                    x_offset = self.ocr_region[0]
                    y_offset = self.ocr_region[1]

                width = self.ocr_region[2]
                height = self.ocr_region[3]

                # 绘制半透明填充
                painter.fillRect(
                    x_offset, y_offset, width, height,
                    QColor(255, 0, 0, int(100 * self.mask_opacity))
                )

                # 绘制边框
                painter.setPen(QPen(QColor(255, 0, 0, int(255 * self.mask_opacity)), 2))
                painter.drawRect(x_offset, y_offset, width, height)

                # 绘制调整手柄
                handle_size = self.get_handle_size()
                painter.fillRect(
                    x_offset - handle_size//2, y_offset - handle_size//2,
                    handle_size, handle_size,
                    QColor(255, 255, 0, int(200 * self.mask_opacity))
                )
                painter.fillRect(
                    x_offset + width - handle_size//2, y_offset - handle_size//2,
                    handle_size, handle_size,
                    QColor(255, 255, 0, int(200 * self.mask_opacity))
                )
                painter.fillRect(
                    x_offset - handle_size//2, y_offset + height - handle_size//2,
                    handle_size, handle_size,
                    QColor(255, 255, 0, int(200 * self.mask_opacity))
                )
                painter.fillRect(
                    x_offset + width - handle_size//2, y_offset + height - handle_size//2,
                    handle_size, handle_size,
                    QColor(255, 255, 0, int(200 * self.mask_opacity))
                )

                # 设置文本颜色和字体
                painter.setPen(QColor(255, 0, 0, int(255 * self.mask_opacity)))
                font = QFont()
                font.setBold(True)
                font.setPointSize(12)  # 增大字体
                painter.setFont(font)

                # 绘制标签
                painter.drawText(
                    x_offset,
                    y_offset - 5,
                    "模板识别区域"
                )

                # 绘制坐标信息
                coord_text = f"({self.ocr_region[0]}, {self.ocr_region[1]}, {int(self.ocr_region[2])}x{int(self.ocr_region[3])})"
                painter.drawText(
                    x_offset,
                    y_offset + self.ocr_region[3] + 15,
                    coord_text
                )

            # 绘制面积检测区域
            if self.show_area_detection and self.area_region:
                # 计算相对于遮罩窗口的坐标
                if self.game_rect:
                    x_offset = self.area_region[0] - self.game_rect[0]
                    y_offset = self.area_region[1] - self.game_rect[1]
                else:
                    x_offset = self.area_region[0]
                    y_offset = self.area_region[1]

                width = self.area_region[2]
                height = self.area_region[3]

                # 绘制半透明填充
                painter.fillRect(
                    x_offset, y_offset, width, height,
                    QColor(0, 255, 0, int(50 * self.mask_opacity))
                )

                # 绘制边框
                painter.setPen(QPen(QColor(0, 255, 0, int(255 * self.mask_opacity)), 2))
                painter.drawRect(x_offset, y_offset, width, height)

                # 绘制调整手柄
                handle_size = self.get_handle_size()
                painter.fillRect(
                    x_offset - handle_size//2, y_offset - handle_size//2,
                    handle_size, handle_size,
                    QColor(255, 255, 0, int(200 * self.mask_opacity))
                )
                painter.fillRect(
                    x_offset + width - handle_size//2, y_offset - handle_size//2,
                    handle_size, handle_size,
                    QColor(255, 255, 0, int(200 * self.mask_opacity))
                )
                painter.fillRect(
                    x_offset - handle_size//2, y_offset + height - handle_size//2,
                    handle_size, handle_size,
                    QColor(255, 255, 0, int(200 * self.mask_opacity))
                )
                painter.fillRect(
                    x_offset + width - handle_size//2, y_offset + height - handle_size//2,
                    handle_size, handle_size,
                    QColor(255, 255, 0, int(200 * self.mask_opacity))
                )

                # 设置文本颜色和字体
                painter.setPen(QColor(0, 255, 255, int(255 * self.mask_opacity)))
                font = QFont()
                font.setBold(True)
                font.setPointSize(12)  # 增大字体
                painter.setFont(font)

                # 绘制标签
                painter.drawText(
                    x_offset,
                    y_offset - 5,
                    "面积检测区域"
                )

                # 绘制坐标信息
                coord_text = f"({self.area_region[0]}, {self.area_region[1]}, {int(self.area_region[2])}x{int(self.area_region[3])})"
                painter.drawText(
                    x_offset,
                    y_offset + self.area_region[3] + 15,
                    coord_text
                )
        except Exception as e:
            logger.error(f"绘制区域出错: {e}")

    def mousePressEvent(self, event):
        """鼠标按下事件，用于选择和调整区域"""
        try:
            if not self.isVisible() or (not self.show_ocr_area and not self.show_area_detection):
                super(OverlayMask, self).mousePressEvent(event)
                return

            pos = event.pos()
            handle_size = self.get_handle_size()

            # 检查是否点击了OCR区域的调整手柄或区域内部
            if self.show_ocr_area and self.ocr_region:
                # 计算相对于遮罩窗口的坐标
                if self.game_rect:
                    x_offset = self.ocr_region[0] - self.game_rect[0]
                    y_offset = self.ocr_region[1] - self.game_rect[1]
                else:
                    x_offset = self.ocr_region[0]
                    y_offset = self.ocr_region[1]

                width = self.ocr_region[2]
                height = self.ocr_region[3]

                # 检查各个调整手柄
                # 左上角
                if abs(pos.x() - x_offset) < handle_size and abs(pos.y() - y_offset) < handle_size:
                    self.dragging = True
                    self.dragging_region = 'ocr'
                    self.drag_edge = 'topleft'
                    self.drag_start_pos = pos
                    self.drag_original_rect = (x_offset, y_offset, width, height)
                    return
                # 右上角
                elif abs(pos.x() - (x_offset + width)) < handle_size and abs(pos.y() - y_offset) < handle_size:
                    self.dragging = True
                    self.dragging_region = 'ocr'
                    self.drag_edge = 'topright'
                    self.drag_start_pos = pos
                    self.drag_original_rect = (x_offset, y_offset, width, height)
                    return
                # 左下角
                elif abs(pos.x() - x_offset) < handle_size and abs(pos.y() - (y_offset + height)) < handle_size:
                    self.dragging = True
                    self.dragging_region = 'ocr'
                    self.drag_edge = 'bottomleft'
                    self.drag_start_pos = pos
                    self.drag_original_rect = (x_offset, y_offset, width, height)
                    return
                # 右下角
                elif abs(pos.x() - (x_offset + width)) < handle_size and abs(pos.y() - (y_offset + height)) < handle_size:
                    self.dragging = True
                    self.dragging_region = 'ocr'
                    self.drag_edge = 'bottomright'
                    self.drag_start_pos = pos
                    self.drag_original_rect = (x_offset, y_offset, width, height)
                    return
                # 整体移动
                elif x_offset <= pos.x() <= x_offset + width and y_offset <= pos.y() <= y_offset + height:
                    self.dragging = True
                    self.dragging_region = 'ocr'
                    self.drag_edge = 'move'
                    self.drag_start_pos = pos
                    self.drag_original_rect = (x_offset, y_offset, width, height)
                    return

            # 检查是否点击了面积检测区域的调整手柄或区域内部
            if self.show_area_detection and self.area_region:
                # 计算相对于遮罩窗口的坐标
                if self.game_rect:
                    x_offset = self.area_region[0] - self.game_rect[0]
                    y_offset = self.area_region[1] - self.game_rect[1]
                else:
                    x_offset = self.area_region[0]
                    y_offset = self.area_region[1]

                width = self.area_region[2]
                height = self.area_region[3]

                # 检查各个调整手柄
                # 左上角
                if abs(pos.x() - x_offset) < handle_size and abs(pos.y() - y_offset) < handle_size:
                    self.dragging = True
                    self.dragging_region = 'area'
                    self.drag_edge = 'topleft'
                    self.drag_start_pos = pos
                    self.drag_original_rect = (x_offset, y_offset, width, height)
                    return
                # 右上角
                elif abs(pos.x() - (x_offset + width)) < handle_size and abs(pos.y() - y_offset) < handle_size:
                    self.dragging = True
                    self.dragging_region = 'area'
                    self.drag_edge = 'topright'
                    self.drag_start_pos = pos
                    self.drag_original_rect = (x_offset, y_offset, width, height)
                    return
                # 左下角
                elif abs(pos.x() - x_offset) < handle_size and abs(pos.y() - (y_offset + height)) < handle_size:
                    self.dragging = True
                    self.dragging_region = 'area'
                    self.drag_edge = 'bottomleft'
                    self.drag_start_pos = pos
                    self.drag_original_rect = (x_offset, y_offset, width, height)
                    return
                # 右下角
                elif abs(pos.x() - (x_offset + width)) < handle_size and abs(pos.y() - (y_offset + height)) < handle_size:
                    self.dragging = True
                    self.dragging_region = 'area'
                    self.drag_edge = 'bottomright'
                    self.drag_start_pos = pos
                    self.drag_original_rect = (x_offset, y_offset, width, height)
                    return
                # 整体移动
                elif x_offset <= pos.x() <= x_offset + width and y_offset <= pos.y() <= y_offset + height:
                    self.dragging = True
                    self.dragging_region = 'area'
                    self.drag_edge = 'move'
                    self.drag_start_pos = pos
                    self.drag_original_rect = (x_offset, y_offset, width, height)
                    return
        except Exception as e:
            logger.error(f"鼠标按下事件处理错误: {e}")

        super(OverlayMask, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件，用于拖拽调整区域"""
        try:
            if self.dragging and self.drag_start_pos and self.drag_original_rect:
                pos = event.pos()
                dx = pos.x() - self.drag_start_pos.x()
                dy = pos.y() - self.drag_start_pos.y()

                orig_x, orig_y, orig_width, orig_height = self.drag_original_rect

                # 根据拖拽边缘计算新的区域
                if self.drag_edge == 'move':
                    new_x = orig_x + dx
                    new_y = orig_y + dy
                    new_width = orig_width
                    new_height = orig_height
                elif self.drag_edge == 'topleft':
                    new_x = orig_x + dx
                    new_y = orig_y + dy
                    new_width = max(10, orig_width - dx)
                    new_height = max(10, orig_height - dy)
                elif self.drag_edge == 'topright':
                    new_x = orig_x
                    new_y = orig_y + dy
                    new_width = max(10, orig_width + dx)
                    new_height = max(10, orig_height - dy)
                elif self.drag_edge == 'bottomleft':
                    new_x = orig_x + dx
                    new_y = orig_y
                    new_width = max(10, orig_width - dx)
                    new_height = max(10, orig_height + dy)
                elif self.drag_edge == 'bottomright':
                    new_x = orig_x
                    new_y = orig_y
                    new_width = max(10, orig_width + dx)
                    new_height = max(10, orig_height + dy)
                else:
                    return

                # 更新对应区域
                if self.dragging_region == 'ocr':
                    # 计算在游戏窗口中的绝对坐标
                    abs_x = new_x + self.game_rect[0] if self.game_rect else new_x
                    abs_y = new_y + self.game_rect[1] if self.game_rect else new_y

                    # 更新OCR区域
                    self.ocr_region = (abs_x, abs_y, new_width, new_height)
                elif self.dragging_region == 'area':
                    # 计算在游戏窗口中的绝对坐标
                    abs_x = new_x + self.game_rect[0] if self.game_rect else new_x
                    abs_y = new_y + self.game_rect[1] if self.game_rect else new_y

                    # 更新面积检测区域
                    self.area_region = (abs_x, abs_y, new_width, new_height)

                # 更新显示
                self.update()
                return
        except Exception as e:
            logger.error(f"鼠标移动事件处理错误: {e}")

        super(OverlayMask, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件，完成区域调整"""
        try:
            if self.dragging:
                # 发送区域调整信号
                if self.dragging_region == 'ocr' and self.ocr_region:
                    self.region_adjusted.emit('ocr', self.ocr_region[0], self.ocr_region[1],
                                            self.ocr_region[2], self.ocr_region[3])
                elif self.dragging_region == 'area' and self.area_region:
                    self.region_adjusted.emit('area', self.area_region[0], self.area_region[1],
                                            self.area_region[2], self.area_region[3])

                # 重置拖拽状态
                self.dragging = False
                self.dragging_region = None
                self.drag_start_pos = None
                self.drag_edge = None
                self.drag_original_rect = None
                return
        except Exception as e:
            logger.error(f"鼠标释放事件处理错误: {e}")

        super(OverlayMask, self).mouseReleaseEvent(event)
