import logging
import os
import sys

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QProgressBar

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Ui_Manage.TransparentOverlay import TransparentOverlay

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FishingOverlay(TransparentOverlay):
    """钓鱼专用透明覆盖窗口类"""
    
    # 定义信号
    start_signal = pyqtSignal()
    stop_signal = pyqtSignal()
    
    def __init__(self, target_config=None, parent=None):
        """初始化钓鱼透明窗口
        
        Args:
            target_config: 目标窗口配置，包含title_part, window_class, process_exe
            parent: 父窗口
        """
        super(FishingOverlay, self).__init__(target_config, parent)
        
        # 钓鱼状态
        self.is_fishing = False
        self.fish_progress = 0
        self.fish_status = "等待开始钓鱼..."
        
    def init_ui(self):
        """初始化UI组件，重写父类方法"""
        # 创建中央窗口部件
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        # 创建主布局
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(10, 10, 10, 10)  # 设置边距

        # 标题标签
        self.title_label = QLabel("自动钓鱼助手")
        self.title_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold; background-color: rgba(0, 0, 0, 150); padding: 5px;")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title_label)
        
        # 状态标签
        self.status_label = QLabel("状态: 等待开始")
        self.status_label.setStyleSheet("color: white; font-size: 14px; background-color: rgba(0, 0, 0, 100); padding: 5px;")
        self.layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(50, 50, 50, 150);
                color: white;
                border-radius: 5px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: rgba(0, 150, 255, 200);
                border-radius: 5px;
            }
        """)
        self.layout.addWidget(self.progress_bar)
        
        # 按钮布局
        self.button_layout = QHBoxLayout()
        
        # 开始按钮
        self.start_button = QPushButton("开始钓鱼")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 150, 0, 200);
                color: white;
                border-radius: 5px;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(0, 180, 0, 220);
            }
            QPushButton:pressed {
                background-color: rgba(0, 120, 0, 200);
            }
        """)
        self.start_button.clicked.connect(self.on_start_clicked)
        self.button_layout.addWidget(self.start_button)
        
        # 停止按钮
        self.stop_button = QPushButton("停止钓鱼")
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(150, 0, 0, 200);
                color: white;
                border-radius: 5px;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(180, 0, 0, 220);
            }
            QPushButton:pressed {
                background-color: rgba(120, 0, 0, 200);
            }
        """)
        self.stop_button.clicked.connect(self.on_stop_clicked)
        self.stop_button.setEnabled(False)
        self.button_layout.addWidget(self.stop_button)
        
        self.layout.addLayout(self.button_layout)
        
        # 信息标签
        self.info_label = QLabel("提示: 莴苣妈妈不是莴笋，是贡菜")
        self.info_label.setStyleSheet("color: white; font-size: 16px; background-color: rgba(0, 0, 0, 100); padding: 5px;")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.info_label)
        
        # 日志区域
        self.log_label = QLabel("日志记录:\n等待操作...")
        self.log_label.setStyleSheet("color: white; font-size: 12px; background-color: rgba(0, 0, 0, 100); padding: 5px;")
        self.log_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.log_label.setWordWrap(True)
        self.log_label.setMinimumHeight(100)
        self.layout.addWidget(self.log_label)
        
        # 设置窗口大小和位置
        self.setGeometry(1550, 250, 300, 350)
        
    def paintEvent(self, event):
        """绘制事件，自定义窗口外观"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 抗锯齿
        
        # 绘制半透明背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))  # RGBA，最后一个参数是透明度
        
        # 绘制边框
        pen = painter.pen()
        pen.setColor(QColor(0, 150, 255, 200))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
    
    def on_start_clicked(self):
        """开始按钮点击事件"""
        self.is_fishing = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("状态: 正在钓鱼")
        self.add_log("开始钓鱼")
        self.start_signal.emit()
    
    def on_stop_clicked(self):
        """停止按钮点击事件"""
        self.is_fishing = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("状态: 已停止")
        self.add_log("停止钓鱼")
        self.stop_signal.emit()
    
    def update_fishing_progress(self, progress, status=None):
        """更新钓鱼进度
        
        Args:
            progress: 进度值(0-100)
            status: 状态描述
        """
        self.fish_progress = progress
        self.progress_bar.setValue(progress)
        
        if status:
            self.fish_status = status
            self.status_label.setText(f"状态: {status}")
            self.add_log(status)
    
    def add_log(self, message):
        """添加日志消息
        
        Args:
            message: 日志消息
        """
        current_text = self.log_label.text()
        lines = current_text.split('\n')
        
        # 保持最多显示5行日志
        if len(lines) > 6:  # 第一行是"日志记录:"
            lines = lines[:1] + lines[-5:]
            
        # 添加新日志
        lines.append(message)
        self.log_label.setText('\n'.join(lines))

# 示例用法
def main():
    app = QApplication(sys.argv)
    
    # 目标窗口配置
    target_config = {
        "title_part": "无限暖暖",
        "window_class": "UnrealWindow",
        "process_exe": "X6Game-Win64-Shipping.exe"
    }
    
    # 创建钓鱼覆盖窗口
    overlay = FishingOverlay(target_config)
    overlay.show()
    
    sys.exit(app.exec_())

