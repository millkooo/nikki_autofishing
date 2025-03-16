import sys
import logging
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QPainter, QColor
import win32gui
import win32con
import win32process
from Ui_Manage.WindowManager import WinControl

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TransparentOverlay(QMainWindow):
    """透明覆盖窗口类，可以覆盖在游戏窗口上"""

    def __init__(self, target_config=None, parent=None):
        """初始化透明窗口

        Args:
            target_config: 目标窗口配置，包含title_part, window_class, process_exe
            parent: 父窗口
        """
        super(TransparentOverlay, self).__init__(parent)

        # 窗口基本属性设置
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)  # 透明背景
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # 显示时不获取焦点

        # 默认不启用鼠标穿透，以便可以点击UI元素
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        # 目标窗口相关
        self.target_config = target_config
        self.target_hwnd = None
        self.is_following = False

        # 初始化UI
        self.init_ui()
        
        # 如果提供了目标窗口配置，则尝试查找并跟随目标窗口
        if self.target_config:
            self.find_and_follow_target()

    def init_ui(self):
        """初始化UI组件"""
        # 创建中央窗口部件
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        
        # 设置窗口大小和位置
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(1550, 250, 370, 470)

    def find_and_follow_target(self):
        """查找并跟随目标窗口"""
        if not self.target_config:
            logger.warning("未提供目标窗口配置")
            return False
        
        # 查找目标窗口
        self.target_hwnd = WinControl.find_target_window(self.target_config)
        if not self.target_hwnd:
            logger.error("未找到目标窗口")
            return False
        
        # 获取目标窗口位置和大小
        self.update_position()
        
        # 设置为跟随状态
        self.is_following = True
        return True
    
    def update_position(self):
        """更新窗口位置以匹配目标窗口"""
        if not self.target_hwnd:
            return
        
        try:
            # 获取目标窗口的客户区矩形
            rect = win32gui.GetClientRect(self.target_hwnd)
            # 将客户区坐标转换为屏幕坐标
            left, top = win32gui.ClientToScreen(self.target_hwnd, (0, 0))
            right, bottom = win32gui.ClientToScreen(self.target_hwnd, (rect[2], rect[3]))
            
            # 设置覆盖窗口的位置和大小
            self.setGeometry(1550, 250, 370, 470)
        except Exception as e:
            logger.error(f"更新窗口位置失败: {str(e)}")
    
    def paintEvent(self, event):
        """绘制事件，可以在这里自定义窗口外观"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 抗锯齿
        
        # 这里可以绘制自定义内容
        # 例如：绘制半透明背景
        # painter.fillRect(self.rect(), QColor(0, 0, 0, 50))  # RGBA，最后一个参数是透明度
    
    def showEvent(self, event):
        """窗口显示事件"""
        super(TransparentOverlay, self).showEvent(event)
        if self.is_following:
            self.update_position()
        # 确保窗口始终在顶层
        self.raise_()
        self.activateWindow()
    
    def set_click_through(self, enabled=True):
        """设置鼠标点击穿透
        
        Args:
            enabled: 是否启用点击穿透
        """
        if enabled:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        else:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
    
    def set_target_config(self, config):
        """设置目标窗口配置
        
        Args:
            config: 目标窗口配置
        """
        self.target_config = config
        return self.find_and_follow_target()

