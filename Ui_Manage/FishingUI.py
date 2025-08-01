import sys
import time
import logging
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QPushButton, QCheckBox, QSlider, QSpinBox,
                            QGroupBox, QMessageBox, QApplication)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient

from Ui_Manage.WindowManager import WinControl
from Ui_Manage.MinimizedWidget import MinimizedWidget
from config_manager import config_manager

logger = logging.getLogger(__name__)

class FishingUI(QMainWindow):
    """新的钓鱼自动化UI - 简洁可爱的蓝白主题"""
    
    # 信号定义
    start_signal = pyqtSignal()
    stop_signal = pyqtSignal()
    config_changed_signal = pyqtSignal(str, object)
    
    def __init__(self, fishing_bot=None, target_config=None, parent=None):
        super(FishingUI, self).__init__(parent)

        # 基本属性
        self.fishing_bot = fishing_bot
        self.is_running = False if not fishing_bot else fishing_bot.running
        self.target_count = 0  # 默认目标次数为0（无限）
        self.continuous_fishing = False  # 默认不开启连续钓鱼
        self.is_pinned = False
        
        # 窗口管理
        self.window_manager = WinControl()
        self.hwnd = None
        if target_config:
            self.hwnd = self.window_manager.find_target_window(target_config)
        
        # 最小化控件
        self.minimized_widget = MinimizedWidget()
        self.minimized_widget.toggle_fishing.connect(self.toggle_fishing)
        self.minimized_widget.expand_ui.connect(self.expand_from_minimized)
        
        # 遮罩层 (重用现有的OverlayMask)
        from Ui_Manage.OverlayMask import OverlayMask
        self.overlay_mask = OverlayMask()
        if self.hwnd:
            self.overlay_mask.set_game_hwnd(self.hwnd)
        if fishing_bot:
            self.overlay_mask.set_fishing_bot(fishing_bot)
        
        # 拖拽相关
        self._is_dragging = False
        self._drag_start_pos = None
        
        # 设置DPI缩放
        self.setup_dpi_scaling()
        
        # 初始化UI
        self.init_ui()
        
        # 状态更新定时器
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(200)

        # 窗口检测相关
        self.window_invalid = False  # 窗口是否无效
        self.last_window_check = 0   # 上次窗口检查时间
        
        logger.info("新钓鱼UI已初始化")
    
    def setup_dpi_scaling(self):
        """设置DPI缩放支持"""
        # DPI缩放需要在QApplication创建之前设置，这里只是占位
        # 实际的DPI设置应该在main.py中QApplication创建之前进行
        pass
    
    def init_ui(self):
        """初始化用户界面"""
        # 窗口基本设置
        self.setWindowTitle("钓鱼助手")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(320, 400)
        
        # 中央控件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)
        
        # 设置样式
        self.setup_styles()
        
        # 创建标题栏
        self.create_title_bar(main_layout)
        
        # 创建状态区域
        self.create_status_section(main_layout)
        
        # 创建控制区域
        self.create_control_section(main_layout)
        
        # 创建遮罩设置区域
        self.create_mask_section(main_layout)
        
        # 设置初始位置
        self.move(1550, 250)
    
    def setup_styles(self):
        """设置UI样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: rgba(240, 248, 255, 230);
                border-radius: 15px;
            }
            QWidget {
                background-color: transparent;
                color: #2c3e50;
                font-family: "Microsoft YaHei", "Segoe UI", Arial;
                font-size: 9pt;
            }
            QGroupBox {
                background-color: rgba(255, 255, 255, 180);
                border: 2px solid rgba(100, 150, 255, 100);
                border-radius: 10px;
                margin-top: 8px;
                padding-top: 5px;
                font-weight: bold;
                color: #34495e;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 8px;
                background-color: rgba(100, 150, 255, 200);
                color: white;
                border-radius: 4px;
            }
            QPushButton {
                background-color: rgba(100, 150, 255, 200);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: rgba(120, 170, 255, 230);
            }
            QPushButton:pressed {
                background-color: rgba(80, 130, 235, 200);
            }
            QPushButton:disabled {
                background-color: rgba(180, 180, 180, 150);
                color: rgba(255, 255, 255, 150);
            }
            QCheckBox {
                color: #2c3e50;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid rgba(100, 150, 255, 150);
                background-color: rgba(255, 255, 255, 200);
            }
            QCheckBox::indicator:checked {
                background-color: rgba(100, 150, 255, 200);
                border-color: rgba(80, 130, 235, 200);
            }
            QSlider::groove:horizontal {
                height: 6px;
                background-color: rgba(200, 200, 200, 150);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                height: 16px;
                background-color: rgba(100, 150, 255, 200);
                border-radius: 8px;
                margin: -5px 0;
            }
            QSlider::handle:horizontal:hover {
                background-color: rgba(120, 170, 255, 230);
            }
            QSpinBox {
                background-color: rgba(255, 255, 255, 200);
                border: 2px solid rgba(100, 150, 255, 100);
                border-radius: 4px;
                padding: 2px 4px;
                min-height: 16px;
            }
            QSpinBox:focus {
                border-color: rgba(100, 150, 255, 200);
            }
            QLabel {
                color: #2c3e50;
            }
        """)
    
    def create_title_bar(self, layout):
        """创建标题栏"""
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题
        self.title_label = QLabel("🎣钓鱼助手")
        self.title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 11pt;
                font-weight: bold;
                background-color: rgba(100, 150, 255, 200);
                border-radius: 8px;
                padding: 8px 9px;
            }
        """)
        self.title_label.setCursor(Qt.SizeAllCursor)
        title_layout.addWidget(self.title_label, 1)
        
        # 控制按钮
        self.create_control_buttons(title_layout)
        
        layout.addLayout(title_layout)
    
    def create_control_buttons(self, layout):
        """创建窗口控制按钮"""
        button_style = """
            QPushButton {
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                border-radius: 12px;
                font-size: 10pt;
                font-weight: bold;
                margin: 2px;
            }
        """
        
        # 置顶按钮
        self.pin_button = QPushButton("📌")
        self.pin_button.setStyleSheet(button_style + """
            QPushButton {
                background-color: rgba(255, 193, 7, 200);
            }
            QPushButton:hover {
                background-color: rgba(255, 213, 47, 230);
            }
        """)
        self.pin_button.setToolTip("置顶/取消置顶")
        self.pin_button.clicked.connect(self.toggle_pin)
        layout.addWidget(self.pin_button)
        
        # 最小化按钮
        self.minimize_button = QPushButton("−")
        self.minimize_button.setStyleSheet(button_style + """
            QPushButton {
                background-color: rgba(108, 117, 125, 200);
            }
            QPushButton:hover {
                background-color: rgba(128, 137, 145, 230);
            }
        """)
        self.minimize_button.setToolTip("最小化")
        self.minimize_button.clicked.connect(self.minimize_to_widget)
        layout.addWidget(self.minimize_button)
        
        # 关闭按钮
        self.close_button = QPushButton("×")
        self.close_button.setStyleSheet(button_style + """
            QPushButton {
                background-color: rgba(220, 53, 69, 200);
            }
            QPushButton:hover {
                background-color: rgba(240, 73, 89, 230);
            }
        """)
        self.close_button.setToolTip("关闭")
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button)

    def create_status_section(self, layout):
        """创建状态显示区域"""
        status_group = QGroupBox("状态信息")
        status_layout = QVBoxLayout(status_group)
        status_layout.setContentsMargins(8, 15, 8, 8)
        status_layout.setSpacing(4)

        # 当前状态
        self.status_label = QLabel("状态: 未开始")
        self.status_label.setStyleSheet("font-weight: bold; color: #34495e;")
        status_layout.addWidget(self.status_label)

        # 钓鱼次数
        self.count_label = QLabel("钓鱼次数: 0")
        self.count_label.setStyleSheet("color: #7f8c8d;")
        status_layout.addWidget(self.count_label)

        layout.addWidget(status_group)

    def create_control_section(self, layout):
        """创建控制区域"""
        control_group = QGroupBox("控制选项")
        control_layout = QVBoxLayout(control_group)
        control_layout.setContentsMargins(8, 15, 8, 8)
        control_layout.setSpacing(6)

        # 目标次数设置
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("目标次数:"))
        self.target_count_spin = QSpinBox()
        self.target_count_spin.setRange(0, 999)
        self.target_count_spin.setValue(self.target_count)
        self.target_count_spin.setToolTip("0表示无限次数")
        target_layout.addWidget(self.target_count_spin)
        control_layout.addLayout(target_layout)

        # 连续钓鱼选项
        self.continuous_fishing_check = QCheckBox("连续钓鱼")
        self.continuous_fishing_check.setChecked(self.continuous_fishing)
        self.continuous_fishing_check.setToolTip("开启后会自动重新抛竿")
        control_layout.addWidget(self.continuous_fishing_check)

        # 启动/停止切换按钮
        self.toggle_button = QPushButton("🎣 启动")
        self.toggle_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 167, 69, 200);
                font-size: 10pt;
                min-height: 28px;
                border-radius: 12px;         
                margin-bottom: 12px;             
            }
            QPushButton:hover {
                background-color: rgba(60, 187, 89, 230);
            }
            QPushButton:disabled {
                background-color: rgba(180, 180, 180, 150);
            }
        """)
        control_layout.addWidget(self.toggle_button)

        # 连接信号
        self.toggle_button.clicked.connect(self.on_toggle_click)

        layout.addWidget(control_group)

    def create_mask_section(self, layout):
        """创建遮罩设置区域"""
        mask_group = QGroupBox("遮罩设置")
        mask_layout = QVBoxLayout(mask_group)
        mask_layout.setContentsMargins(8, 15, 8, 8)
        mask_layout.setSpacing(6)

        # 遮罩透明度
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("透明度:"))
        self.mask_opacity_slider = QSlider(Qt.Horizontal)
        self.mask_opacity_slider.setRange(0, 100)
        self.mask_opacity_slider.setValue(30)
        self.mask_opacity_slider.valueChanged.connect(self.on_mask_opacity_changed)
        opacity_layout.addWidget(self.mask_opacity_slider)
        mask_layout.addLayout(opacity_layout)

        # 显示区域选项和刷新按钮
        areas_layout = QHBoxLayout()
        self.show_areas_check = QCheckBox("显示检测区域")
        self.show_areas_check.setChecked(True)
        self.show_areas_check.stateChanged.connect(self.on_show_areas_changed)
        areas_layout.addWidget(self.show_areas_check)

        self.refresh_button = QPushButton("🔄 刷新区域")
        self.refresh_button.clicked.connect(self.on_refresh_areas)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                min-width: 80px;
                max-width: 80px;
            }
        """)
        areas_layout.addWidget(self.refresh_button)
        mask_layout.addLayout(areas_layout)

        layout.addWidget(mask_group)

    # 事件处理方法
    def mousePressEvent(self, event):
        """鼠标按下事件 - 用于拖拽窗口"""
        if event.button() == Qt.LeftButton:
            # 检查是否点击在标题栏区域
            title_rect = self.title_label.geometry()
            if title_rect.contains(event.pos()):
                self._is_dragging = True
                self._drag_start_pos = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 拖拽窗口"""
        if self._is_dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            event.accept()

    # 窗口控制方法
    def toggle_pin(self):
        """切换置顶状态"""
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.pin_button.setText("📍")
            self.pin_button.setToolTip("取消置顶")
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.pin_button.setText("📌")
            self.pin_button.setToolTip("置顶")
        self.show()

    def minimize_to_widget(self):
        """最小化到小控件"""
        # 保存当前位置
        current_pos = self.pos()

        # 隐藏主窗口
        self.hide()

        # 显示最小化控件
        self.minimized_widget.show_at_position(current_pos.x() + 50, current_pos.y() + 50)

        # 更新最小化控件状态
        self.minimized_widget.set_fishing_state(self.is_running, self.get_fishing_count())

        logger.info("UI已最小化到小控件")

    def expand_from_minimized(self):
        """从最小化控件展开"""
        # 隐藏最小化控件
        self.minimized_widget.hide()

        # 显示主窗口
        self.show()
        self.raise_()
        self.activateWindow()

        logger.info("UI已从最小化控件展开")

    def toggle_fishing(self):
        """切换钓鱼状态（从最小化控件调用）"""
        self.on_toggle_click()

    # 控制按钮事件处理
    def on_toggle_click(self):
        """切换按钮点击事件"""
        if self.is_running:
            self.on_stop_click()
        else:
            self.on_start_click()

    def on_start_click(self):
        """启动按钮点击事件"""
        if self.fishing_bot:
            # 获取当前设置
            target_count = self.target_count_spin.value()
            continuous = self.continuous_fishing_check.isChecked()

            # 更新机器人设置
            self.fishing_bot.target_fishing_count = target_count
            self.fishing_bot.continuous_fishing = continuous

            # 发送启动信号
            self.start_signal.emit()
            logger.info(f"发送启动信号 - 目标次数: {target_count if target_count > 0 else '无限'}, 连续钓鱼: {'开启' if continuous else '关闭'}")

    def on_stop_click(self):
        """停止按钮点击事件"""
        if self.fishing_bot:
            # 发送停止信号
            self.stop_signal.emit()
            logger.info("发送停止信号")

    # 遮罩设置事件处理
    def on_mask_opacity_changed(self, value):
        """遮罩透明度改变事件"""
        if self.overlay_mask:
            self.overlay_mask.set_opacity(value)
            logger.debug(f"遮罩透明度设置为: {value}%")

    def on_show_areas_changed(self, state):
        """显示区域选项改变事件"""
        show_areas = state == Qt.Checked
        if self.overlay_mask:
            self.overlay_mask.set_show_ocr(show_areas)
            self.overlay_mask.set_show_area(show_areas)
            if show_areas:
                self.overlay_mask.show()
            else:
                self.overlay_mask.hide()
            logger.info(f"检测区域显示: {'开启' if show_areas else '关闭'}")

    def on_refresh_areas(self):
        """刷新区域按钮点击事件"""
        try:
            if self.overlay_mask and self.fishing_bot:
                # 重新从钓鱼机器人获取区域信息
                self.overlay_mask.set_fishing_bot(self.fishing_bot)
                # 更新遮罩位置
                self.overlay_mask.update_position()
                # 强制重绘
                self.overlay_mask.update()
                logger.info("已刷新检测区域")
            else:
                logger.warning("无法刷新区域：遮罩层或钓鱼机器人未初始化")
        except Exception as e:
            logger.error(f"刷新区域时出错: {e}")
            # 显示错误提示给用户
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "刷新失败", f"刷新检测区域时出错：{str(e)}")

    # 状态更新
    def update_status(self):
        """更新状态信息"""
        try:
            # 检查窗口句柄有效性
            current_time = time.time()
            should_check_window = False

            if not self.window_invalid:
                # 窗口正常时，每次都检查
                should_check_window = True
            else:
                # 窗口无效时，每10秒检查一次
                if current_time - self.last_window_check >= 10:
                    should_check_window = True

            if should_check_window:
                self.last_window_check = current_time
                window_valid = self._check_window_validity()

                if not window_valid and not self.window_invalid:
                    # 窗口刚变为无效
                    self.window_invalid = True
                    self.status_timer.stop()
                    self.status_timer.start(10000)  # 改为10秒检测一次
                    logger.warning("检测到窗口句柄无效，切换到10秒检测模式")
                elif window_valid and self.window_invalid:
                    # 窗口恢复有效
                    self.window_invalid = False
                    self.status_timer.stop()
                    self.status_timer.start(200)  # 恢复200ms检测
                    logger.info("窗口句柄恢复有效，切换到正常检测模式")

            if self.fishing_bot:
                # 更新运行状态
                self.is_running = self.fishing_bot.running

                # 更新切换按钮状态和文本
                self.toggle_button.setEnabled(not self.window_invalid)
                if self.is_running:
                    self.toggle_button.setText("⏹ 停止")
                    self.toggle_button.setStyleSheet("""
                        QPushButton {
                            background-color: rgba(220, 53, 69, 200);
                            font-size: 10pt;
                            min-height: 28px;
                        }
                        QPushButton:hover {
                            background-color: rgba(240, 73, 89, 230);
                        }
                        QPushButton:disabled {
                            background-color: rgba(180, 180, 180, 150);
                        }
                    """)
                else:
                    self.toggle_button.setText("🎣 启动")
                    self.toggle_button.setStyleSheet("""
                        QPushButton {
                            background-color: rgba(40, 167, 69, 200);
                            font-size: 10pt;
                            min-height: 28px;
                        }
                        QPushButton:hover {
                            background-color: rgba(60, 187, 89, 230);
                        }
                        QPushButton:disabled {
                            background-color: rgba(180, 180, 180, 150);
                        }
                    """)

                # 更新状态标签
                if self.window_invalid:
                    status_text = "❌ 请打开游戏后重启钓鱼助手"
                    self.status_label.setText(f"状态: {status_text}")
                    self.status_label.setStyleSheet("font-weight: bold; color: #e74c3c;")  # 红色
                else:
                    status_text = "🎣 运行中" if self.is_running else "⏸ 已停止"
                    self.status_label.setText(f"状态: {status_text}")
                    self.status_label.setStyleSheet("font-weight: bold; color: #34495e;")  # 恢复默认颜色

                # 更新钓鱼计数
                fishing_count = self.get_fishing_count()
                target_text = str(self.fishing_bot.target_fishing_count) if hasattr(self.fishing_bot, 'target_fishing_count') and self.fishing_bot.target_fishing_count > 0 else "无限"
                self.count_label.setText(f"钓鱼次数: {fishing_count}/{target_text}")

                # 更新最小化控件状态
                if self.minimized_widget.isVisible():
                    self.minimized_widget.set_fishing_state(self.is_running, fishing_count)

                # 更新遮罩位置（只在窗口有效时）
                if self.overlay_mask and not self.window_invalid:
                    self.overlay_mask.update_position()

        except Exception as e:
            logger.error(f"更新状态出错: {e}")

    def get_fishing_count(self):
        """获取钓鱼次数"""
        if self.fishing_bot and hasattr(self.fishing_bot, 'state_handler'):
            return self.fishing_bot.state_handler.get_fishing_count()
        return 0

    def _check_window_validity(self):
        """检查窗口句柄有效性"""
        if not self.hwnd:
            return False
        return self.window_manager.is_window_valid(self.hwnd)

    # 窗口事件
    def closeEvent(self, event):
        """关闭事件"""
        if self.fishing_bot and self.fishing_bot.running:
            # 显示确认对话框
            reply = QMessageBox.question(
                self,
                "确认退出",
                "钓鱼机器人正在运行，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.fishing_bot.stop()
            else:
                event.ignore()
                return

        # 关闭遮罩层和最小化控件
        if self.overlay_mask:
            self.overlay_mask.close()
        if self.minimized_widget:
            self.minimized_widget.close()

        super(FishingUI, self).closeEvent(event)
        logger.info("钓鱼UI已关闭")
