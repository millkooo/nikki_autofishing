import sys
import logging
import math
import time
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient, QRadialGradient, QPainterPath

logger = logging.getLogger(__name__)

class MinimizedWidget(QWidget):
    """最小化后的小控件"""

    # 信号定义
    toggle_fishing = pyqtSignal()  # 切换钓鱼状态
    expand_ui = pyqtSignal()       # 展开完整UI

    def __init__(self, parent=None):
        super(MinimizedWidget, self).__init__(parent)

        # 窗口设置
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 状态变量
        self.is_fishing = False
        self.fishing_count = 0
        self.hover_state = False
        self.click_animation = False

        # 设置固定大小 - 方形设计
        self.setFixedSize(85, 85)

        # 动画效果
        self.setup_animations()

        # 更新定时器 - 只在需要动画时运行
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        # 不自动启动，只在需要动画时启动

        # 点击动画定时器
        self.click_timer = QTimer()
        self.click_timer.timeout.connect(self.reset_click_animation)
        self.click_timer.setSingleShot(True)

        # 设置工具提示
        self.setToolTip("🎣 钓鱼助手\n左键: 开始/停止钓鱼\n右键: 展开完整界面")

        logger.info("最小化控件已初始化")
    
    def setup_animations(self):
        """设置动画效果"""
        self.animation_progress = 0.0  # 动画进度 (0-1)
        self.animation_active = False  # 是否正在播放动画
        self.animation_type = None     # 动画类型
        self.animation_duration = 0    # 动画持续时间
        self.animation_start_time = 0  # 动画开始时间

    def set_fishing_state(self, is_fishing, count=0):
        """设置钓鱼状态"""
        old_fishing = self.is_fishing
        self.is_fishing = is_fishing
        self.fishing_count = count

        # 状态改变时触发动画
        if old_fishing != is_fishing:
            self.start_state_change_animation()

        self.update()

    def start_state_change_animation(self):
        """启动状态改变动画"""
        self.animation_active = True
        self.animation_progress = 0.0
        self.animation_type = "state_change"
        self.animation_duration = 800  # 800ms动画
        self.animation_start_time = time.time() * 1000

        # 启动定时器
        self.update_timer.start(16)  # 60fps

    def start_click_animation(self):
        """启动点击动画"""
        self.animation_active = True
        self.animation_progress = 0.0
        self.animation_type = "click"
        self.animation_duration = 300  # 300ms动画
        self.animation_start_time = time.time() * 1000

        # 启动定时器
        self.update_timer.start(16)  # 60fps

    def update_display(self):
        """更新显示动画"""
        if not self.animation_active:
            return

        current_time = time.time() * 1000
        elapsed = current_time - self.animation_start_time

        if elapsed >= self.animation_duration:
            # 动画结束
            self.animation_active = False
            self.animation_progress = 1.0
            self.update_timer.stop()  # 停止定时器
        else:
            # 计算动画进度 (使用缓动函数)
            progress = elapsed / self.animation_duration
            # 使用ease-out-cubic缓动
            self.animation_progress = 1 - pow(1 - progress, 3)

        self.update()
    
    def paintEvent(self, event):
        """绘制事件 - 方形现代化设计"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # 计算绘制区域 - 方形
        rect = self.rect().adjusted(6, 6, -6, -6)
        center = rect.center()

        # 绘制阴影效果
        self.draw_shadow(painter, rect)

        # 绘制主背景
        self.draw_background(painter, rect)

        # 绘制状态图标
        self.draw_status_icon(painter, center)

        # 绘制钓鱼次数
        self.draw_fishing_count(painter, rect)

        # 绘制动画效果
        self.draw_animation_effects(painter, rect)

        # 绘制悬停效果
        self.draw_interaction_effects(painter, rect)

    def draw_shadow(self, painter, rect):
        """绘制阴影效果 - 方形"""
        shadow_rect = rect.adjusted(-3, -3, 3, 3)

        # 绘制阴影
        painter.setBrush(QBrush(QColor(0, 0, 0, 40)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(shadow_rect, 8, 8)

    def draw_background(self, painter, rect):
        """绘制背景 - 方形渐变"""
        base_alpha = 230

        # 动画效果调整透明度
        if self.animation_active and self.animation_type == "state_change":
            # 状态改变动画：透明度波动
            wave = math.sin(self.animation_progress * math.pi * 2) * 0.3
            alpha = int(base_alpha + wave * 50)
        else:
            alpha = base_alpha

        # 创建渐变背景
        if self.is_fishing:
            # 运行状态 - 绿色系渐变
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0, QColor(46, 204, 113, alpha))   # 翠绿色
            gradient.setColorAt(0.5, QColor(39, 174, 96, alpha))  # 深绿色
            gradient.setColorAt(1, QColor(34, 153, 84, alpha))    # 更深绿色
        else:
            # 停止状态 - 蓝灰色渐变
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0, QColor(149, 165, 166, alpha))
            gradient.setColorAt(0.5, QColor(127, 140, 141, alpha))
            gradient.setColorAt(1, QColor(108, 122, 137, alpha))

        # 绘制主方形背景
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 160), 2))
        painter.drawRoundedRect(rect, 12, 12)
    
    def draw_status_icon(self, painter, center):
        """绘制状态图标"""
        painter.save()

        # 设置图标颜色
        icon_color = QColor(255, 255, 255, 250)
        painter.setPen(QPen(icon_color, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(QBrush(icon_color))

        # 动画缩放效果
        scale = 1.0
        if self.animation_active and self.animation_type == "click":
            scale = 1.0 + self.animation_progress * 0.2  # 最大放大20%
        elif self.animation_active and self.animation_type == "state_change":
            # 状态改变时的弹跳效果
            bounce = math.sin(self.animation_progress * math.pi) * 0.15
            scale = 1.0 + bounce

        painter.translate(center)
        painter.scale(scale, scale)

        if self.is_fishing:
            # 运行状态 - 绘制停止方块
            stop_size = 12
            painter.setBrush(QBrush(icon_color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(-stop_size//2, -stop_size//2, stop_size, stop_size, 2, 2)

        else:
            # 停止状态 - 绘制播放三角形
            from PyQt5.QtCore import QPoint
            from PyQt5.QtGui import QPolygon

            points = QPolygon([
                QPoint(-8, -10),
                QPoint(10, 0),
                QPoint(-8, 10)
            ])
            painter.drawPolygon(points)

        painter.restore()

    def draw_fishing_count(self, painter, rect):
        """绘制钓鱼次数"""
        if self.fishing_count > 0:
            # 计算数字显示位置 - 右下角
            badge_size = 22
            count_rect = QRect(rect.right() - badge_size + 3, rect.bottom() - badge_size + 3, badge_size, badge_size)

            # 动画缩放效果
            scale = 1.0
            if self.animation_active and self.animation_type == "state_change":
                # 数字更新时的弹跳效果
                bounce = math.sin(self.animation_progress * math.pi * 2) * 0.1
                scale = 1.0 + bounce

            painter.save()
            painter.translate(count_rect.center())
            painter.scale(scale, scale)

            # 绘制数字背景圆圈
            badge_rect = QRect(-badge_size//2, -badge_size//2, badge_size, badge_size)
            painter.setBrush(QBrush(QColor(231, 76, 60, 220)))  # 红色背景
            painter.setPen(QPen(QColor(255, 255, 255, 180), 2))
            painter.drawEllipse(badge_rect)

            # 绘制数字
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.setPen(QPen(QColor(255, 255, 255)))
            count_text = str(min(self.fishing_count, 99))  # 最多显示99
            if self.fishing_count > 99:
                count_text = "99+"
            painter.drawText(badge_rect, Qt.AlignCenter, count_text)

            painter.restore()

    def draw_animation_effects(self, painter, rect):
        """绘制动画效果"""
        if not self.animation_active:
            return

        if self.animation_type == "state_change":
            # 状态改变时的光环效果
            ring_alpha = int((1.0 - self.animation_progress) * 100)
            ring_width = 2 + self.animation_progress * 4

            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, ring_alpha), ring_width))

            # 绘制扩散的光环
            ring_rect = rect.adjusted(-int(self.animation_progress * 8), -int(self.animation_progress * 8),
                                    int(self.animation_progress * 8), int(self.animation_progress * 8))
            painter.drawRoundedRect(ring_rect, 12, 12)

        elif self.animation_type == "click":
            # 点击时的波纹效果
            ripple_alpha = int((1.0 - self.animation_progress) * 80)
            ripple_size = int(self.animation_progress * 15)

            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, ripple_alpha), 2))

            ripple_rect = rect.adjusted(-ripple_size, -ripple_size, ripple_size, ripple_size)
            painter.drawRoundedRect(ripple_rect, 12, 12)

    def draw_interaction_effects(self, painter, rect):
        """绘制交互效果"""
        # 悬停效果
        if self.hover_state:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, 100), 2))
            hover_rect = rect.adjusted(-2, -2, 2, 2)
            painter.drawRoundedRect(hover_rect, 14, 14)

    def reset_click_animation(self):
        """重置点击动画"""
        self.click_animation = False
        self.update()

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        # 触发点击动画
        self.start_click_animation()

        if event.button() == Qt.LeftButton:
            # 左键切换钓鱼状态
            self.toggle_fishing.emit()
            logger.info("方形控件: 切换钓鱼状态")
        elif event.button() == Qt.RightButton:
            # 右键展开UI
            self.expand_ui.emit()
            logger.info("方形控件: 展开完整UI")

    def enterEvent(self, event):
        """鼠标进入事件"""
        self.hover_state = True
        self.update()

    def leaveEvent(self, event):
        """鼠标离开事件"""
        self.hover_state = False
        self.update()

    def show_at_position(self, x, y):
        """在指定位置显示"""
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        logger.info(f"方形控件显示在位置: ({x}, {y})")
