import os
import sys
import threading
import time
import traceback
import win32gui

from PyQt5.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QPainter, QPen, QColor

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_fishing import AutoFishing
from FishingOverlay import FishingOverlay
from Ui_Manage.WindowManager import WinControl
from controller.MouseController import mouse
from Ui_Manage.TransparentOverlay import TransparentOverlay

class FishingAdapter(QObject):
    """
    钓鱼适配器类，用于连接AutoFishing和FishingOverlay
    
    这个类作为中间层，将AutoFishing的功能与FishingOverlay的UI连接起来，
    处理信号传递、状态更新和线程管理。
    """
    
    # 定义信号
    progress_updated = pyqtSignal(int, str)
    log_message = pyqtSignal(str)
    
    def __init__(self):
        """初始化钓鱼适配器"""
        super(FishingAdapter, self).__init__()
        
        # 创建覆盖层UI
        self.overlay = FishingOverlay()
        
        # 连接信号
        self.overlay.start_signal.connect(self.start_fishing)
        self.overlay.stop_signal.connect(self.stop_fishing)
        self.overlay.fishing_mode_changed.connect(self.on_fishing_mode_changed)  # 连接钓鱼模式变更信号
        self.overlay.show_region_signal.connect(self.on_show_region_changed)  # 连接新的信号
        self.progress_updated.connect(self.overlay.update_fishing_progress)
        self.log_message.connect(self.overlay.add_log)
        
        # 状态变量
        self.fishing_thread = None
        self.is_fishing = False
        self.progress_timer = None
        self.fishing_mode = 0  # 0: 单次钓鱼, 1: 自动钓鱼2次, 2: 自动钓鱼3次
        self.auto_fishing_count = 0  # 自动钓鱼计数
        self.max_auto_fishing_count = 3  # 最大自动钓鱼次数
        self.auto_fishing_timer = None  # 自动钓鱼定时器
        self._last_fish_caught = False  # 上次钓鱼是否完成的标志
        
        # 检测区域窗口
        self.region_window = None
        
        # 初始化进度更新定时器
        self.setup_progress_timer()
        
        # 创建自动钓鱼实例
        try:
            self.auto_fishing = AutoFishing()
            self.target_hwnd_valid = True
        except Exception as e:
            self.target_hwnd_valid = False
            self.log_message.emit(f"初始化错误: {str(e)}")
            self.log_message.emit("请确保游戏已经启动，然后重新启动工具")
            # 禁用开始按钮
            self.overlay.start_button.setEnabled(False)
            # 显示错误提示
            self.overlay.info_label.setText("错误: 未找到游戏窗口，请先启动游戏")
            self.overlay.info_label.setStyleSheet("color: red; font-size: 16px; background-color: rgba(0, 0, 0, 100); padding: 5px;")
        
    def setup_progress_timer(self):
        """设置进度更新定时器"""
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_progress)
        self.progress_timer.setInterval(500)  # 每500毫秒更新一次
    
    def on_fishing_mode_changed(self, mode):
        """钓鱼模式变更处理"""
        self.fishing_mode = mode
        mode_name = '单次钓鱼' if mode == 0 else '钓鱼2次' if mode == 1 else '钓鱼3次'
        self.log_message.emit(f"钓鱼模式已设置为: {mode_name}")
        print(f"[DEBUG] 当前模式ID: {mode}, 模式名称: {mode_name}")
        
        # 如果正在钓鱼，停止当前钓鱼
        if self.is_fishing:
            self.log_message.emit("由于模式变更，停止当前钓鱼")
            self.stop_fishing()
    
    def start_fishing(self):
        """开始钓鱼"""
        if self.is_fishing:
            print("[DEBUG] 已经在钓鱼中，忽略开始请求")
            return
            
        # 检查目标窗口是否有效
        if not hasattr(self, 'target_hwnd_valid') or not self.target_hwnd_valid:
            self.log_message.emit("错误: 未找到游戏窗口，无法开始钓鱼")
            QMessageBox.warning(self.overlay, "错误", "未找到游戏窗口，请先启动游戏，然后重新启动工具")
            return
            
        self.is_fishing = True
        self._last_fish_caught = False  # 重置钓鱼完成标志
        mode_name = '单次钓鱼' if self.fishing_mode == 0 else '钓鱼2次' if self.fishing_mode == 1 else '钓鱼3次'
        self.log_message.emit(f"正在启动自动钓鱼... 当前模式: {mode_name}")
        
        # 重置自动钓鱼计数
        if self.fishing_mode == 1:  # 自动钓鱼2次模式
            self.auto_fishing_count = 1
            self.max_auto_fishing_count = 2  # 设置最大钓鱼次数为2
            self.log_message.emit(f"自动钓鱼模式: 第{self.auto_fishing_count}次/{self.max_auto_fishing_count}次")
            print(f"[DEBUG] 自动钓鱼流程: 等待手动点击右键开始第一次钓鱼")
        elif self.fishing_mode == 2:  # 自动钓鱼3次模式
            self.auto_fishing_count = 1
            self.max_auto_fishing_count = 3  # 设置最大钓鱼次数为3
            self.log_message.emit(f"自动钓鱼模式: 第{self.auto_fishing_count}次/{self.max_auto_fishing_count}次")
            print(f"[DEBUG] 自动钓鱼流程: 等待手动点击右键开始第一次钓鱼")
        
        # 启动钓鱼线程
        self.fishing_thread = threading.Thread(target=self.fishing_thread_func)
        self.fishing_thread.daemon = True
        self.fishing_thread.start()
        print(f"[DEBUG] 钓鱼线程已启动: {self.fishing_thread.name}")
        
        # 启动进度更新定时器
        if not self.progress_timer.isActive():
            self.progress_timer.start()
            print("[DEBUG] 进度更新定时器已启动")
    
    def stop_fishing(self):
        """停止钓鱼"""
        if not self.is_fishing:
            self.log_message.emit("当前没有钓鱼活动，忽略停止请求")
            return
            
        self.is_fishing = False
        self.log_message.emit("正在停止自动钓鱼...")
        
        # 停止自动钓鱼
        if hasattr(self, 'auto_fishing'):
            self.auto_fishing.stop_flag = True
            self.auto_fishing.reset_flag = True
            self.auto_fishing.fishing = False  # 重置钓鱼状态
            self.log_message.emit("已设置钓鱼停止标志")
        
        # 停止自动钓鱼定时器
        if self.auto_fishing_timer and self.auto_fishing_timer.isActive():
            self.auto_fishing_timer.stop()
            self.log_message.emit("已停止自动钓鱼定时器")
        
        # 重置自动钓鱼计数
        old_count = self.auto_fishing_count
        self.auto_fishing_count = 0
        self._last_fish_caught = False  # 重置钓鱼完成标志
        # 根据当前模式重置最大钓鱼次数
        if self.fishing_mode == 1:
            self.max_auto_fishing_count = 2
        elif self.fishing_mode == 2:
            self.max_auto_fishing_count = 3
        if old_count > 0:
            self.log_message.emit(f"已重置自动钓鱼计数: {old_count} -> 0")
        
        # 等待钓鱼线程结束
        if self.fishing_thread and self.fishing_thread.is_alive():
            self.log_message.emit("等待钓鱼线程结束...")
            self.fishing_thread.join(timeout=2)
            if self.fishing_thread.is_alive():
                self.log_message.emit("钓鱼线程未在2秒内结束，继续执行")
            else:
                self.log_message.emit("钓鱼线程已结束")
        
        # 停止进度更新定时器
        self.progress_timer.stop()
        self.log_message.emit("已停止进度更新定时器")
        
        # 重置进度
        self.progress_updated.emit(0, "已停止")
        self.log_message.emit("自动钓鱼已停止")
    
    def fishing_thread_func(self):
        """钓鱼线程函数"""
        try:
            # 重置钓鱼状态，但保留fishing状态
            self.auto_fishing.reset()
            # 启动自动钓鱼
            self.auto_fishing.start()
        except Exception as e:
            self.log_message.emit(f"钓鱼过程出错: {str(e)}")
        finally:
            self.is_fishing = False
            self.progress_updated.emit(0, "已完成")
            self.log_message.emit("钓鱼线程已结束")
    
    def update_progress(self):
        """更新钓鱼进度"""
        if not self.is_fishing:
            return
            
        # 获取当前钓鱼状态
        if hasattr(self.auto_fishing, 'fish_caught') and self.auto_fishing.fish_caught:
            status = "钓鱼完成！等待手动开始下一次"
            progress = 100
            self.progress_updated.emit(progress, status)
            
            # 避免重复处理钓鱼完成事件
            if not hasattr(self, '_last_fish_caught') or not self._last_fish_caught:
                self._last_fish_caught = True
                self.log_message.emit("钓鱼完成！")
                
                # 记录当前状态的详细信息
                self.log_message.emit(f"当前钓鱼模式: {self.fishing_mode} ({'单次钓鱼' if self.fishing_mode == 0 else '钓鱼2次' if self.fishing_mode == 1 else '钓鱼3次'})")
                self.log_message.emit(f"当前钓鱼计数: {self.auto_fishing_count}/{self.max_auto_fishing_count}")
                
                # 如果是自动钓鱼模式，且当前钓鱼次数小于最大次数，则自动开始下一次钓鱼
                if (self.fishing_mode == 1 or self.fishing_mode == 2) and self.auto_fishing_count < self.max_auto_fishing_count:
                    self.auto_fishing_count += 1
                    self.log_message.emit(f"自动钓鱼进度: 第{self.auto_fishing_count}次/{self.max_auto_fishing_count}次")
                    
                    # 等待4秒后自动开始下一次钓鱼
                    if self.auto_fishing_timer is None:
                        self.auto_fishing_timer = QTimer()
                        self.auto_fishing_timer.setSingleShot(True)
                        self.auto_fishing_timer.timeout.connect(self.auto_start_next_fishing)
                        self.log_message.emit("已创建自动钓鱼定时器")
                    
                    self.auto_fishing_timer.start(4000)  # 4秒后自动开始下一次钓鱼
                    self.log_message.emit("等待4秒后自动开始下一次钓鱼...")
                    self.log_message.emit(f"定时器状态: {'活动' if self.auto_fishing_timer.isActive() else '非活动'}, 剩余时间: 约4秒")
                elif (self.fishing_mode == 1 or self.fishing_mode == 2) and self.auto_fishing_count >= self.max_auto_fishing_count:
                    self.log_message.emit(f"已完成{self.max_auto_fishing_count}次自动钓鱼，等待手动开始新一轮")
                    self.log_message.emit("请点击右键开始新一轮自动钓鱼")
                    self.auto_fishing_count = 1  # 重置计数
                    self.log_message.emit("已重置自动钓鱼计数为1")
        else:
            # 重置钓鱼完成标志
            self._last_fish_caught = False
            
            if hasattr(self.auto_fishing, 'reeling') and self.auto_fishing.reeling:
                status = "正在收线..."
                progress = 85
                self.progress_updated.emit(progress, status)
            elif hasattr(self.auto_fishing, 'fishing') and self.auto_fishing.fishing:
                if hasattr(self.auto_fishing, 'current_area') and hasattr(self.auto_fishing, 'initial_area'):
                    if self.auto_fishing.current_area > self.auto_fishing.base_thresholds["fish_hook"]:
                        status = "正在溜鱼..."
                        progress = 50
                    else:
                        status = "等待鱼上钩..."
                        progress = 30
                else:
                    status = "等待鱼上钩..."
                    progress = 30
                self.progress_updated.emit(progress, status)
            else:
                status = "等待开始钓鱼..."
                progress = 10
                self.progress_updated.emit(progress, status)
    
    def auto_start_next_fishing(self):
        """自动开始下一次钓鱼"""
        if not self.is_fishing:
            print("[DEBUG] 当前不在钓鱼状态，取消自动开始下一次钓鱼")
            return
            
        self.log_message.emit(f"自动开始第{self.auto_fishing_count}次钓鱼...")
        
        # 模拟右键点击
        if hasattr(self, 'auto_fishing'):
            try:
                # 首先重置钓鱼状态，但保持fishing为True
                print("[DEBUG] 重置钓鱼状态，准备下一次钓鱼")
                self.auto_fishing.fish_caught = False
                self.auto_fishing.reeling = False
                
                # 直接使用mouse.click_right模拟右键点击
                mouse.click_right(0.2)  # 按住右键0.2秒
                print("[DEBUG] 已使用mouse.click_right(0.2)模拟右键点击")
                
                # 确保钓鱼状态正确
                self.auto_fishing.fishing = True
                print(f"[DEBUG] 钓鱼状态已设置: fishing={self.auto_fishing.fishing}, fish_caught={self.auto_fishing.fish_caught}, reeling={self.auto_fishing.reeling}")
            except Exception as e:
                print(f"[ERROR] 模拟右键点击出错: {str(e)}")
                print(f"[ERROR] 错误详情: {traceback.format_exc()}")
        else:
            print("[ERROR] 错误: 自动钓鱼实例不存在，无法模拟右键点击")
    
    def show(self):
        """显示覆盖层UI"""
        self.overlay.show()
    
    def close(self):
        """关闭适配器"""
        self.stop_fishing()
        if hasattr(self, 'keyboard'):
            self.keyboard.close()
        self.overlay.close()

    def on_show_region_changed(self, show):
        """处理显示/隐藏检测区域的变更
        
        Args:
            show: 是否显示检测区域
        """
        if show:
            if not self.region_window:
                # 创建一个新的透明窗口来显示区域
                self.region_window = TransparentOverlay()
                self.region_window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
                self.region_window.setAttribute(Qt.WA_TranslucentBackground)
                self.region_window.setAttribute(Qt.WA_TransparentForMouseEvents, True)  # 鼠标穿透
                
                # 获取游戏窗口位置和大小
                if hasattr(self, 'auto_fishing') and hasattr(self.auto_fishing, 'target_hwnd'):
                    rect = win32gui.GetWindowRect(self.auto_fishing.target_hwnd)
                    # 从配置文件获取检测区域参数
                    region = self.auto_fishing.config["fishing"]["region"]
                    scaled_region = self.auto_fishing._calculate_scaled_region(
                        region["x_offset"],
                        region["y_offset"],
                        region["width"],
                        region["height"]
                    )
                    
                    # 设置窗口位置和大小
                    x = rect[0] + scaled_region['x_offset']
                    y = rect[1] + scaled_region['y_offset']
                    width = scaled_region['width']
                    height = scaled_region['height']
                    
                    self.region_window.setGeometry(x, y, width, height)
                    
                    # 重写paintEvent来绘制边框和文字
                    def paintEvent(event):
                        painter = QPainter(self.region_window)
                        painter.setRenderHint(QPainter.Antialiasing)
                        
                        # 设置画笔
                        pen = QPen(QColor(255, 255, 0))  # 黄色
                        pen.setWidth(2)
                        painter.setPen(pen)
                        
                        # 绘制矩形
                        painter.drawRect(self.region_window.rect().adjusted(1, 1, -1, -1))
                        
                        # 绘制黄色文本（基本使用说明）
                        painter.setPen(QPen(QColor(255, 255, 0)))  # 黄色文字
                        font = painter.font()
                        font.setPointSize(12)  # 设置字体大小
                        painter.setFont(font)
                        text = "使用时请确认鱼始终在此框内\n"
                        text += "开始钓鱼前请关闭此框\n"
                        text += "配置文件可以调整位置，如果位置不合适，可自行调整"
                        text += "\n如果鱼在框内，但一直显示等待鱼上钩，请调整判定阈值\n\n\n\n\n\n\n\n\n\n\n"


                        # 计算黄色文本的矩形区域（在上半部分）
                        rect = self.region_window.rect()
                        yellow_rect = rect.adjusted(10, 10, -10, rect.height() // 2)
                        painter.drawText(yellow_rect, Qt.AlignCenter, text)

                        # 绘制红色文本（错误提示）
                        painter.setPen(QPen(QColor(255, 0, 0)))  # 红色
                        font.setPointSize(14)  # 设置字体大小
                        painter.setFont(font)

                        text1 = "\n如果不知道这是什么又可以正常使用请关闭并无视"
                        
                        # 计算红色文本的矩形区域（在下半部分）
                        red_rect = rect.adjusted(10, rect.height() // 2, -10, -10)
                        painter.drawText(red_rect, Qt.AlignCenter, text1)

                    self.region_window.paintEvent = paintEvent
                    self.region_window.show()
        else:
            if self.region_window:
                self.region_window.close()
                self.region_window = None

def main():
    """主函数"""
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 创建钓鱼适配器
    adapter = FishingAdapter()
    adapter.show()
    
    # 添加初始日志
    adapter.log_message.emit("钓鱼助手已启动")
    if hasattr(adapter, 'target_hwnd_valid') and adapter.target_hwnd_valid:
        adapter.log_message.emit("请点击'开始钓鱼'按钮开始")
    else:
        adapter.log_message.emit("错误: 未找到游戏窗口，请先启动游戏")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 