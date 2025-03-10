import os
import sys
import threading

from PyQt5.QtCore import QObject, pyqtSignal, QTimer

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_fishing import AutoFishing
from FishingOverlay import FishingOverlay

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
        
        # 创建自动钓鱼实例
        self.auto_fishing = AutoFishing()
        
        # 创建覆盖层UI
        self.overlay = FishingOverlay()
        
        # 连接信号
        self.overlay.start_signal.connect(self.start_fishing)
        self.overlay.stop_signal.connect(self.stop_fishing)
        self.progress_updated.connect(self.overlay.update_fishing_progress)
        self.log_message.connect(self.overlay.add_log)
        
        # 状态变量
        self.fishing_thread = None
        self.is_fishing = False
        self.progress_timer = None
        
        # 初始化进度更新定时器
        self.setup_progress_timer()
        
    def setup_progress_timer(self):
        """设置进度更新定时器"""
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_progress)
        self.progress_timer.setInterval(500)  # 每500毫秒更新一次
    
    def start_fishing(self):
        """开始钓鱼"""
        if self.is_fishing:
            return
            
        self.is_fishing = True
        self.log_message.emit("正在启动自动钓鱼...")
        
        # 启动钓鱼线程
        self.fishing_thread = threading.Thread(target=self.fishing_thread_func)
        self.fishing_thread.daemon = True
        self.fishing_thread.start()
        
        # 启动进度更新定时器
        self.progress_timer.start()
    
    def stop_fishing(self):
        """停止钓鱼"""
        if not self.is_fishing:
            return
            
        self.is_fishing = False
        self.log_message.emit("正在停止自动钓鱼...")
        
        # 停止自动钓鱼
        self.auto_fishing.stop_flag = True
        self.auto_fishing.reset_flag = True
        
        # 等待钓鱼线程结束
        if self.fishing_thread and self.fishing_thread.is_alive():
            self.fishing_thread.join(timeout=2)
        
        # 停止进度更新定时器
        self.progress_timer.stop()
        
        # 重置进度
        self.progress_updated.emit(0, "已停止")
        self.log_message.emit("自动钓鱼已停止")
    
    def fishing_thread_func(self):
        """钓鱼线程函数"""
        try:
            # 重置钓鱼状态
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
            status = "钓鱼完成！等待下次右键"
            progress = 100
        elif hasattr(self.auto_fishing, 'reeling') and self.auto_fishing.reeling:
            status = "正在收线..."
            progress = 85
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
        else:
            status = "等待开始钓鱼..."
            progress = 10
            
        # 发送进度更新信号
        self.progress_updated.emit(progress, status)
    
    def show(self):
        """显示覆盖层UI"""
        self.overlay.show()
    
    def close(self):
        """关闭适配器"""
        self.stop_fishing()
        self.overlay.close()

def main():
    """主函数"""
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 创建钓鱼适配器
    adapter = FishingAdapter()
    adapter.show()
    
    # 添加初始日志
    adapter.log_message.emit("钓鱼助手已启动")
    adapter.log_message.emit("请点击'开始钓鱼'按钮开始")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 