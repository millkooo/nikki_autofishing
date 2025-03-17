import logging
import os
import sys
import json
import random

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QProgressBar, QCheckBox, QComboBox, QSlider

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Ui_Manage.TransparentOverlay import TransparentOverlay

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_resource_path(relative_path):
    """获取资源文件的绝对路径"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 创建临时文件夹，将路径存储在 _MEIPASS 中
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class FishingOverlay(TransparentOverlay):
    """钓鱼专用透明覆盖窗口类"""
    
    # 定义信号
    start_signal = pyqtSignal()
    stop_signal = pyqtSignal()
    fishing_mode_changed = pyqtSignal(int)  # 新增信号，用于通知钓鱼模式变更
    show_region_signal = pyqtSignal(bool)  # True表示显示区域，False表示隐藏区域
    scale_changed_signal = pyqtSignal(float)  # 新增信号，用于通知UI缩放比例变更
    
    def __init__(self, target_config=None, parent=None):
        """初始化钓鱼透明窗口
        
        Args:
            target_config: 目标窗口配置，包含title_part, window_class, process_exe
            parent: 父窗口
        """
        # 在调用父类初始化之前先初始化stories和缩放相关变量
        # 缩放相关变量
        self.scale_factor = 1.0  # 初始缩放比例为1.0
        self.min_scale = 0.5    # 最小缩放比例
        self.max_scale = 2.0    # 最大缩放比例
        self.original_size = (300, 400)  # 原始窗口大小
        
        # 加载小姚故事集
        try:
            story_path = get_resource_path('小姚故事选集.json')
            with open(story_path, 'r', encoding='utf-8') as f:
                self.stories = json.load(f)['stories']
        except Exception as e:
            logger.error(f"加载故事集失败: {e}")
            self.stories = ["莴苣去年和欧的白求的婚"]  
            
        super(FishingOverlay, self).__init__(target_config, parent)
        
        # 钓鱼状态
        self.is_fishing = False
        self.fish_progress = 0
        self.fish_status = "等待开始钓鱼..."
        
        # 拖动相关变量
        self.dragging = False
        self.drag_position = None
        
        # 添加新的状态变量
        self.show_region = False
        self.title_click_count = 0  # 添加标题点击计数器
        self.start_click_count = 0  # 添加开始按钮点击计数器
        
        # 初始化UI
        self.init_ui()
        
        # 设置鼠标追踪 - 移到init_ui之后，确保title_label已经创建
        self.setMouseTracking(True)
        self.title_label.setMouseTracking(True)
        self.title_label.setCursor(Qt.OpenHandCursor)
        
    def format_story(self, story):
        """格式化故事文本，确保最多三行显示，每行最多14个中文字
        
        Args:
            story: 原始故事文本
            
        Returns:
            格式化后的故事文本
        """
        prefix = "冷知识："
        max_chars = 14  # 每行最多字符数
        
        if len(story) <= max_chars - len(prefix):  # 如果故事加上前缀不超过14个字符
            return prefix + story
        elif len(story) <= max_chars * 2 - len(prefix):  # 如果故事需要两行
            first_line = prefix + story[:max_chars - len(prefix)]
            second_line = story[max_chars - len(prefix):max_chars * 2 - len(prefix)]
            return first_line + "\n" + second_line
        else:  
            first_line = prefix + story[:max_chars - len(prefix)]
            second_line = story[max_chars - len(prefix):max_chars * 2 - len(prefix)]
            third_line = story[max_chars * 2 - len(prefix):max_chars * 3 - len(prefix)]
            return first_line + "\n" + second_line + "\n" + third_line
        
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
        
        # 钓鱼模式选择
        self.mode_layout = QHBoxLayout()
        self.mode_label = QLabel("钓鱼模式:")
        self.mode_label.setStyleSheet("color: white; font-size: 14px;")
        self.mode_layout.addWidget(self.mode_label)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("单次钓鱼")
        self.mode_combo.addItem("钓鱼2次")
        self.mode_combo.addItem("钓鱼3次")
        self.mode_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(50, 50, 50, 150);
                color: white;
                border-radius: 5px;
                padding: 5px;
            }
            QComboBox:hover {
                background-color: rgba(70, 70, 70, 170);
            }
            QComboBox QAbstractItemView {
                background-color: rgba(50, 50, 50, 200);
                color: white;
                selection-background-color: rgba(0, 150, 255, 150);
            }
        """)
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        self.mode_layout.addWidget(self.mode_combo)
        
        self.layout.addLayout(self.mode_layout)
        
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
        
        # 在按钮布局中添加新的按钮
        self.show_region_button = QPushButton("显示检测区域")
        self.show_region_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(150, 150, 0, 200);
                color: white;
                border-radius: 5px;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(180, 180, 0, 220);
            }
            QPushButton:pressed {
                background-color: rgba(120, 120, 0, 200);
            }
            QPushButton:checked {
                background-color: rgba(200, 200, 0, 220);
            }
        """)
        self.show_region_button.setCheckable(True)  # 使按钮可切换
        self.show_region_button.clicked.connect(self.on_show_region_clicked)
        self.button_layout.addWidget(self.show_region_button)
        self.show_region_button.hide()  # 初始时隐藏按钮
        
        self.layout.addLayout(self.button_layout)
        
        # 添加缩放控制布局
        self.scale_layout = QHBoxLayout()
        
        # 缩小按钮
        self.zoom_out_button = QPushButton("-")
        self.zoom_out_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(50, 50, 150, 200);
                color: white;
                border-radius: 5px;
                padding: 5px;
                font-weight: bold;
                min-width: 30px;
            }
            QPushButton:hover {
                background-color: rgba(70, 70, 180, 220);
            }
            QPushButton:pressed {
                background-color: rgba(30, 30, 120, 200);
            }
        """)
        self.zoom_out_button.clicked.connect(self.on_zoom_out_clicked)
        self.scale_layout.addWidget(self.zoom_out_button)
        
        # 缩放滑块
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(int(self.min_scale * 100), int(self.max_scale * 100))
        self.scale_slider.setValue(int(self.scale_factor * 100))
        self.scale_slider.setStyleSheet("""
            QSlider {
                background-color: transparent;
            }
            QSlider::groove:horizontal {
                background-color: rgba(50, 50, 50, 150);
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background-color: rgba(0, 150, 255, 200);
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background-color: rgba(0, 180, 255, 220);
            }
        """)
        self.scale_slider.valueChanged.connect(self.on_scale_slider_changed)
        self.scale_layout.addWidget(self.scale_slider)
        
        # 放大按钮
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(50, 50, 150, 200);
                color: white;
                border-radius: 5px;
                padding: 5px;
                font-weight: bold;
                min-width: 30px;
            }
            QPushButton:hover {
                background-color: rgba(70, 70, 180, 220);
            }
            QPushButton:pressed {
                background-color: rgba(30, 30, 120, 200);
            }
        """)
        self.zoom_in_button.clicked.connect(self.on_zoom_in_clicked)
        self.scale_layout.addWidget(self.zoom_in_button)
        
        # 缩放比例标签
        self.scale_label = QLabel(f"{int(self.scale_factor * 100)}%")
        self.scale_label.setStyleSheet("color: white; font-size: 12px;")
        self.scale_label.setAlignment(Qt.AlignCenter)
        self.scale_layout.addWidget(self.scale_label)
        
        self.layout.addLayout(self.scale_layout)
        
        # 信息标签
        random_story = random.choice(self.stories)
        formatted_story = self.format_story(random_story)
        self.info_label = QLabel(formatted_story)  
        self.info_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16px;
                background-color: rgba(0, 0, 0, 100);
                padding: 5px;
                qproperty-alignment: AlignCenter;
            }
        """)
        self.info_label.setFixedHeight(100)  # 保持三行高度
        self.layout.addWidget(self.info_label)
        
        # 日志区域
        self.log_label = QLabel("日志记录:\n等待操作...")
        self.log_label.setStyleSheet("color: white; font-size: 12px; background-color: rgba(0, 0, 0, 100); padding: 5px;")
        self.log_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.log_label.setWordWrap(True)
        self.log_label.setMinimumHeight(100)
        self.layout.addWidget(self.log_label)
        
        # 设置窗口大小和位置
        self.setGeometry(1550, 250, 300, 400)  # 增加高度以适应新添加的控件
        
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
        self.update_story()  # 更新故事
        self.add_log("开始钓鱼")
        self.add_log(f"当前钓鱼模式: {self.mode_combo.currentText()}")
        self.add_log(f"模式索引: {self.mode_combo.currentIndex()}")
        
        # 增加点击计数并检查是否显示检测区域按钮
        self.start_click_count += 1
        if self.start_click_count >= 8 and not self.show_region_button.isVisible():
            self.show_region_button.show()
            self.add_log("已解锁显示检测区域功能")
        
        self.start_signal.emit()
    
    def on_stop_clicked(self):
        """停止按钮点击事件"""
        self.is_fishing = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("状态: 已停止")
        self.add_log("停止钓鱼")
        self.add_log(f"当前钓鱼模式: {self.mode_combo.currentText()}")
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
            old_status = self.fish_status
            self.fish_status = status
            self.status_label.setText(f"状态: {status}")
            
            # 只有状态变化时才添加日志
            if old_status != status:
                self.add_log(status)
                if status == "钓鱼完成！等待手动开始下一次" and self.mode_combo.currentIndex() == 1:
                    self.add_log("自动钓鱼模式: 等待自动开始下一次钓鱼")
    
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

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            # 只有点击标题栏才能拖动
            if self.title_label.geometry().contains(event.pos()):
                self.dragging = True
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                self.title_label.setCursor(Qt.ClosedHandCursor)
                
                # 增加标题点击计数并检查是否显示检测区域按钮
                self.title_click_count += 1
                if self.title_click_count >= 8 and not self.show_region_button.isVisible():
                    self.show_region_button.show()
                    self.add_log("已解锁显示检测区域功能")
                
                event.accept()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.title_label.setCursor(Qt.OpenHandCursor)
            event.accept()
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def on_mode_changed(self, index):
        """钓鱼模式变更事件"""
        mode_name = self.mode_combo.currentText()
        self.add_log(f"钓鱼模式已切换为: {mode_name}")
        self.add_log(f"模式索引: {index}")
        
        if self.is_fishing:
            self.add_log("警告: 在钓鱼过程中切换模式，将停止当前钓鱼")
            
        self.fishing_mode_changed.emit(index)

    def update_story(self):
        """更新显示的故事"""
        random_story = random.choice(self.stories)
        formatted_story = self.format_story(random_story)
        self.info_label.setText(formatted_story)  # 不需要额外添加冷知识前缀

    def on_show_region_clicked(self):
        """显示/隐藏检测区域按钮点击事件"""
        self.show_region = self.show_region_button.isChecked()
        self.show_region_signal.emit(self.show_region)
        if self.show_region:
            self.add_log("显示检测区域")
        else:
            self.add_log("隐藏检测区域")
            
    def on_zoom_in_clicked(self):
        """放大按钮点击事件"""
        new_scale = min(self.scale_factor + 0.1, self.max_scale)
        self.set_scale(new_scale)
        
    def on_zoom_out_clicked(self):
        """缩小按钮点击事件"""
        new_scale = max(self.scale_factor - 0.1, self.min_scale)
        self.set_scale(new_scale)
        
    def on_scale_slider_changed(self, value):
        """缩放滑块值变更事件"""
        new_scale = value / 100.0
        self.set_scale(new_scale, update_slider=False)
        
    def set_scale(self, scale, update_slider=True):
        """设置UI缩放比例
        
        Args:
            scale: 缩放比例
            update_slider: 是否更新滑块位置
        """
        if scale == self.scale_factor:
            return
            
        self.scale_factor = scale
        
        # 更新缩放比例标签
        self.scale_label.setText(f"{int(self.scale_factor * 100)}%")
        
        # 更新滑块位置（如果需要）
        if update_slider:
            self.scale_slider.setValue(int(self.scale_factor * 100))
        
        # 计算新的窗口大小
        new_width = int(self.original_size[0] * self.scale_factor)
        new_height = int(self.original_size[1] * self.scale_factor)
        
        # 获取当前窗口位置
        current_pos = self.pos()
        
        # 调整窗口大小，保持位置不变
        self.setGeometry(current_pos.x(), current_pos.y(), new_width, new_height)
        
        # 调整字体大小
        self.update_font_sizes()
        
        # 发送缩放变更信号
        self.scale_changed_signal.emit(self.scale_factor)
        
        self.add_log(f"UI缩放比例已调整为: {int(self.scale_factor * 100)}%")
        
    def update_font_sizes(self):
        """根据缩放比例更新字体大小和控件大小"""
        # 标题标签
        title_style = self.title_label.styleSheet()
        title_style = self.update_font_size_in_style(title_style, 18)
        self.title_label.setStyleSheet(title_style)
        
        # 状态标签
        status_style = self.status_label.styleSheet()
        status_style = self.update_font_size_in_style(status_style, 14)
        self.status_label.setStyleSheet(status_style)
        
        # 模式标签
        mode_style = self.mode_label.styleSheet()
        mode_style = self.update_font_size_in_style(mode_style, 14)
        self.mode_label.setStyleSheet(mode_style)
        
        # 模式选择框
        combo_style = self.mode_combo.styleSheet()
        combo_style = self.update_font_size_in_style(combo_style, 14)
        combo_style = self.update_padding_in_style(combo_style, 5)
        combo_style = self.update_border_radius_in_style(combo_style, 5)
        self.mode_combo.setStyleSheet(combo_style)
        
        # 进度条
        progress_style = self.progress_bar.styleSheet()
        progress_style = self.update_font_size_in_style(progress_style, 14)
        progress_style = self.update_height_in_style(progress_style, 20)
        progress_style = self.update_border_radius_in_style(progress_style, 5)
        self.progress_bar.setStyleSheet(progress_style)
        
        # 开始按钮
        start_style = self.start_button.styleSheet()
        start_style = self.update_font_size_in_style(start_style, 14)
        start_style = self.update_padding_in_style(start_style, 5)
        start_style = self.update_border_radius_in_style(start_style, 5)
        self.start_button.setStyleSheet(start_style)
        
        # 停止按钮
        stop_style = self.stop_button.styleSheet()
        stop_style = self.update_font_size_in_style(stop_style, 14)
        stop_style = self.update_padding_in_style(stop_style, 5)
        stop_style = self.update_border_radius_in_style(stop_style, 5)
        self.stop_button.setStyleSheet(stop_style)
        
        # 显示检测区域按钮
        region_style = self.show_region_button.styleSheet()
        region_style = self.update_font_size_in_style(region_style, 14)
        region_style = self.update_padding_in_style(region_style, 5)
        region_style = self.update_border_radius_in_style(region_style, 5)
        self.show_region_button.setStyleSheet(region_style)
        
        # 缩小按钮
        zoom_out_style = self.zoom_out_button.styleSheet()
        zoom_out_style = self.update_font_size_in_style(zoom_out_style, 14)
        zoom_out_style = self.update_padding_in_style(zoom_out_style, 5)
        zoom_out_style = self.update_border_radius_in_style(zoom_out_style, 5)
        zoom_out_style = self.update_min_width_in_style(zoom_out_style, 30)
        self.zoom_out_button.setStyleSheet(zoom_out_style)
        
        # 放大按钮
        zoom_in_style = self.zoom_in_button.styleSheet()
        zoom_in_style = self.update_font_size_in_style(zoom_in_style, 14)
        zoom_in_style = self.update_padding_in_style(zoom_in_style, 5)
        zoom_in_style = self.update_border_radius_in_style(zoom_in_style, 5)
        zoom_in_style = self.update_min_width_in_style(zoom_in_style, 30)
        self.zoom_in_button.setStyleSheet(zoom_in_style)
        
        # 缩放滑块
        slider_style = self.scale_slider.styleSheet()
        slider_style = self.update_height_in_style(slider_style, 8, "QSlider::groove:horizontal")
        slider_style = self.update_width_in_style(slider_style, 16, "QSlider::handle:horizontal")
        slider_style = self.update_border_radius_in_style(slider_style, 4, "QSlider::groove:horizontal")
        slider_style = self.update_border_radius_in_style(slider_style, 8, "QSlider::handle:horizontal")
        self.scale_slider.setStyleSheet(slider_style)
        
        # 缩放比例标签
        scale_label_style = self.scale_label.styleSheet()
        scale_label_style = self.update_font_size_in_style(scale_label_style, 12)
        self.scale_label.setStyleSheet(scale_label_style)
        
        # 信息标签
        info_style = self.info_label.styleSheet()
        info_style = self.update_font_size_in_style(info_style, 16)
        info_style = self.update_padding_in_style(info_style, 5)
        self.info_label.setStyleSheet(info_style)
        # 调整信息标签高度
        self.info_label.setFixedHeight(int(100 * self.scale_factor))
        
        # 日志标签
        log_style = self.log_label.styleSheet()
        log_style = self.update_font_size_in_style(log_style, 12)
        log_style = self.update_padding_in_style(log_style, 5)
        self.log_label.setStyleSheet(log_style)
        # 调整日志标签最小高度
        self.log_label.setMinimumHeight(int(100 * self.scale_factor))
        
    def update_font_size_in_style(self, style, base_size):
        """在样式表中更新字体大小
        
        Args:
            style: 原始样式表
            base_size: 基础字体大小
            
        Returns:
            更新后的样式表
        """
        import re
        # 计算新的字体大小
        new_size = int(base_size * self.scale_factor)
        
        # 使用正则表达式替换字体大小
        pattern = r'font-size:\s*\d+px'
        replacement = f'font-size: {new_size}px'
        
        if re.search(pattern, style):
            return re.sub(pattern, replacement, style)
        else:
            return style
            
    def update_padding_in_style(self, style, base_padding, selector=""):
        """在样式表中更新内边距
        
        Args:
            style: 原始样式表
            base_padding: 基础内边距
            selector: CSS选择器，为空时应用于整个样式
            
        Returns:
            更新后的样式表
        """
        import re
        # 计算新的内边距
        new_padding = int(base_padding * self.scale_factor)
        
        # 使用正则表达式替换内边距
        if selector:
            pattern = rf'{selector}\s*{{\s*[^}}]*padding:\s*\d+px[^}}]*}}'
            if re.search(pattern, style):
                return re.sub(r'padding:\s*\d+px', f'padding: {new_padding}px', style)
        else:
            pattern = r'padding:\s*\d+px'
            if re.search(pattern, style):
                return re.sub(pattern, f'padding: {new_padding}px', style)
        
        return style
        
    def update_border_radius_in_style(self, style, base_radius, selector=""):
        """在样式表中更新边框圆角
        
        Args:
            style: 原始样式表
            base_radius: 基础圆角半径
            selector: CSS选择器，为空时应用于整个样式
            
        Returns:
            更新后的样式表
        """
        import re
        # 计算新的圆角半径
        new_radius = int(base_radius * self.scale_factor)
        
        # 使用正则表达式替换圆角半径
        if selector:
            pattern = rf'{selector}\s*{{\s*[^}}]*border-radius:\s*\d+px[^}}]*}}'
            if re.search(pattern, style):
                return re.sub(r'border-radius:\s*\d+px', f'border-radius: {new_radius}px', style)
        else:
            pattern = r'border-radius:\s*\d+px'
            if re.search(pattern, style):
                return re.sub(pattern, f'border-radius: {new_radius}px', style)
        
        return style
        
    def update_height_in_style(self, style, base_height, selector=""):
        """在样式表中更新高度
        
        Args:
            style: 原始样式表
            base_height: 基础高度
            selector: CSS选择器，为空时应用于整个样式
            
        Returns:
            更新后的样式表
        """
        import re
        # 计算新的高度
        new_height = int(base_height * self.scale_factor)
        
        # 使用正则表达式替换高度
        if selector:
            pattern = rf'{selector}\s*{{\s*[^}}]*height:\s*\d+px[^}}]*}}'
            if re.search(pattern, style):
                return re.sub(r'height:\s*\d+px', f'height: {new_height}px', style)
        else:
            pattern = r'height:\s*\d+px'
            if re.search(pattern, style):
                return re.sub(pattern, f'height: {new_height}px', style)
        
        return style
        
    def update_width_in_style(self, style, base_width, selector=""):
        """在样式表中更新宽度
        
        Args:
            style: 原始样式表
            base_width: 基础宽度
            selector: CSS选择器，为空时应用于整个样式
            
        Returns:
            更新后的样式表
        """
        import re
        # 计算新的宽度
        new_width = int(base_width * self.scale_factor)
        
        # 使用正则表达式替换宽度
        if selector:
            pattern = rf'{selector}\s*{{\s*[^}}]*width:\s*\d+px[^}}]*}}'
            if re.search(pattern, style):
                return re.sub(r'width:\s*\d+px', f'width: {new_width}px', style)
        else:
            pattern = r'width:\s*\d+px'
            if re.search(pattern, style):
                return re.sub(pattern, f'width: {new_width}px', style)
        
        return style
        
    def update_min_width_in_style(self, style, base_width, selector=""):
        """在样式表中更新最小宽度
        
        Args:
            style: 原始样式表
            base_width: 基础最小宽度
            selector: CSS选择器，为空时应用于整个样式
            
        Returns:
            更新后的样式表
        """
        import re
        # 计算新的最小宽度
        new_min_width = int(base_width * self.scale_factor)
        
        # 使用正则表达式替换最小宽度
        if selector:
            pattern = rf'{selector}\s*{{\s*[^}}]*min-width:\s*\d+px[^}}]*}}'
            if re.search(pattern, style):
                return re.sub(r'min-width:\s*\d+px', f'min-width: {new_min_width}px', style)
        else:
            pattern = r'min-width:\s*\d+px'
            if re.search(pattern, style):
                return re.sub(pattern, f'min-width: {new_min_width}px', style)
        
        return style


