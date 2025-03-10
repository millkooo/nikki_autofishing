import json
import os
import sys
import threading
import time

import cv2
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Ui_Manage.WindowManager import WinControl
from capture.img_processor import ImageProcessor
from controller.MouseController import mouse
from controller.KeyboardController import get_input_handler

# 读取配置文件
def load_config():
    """从JSON文件加载配置"""
    try:
        # 获取配置文件路径
        try:
            # PyInstaller创建临时文件夹,将路径存储在_MEIPASS中
            base_path = sys._MEIPASS
            config_path = os.path.join(base_path, 'config.json')
        except Exception:
            # 如果不是打包的情况,就使用当前文件的目录
            base_path = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_path, 'config.json')
            
        if not os.path.exists(config_path):
            print(f"配置文件不存在: {config_path}")
            sys.exit(1)
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        print(f"成功加载配置文件: {config_path}")
        return config
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        sys.exit(1)

class AutoFishing:
    def __init__(self):
        # 加载配置
        self.config = load_config()
        
        # 初始化窗口和控制器
        self.target_hwnd = WinControl.find_target_window(self.config["window"])
        self.image_processor = ImageProcessor(self.target_hwnd)
        self.input_handler = get_input_handler()
        
        # 获取屏幕分辨率和缩放比例
        self.window_width = self.image_processor.window_width
        self.window_height = self.image_processor.window_height
        self.scale_factor = WinControl.get_scaling_factor(self.target_hwnd)
        
        # 计算基于1080p的缩放比例
        self.width_ratio = self.window_width / 1920
        self.height_ratio = self.window_height / 1080
        print(f"屏幕分辨率: {self.window_width}x{self.window_height}, 缩放比例: {self.scale_factor}")
        print(f"宽度比例: {self.width_ratio}, 高度比例: {self.height_ratio}")
        
        # 计算面积阈值的缩放因子
        self.area_scale_factor = self._calculate_area_scale_factor()
        print(f"面积缩放因子: {self.area_scale_factor}")
        
        # 基准阈值（1080p分辨率下的值）
        self.base_thresholds = {
            "fish_hook": 200,      # 鱼上钩判断阈值
            "near_zero_1": 5,      # 面积接近0判断阈值1
            "near_zero_2": 30,     # 面积接近0判断阈值2
            "area_decrease": 20,   # 有效面积减少判断阈值
            "reel_complete": 50,   # 收线完成判断阈值
            "area_ratio": 0.95     # 面积增大需要继续拉鱼的判断比例
        }
        
        # 颜色范围参数 - 用于检测钓鱼进度
        self.lower = np.array([22, 54, 250])
        self.upper = np.array([25, 88, 255])
        
        # 形态学操作内核
        self.kernel = np.ones((5, 5), np.uint8)
        
        # 钓鱼状态变量
        self.fishing = False
        self.initial_area = 0
        self.current_area = 0
        self.last_area = 0
        self.fish_caught = False
        self.reeling = False
        self.stop_flag = False
        self.reset_flag = False
        
        # 创建线程锁
        self.lock = threading.Lock()
        
        # 创建监控线程
        self.monitor_thread = None
        
        # 设置键盘监听
        self._setup_keyboard_listener()
    
    def _calculate_area_scale_factor(self):
        """计算面积阈值的缩放因子
        面积是二维的，所以使用宽度和高度比例的乘积作为缩放因子
        """
        return self.width_ratio * self.height_ratio
    
    def _get_scaled_threshold(self, threshold_name):
        """获取缩放后的阈值"""
        base_value = self.base_thresholds[threshold_name]
        # 对于比例值，不需要缩放
        if threshold_name == "area_ratio":
            return base_value
        # 对于面积阈值，使用面积缩放因子
        return base_value * self.area_scale_factor
    
    def _calculate_scaled_region(self, base_x, base_y, base_width, base_height):
        """根据屏幕分辨率计算缩放后的区域参数"""
        x_offset = int(base_x * self.width_ratio)
        y_offset = int(base_y * self.height_ratio)
        width = int(base_width * self.width_ratio)
        height = int(base_height * self.height_ratio)
        
        return {
            "x_offset": x_offset,
            "y_offset": y_offset,
            "width": width,
            "height": height
        }
    
    def _setup_keyboard_listener(self):
        """设置键盘监听器"""
        from pynput.keyboard import Listener

        def on_press(key):
            try:
                if key.char.lower() == 'q':
                    print("检测到Q键按下，返回初始状态...")
                    self.reset_flag = True
            except AttributeError:
                pass  # 特殊键不处理
        
        # 启动键盘监听
        self.keyboard_listener = Listener(on_press=on_press)
        self.keyboard_listener.daemon = True
        self.keyboard_listener.start()
    
    def reset(self):
        """重置钓鱼状态，返回初始状态"""
        print("正在重置钓鱼状态...")
        self.fishing = False
        self.fish_caught = False
        self.reeling = False
        self.reset_flag = False
        
        # 如果有收线状态属性，删除它们
        if hasattr(self, 'reeling_start_time'):
            delattr(self, 'reeling_start_time')
        if hasattr(self, 'reeling_clicks'):
            delattr(self, 'reeling_clicks')
        
        print("已返回初始状态，等待开始钓鱼...")
    
    def start(self):
        """开始自动钓鱼"""
        print("自动钓鱼已启动，按Q键返回初始状态...")
        self.stop_flag = False
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_area)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        # 主循环
        try:
            while not self.stop_flag:
                # 检查是否需要重置
                if self.reset_flag:
                    self.reset()
                    continue
                
                # 等待右键按下开始钓鱼
                print("等待右键按下开始钓鱼...")
                self._wait_for_fishing_start()
                if self.stop_flag or self.reset_flag:
                    continue
                
                # 开始钓鱼流程
                self._fishing_process()
                
                # 等待一段时间再开始下一轮
                time.sleep(1)
        except KeyboardInterrupt:
            print("程序被手动中断")
        finally:
            self.stop()
    
    def stop(self):
        """停止自动钓鱼"""
        print("正在停止自动钓鱼...")
        self.stop_flag = True
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
        if hasattr(self, 'keyboard_listener') and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()
        cv2.destroyAllWindows()
        print("自动钓鱼已停止")
    
    def _monitor_area(self):
        """监控颜色面积的线程函数"""
        while not self.stop_flag:
            # 检查是否需要重置
            if self.reset_flag:
                time.sleep(0.1)
                continue
                
            # 使用基于1080p的基准参数，通过缩放比例计算实际截图区域
            # 原始参数为1080p下的: x_offset=260, y_offset=220, width=1000, height=400
            scaled_region = self._calculate_scaled_region(260, 220, 1000, 400)
            frame = self.image_processor.capture_region(scaled_region)
            
            if frame is None:
                time.sleep(0.1)
                continue
            
            try:
                # 转换为HSV颜色空间
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                
                # 创建颜色掩膜
                mask = cv2.inRange(hsv, self.lower, self.upper)
                
                # 查找轮廓
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # 计算总面积
                total_area = 0
                valid_contours = []
                
                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    total_area += area
                    valid_contours.append(cnt)
                
                # 更新面积数据
                with self.lock:
                    self.last_area = self.current_area
                    self.current_area = total_area
                
            except Exception as e:
                print(f"监控出错: {e}")
            
            time.sleep(0.1)  # 控制帧率
    
    def _wait_for_fishing_start(self):
        """等待钓鱼开始（检测到用户右键按下）"""
        from pynput.mouse import Listener as MouseListener
        
        print("请按下右键开始钓鱼...")
        self.fishing = False
        right_clicked = False
        
        # 创建鼠标监听器
        def on_click(x, y, button, pressed):
            nonlocal right_clicked
            from pynput.mouse import Button
            if button == Button.right and pressed:
                right_clicked = True
                return False  # 停止监听
            return True
        
        # 启动鼠标监听
        listener = MouseListener(on_click=on_click)
        listener.start()
        
        # 等待右键点击或超时
        wait_start_time = time.time()
        while not right_clicked and not self.stop_flag and not self.reset_flag and time.time() - wait_start_time < 30:
            time.sleep(0.1)
        
        # 停止监听器
        if listener.is_alive():
            listener.stop()
        
        # 检查是否需要重置或停止
        if self.reset_flag or self.stop_flag:
            return False
        
        if not right_clicked:
            print("等待右键超时，取消钓鱼")
            return False
        
        print("已检测到右键点击，等待鱼上钩...")
        self.fishing = True
        
        # 循环按S键等待鱼上钩
        start_time = time.time()
        while not self.stop_flag and not self.reset_flag and time.time() - start_time < 20:  # 最多等待20秒
            self.input_handler.press('s', tm=0.2)
            time.sleep(0.3)
            
            # 检查是否有面积出现（鱼上钩）
            with self.lock:
                fish_hook_threshold = self._get_scaled_threshold("fish_hook")
                if self.current_area > fish_hook_threshold:  # 使用缩放后的阈值
                    self.initial_area = self.current_area
                    print(f"鱼已上钩！初始面积: {self.initial_area}, 阈值: {fish_hook_threshold}")
                    return True
        
        # 检查是否需要重置
        if self.reset_flag:
            return False
        
        # 超时处理
        print("等待超时，鱼没有上钩")
        self.fishing = False
        return False
    
    def _fishing_process(self):
        """完整的钓鱼流程"""
        if not self.fishing:
            return
        
        print("开始钓鱼流程...")
        self.fish_caught = False
        self.reeling = False
        
        # 拉鱼阶段
        while not self.stop_flag and not self.reset_flag and not self.fish_caught:
            # 检查是否需要重置
            if self.reset_flag:
                break
                
            # 检查面积变化，决定按哪个键
            with self.lock:
                current = self.current_area
                last = self.last_area
            
            # 如果面积接近0，表示拉线阶段结束，应该进入收线阶段
            near_zero_threshold = self._get_scaled_threshold("near_zero_1")
            if current < near_zero_threshold and not self.reeling:  # 使用缩放后的阈值
                print(f"面积接近0 ({current} < {near_zero_threshold})，拉线阶段结束，进入收线阶段")
                self._press_alternating_keys(0.5)
                self.reeling = True
                # 立即跳转到收线阶段处理
                continue
            
            # 根据面积变化决定按哪个键
            if not self.reeling:
                # 尝试按A键，看面积是否减少
                print("尝试按A键")
                self.input_handler.press('a', tm=0.5)
                time.sleep(0.2)  # 给监控线程时间更新面积
                
                with self.lock:
                    new_area = self.current_area
                area_change = current - new_area
                
                area_decrease_threshold = self._get_scaled_threshold("area_decrease")
                # 只有当面积减少超过阈值时才认为是有效的变化
                if area_change > area_decrease_threshold:  # A键有效，使用缩放后的阈值
                    print(f"鱼向右游，按A键有效，面积减少: {area_change} (阈值: {area_decrease_threshold})")
                    # 如果按键后进入了收线阶段，则不再继续执行后续逻辑
                    if self._press_key_until_area_decreases('a'):
                        continue
                else:  # 尝试D键
                    print("尝试按D键")
                    self.input_handler.press('d', tm=0.5)
                    time.sleep(0.2)  # 给监控线程时间更新面积
                    
                    with self.lock:
                        new_area = self.current_area
                    area_change = current - new_area
                    
                    # 只有当面积减少超过阈值时才认为是有效的变化
                    if area_change > area_decrease_threshold:  # D键有效，使用缩放后的阈值
                        print(f"鱼向左游，按D键有效，面积减少: {area_change} (阈值: {area_decrease_threshold})")
                        # 如果按键后进入了收线阶段，则不再继续执行后续逻辑
                        if self._press_key_until_area_decreases('d'):
                            continue
            
            # 收线阶段
            if self.reeling:
                # 记录收线开始时间
                if not hasattr(self, 'reeling_start_time'):
                    self.reeling_start_time = time.time()
                    self.reeling_clicks = 0
                    print("开始收线计时")
                
                # 连续右键收线，不限制次数，直到满足条件
                reeling_duration = time.time() - self.reeling_start_time
                
                # 快速右键点击
                for _ in range(5):  # 每次循环点击5次，然后检查状态
                    if self.stop_flag or self.reset_flag:
                        break
                    mouse.click_right(0.02)
                    self.reeling_clicks += 1
                    print(f"---------正在右键 {self.reeling_clicks}--------")
                    time.sleep(0.05)
                
                # 检查是否需要重置
                if self.reset_flag:
                    break
                
                # 检查面积变化
                with self.lock:
                    reel_complete_threshold = self._get_scaled_threshold("reel_complete")
                    area_ratio = self._get_scaled_threshold("area_ratio")
                    # 只有在收线超过2秒后才判断是否完成，避免初期误判
                    if reeling_duration > 2.0 and self.current_area < reel_complete_threshold and self.reeling_clicks > 20:
                        print(f"收线完成，钓鱼结束 (用时: {reeling_duration:.1f}秒, 点击: {self.reeling_clicks}次, 面积: {self.current_area} < {reel_complete_threshold})")
                        self.fish_caught = True
                        # 收线完成后按F键拾取物品
                        time.sleep(1)
                        self.input_handler.press("f")
                        # 重置收线状态
                        delattr(self, 'reeling_start_time')
                        delattr(self, 'reeling_clicks')
                        break
                    
                    # 如果面积接近初始面积，需要继续拉鱼
                    if self.current_area > self.initial_area * area_ratio:
                        print(f"面积增大至 {self.current_area} > {self.initial_area * area_ratio}，需要继续拉鱼")
                        self.reeling = False
                        # 重置收线状态
                        delattr(self, 'reeling_start_time')
                        delattr(self, 'reeling_clicks')
            
            time.sleep(0.1)  # 控制循环速度
        
        # 钓鱼结束
        self.fishing = False
        print("本轮钓鱼结束")
    
    def _press_key_until_area_decreases(self, key):
        """持续按键直到面积不再减少"""
        with self.lock:
            start_area = self.current_area
            last_check_area = start_area  # 上次检查的面积
        
        max_attempts = 20  # 增加最大尝试次数
        no_decrease_count = 0  # 连续没有减少的次数
        entered_reeling = False  # 标记是否已进入收线阶段
        
        self.input_handler.press_up(key)
        
        for _ in range(max_attempts):
            if self.stop_flag or self.reset_flag or self.reeling:
                break
            self.input_handler.press(key, tm=0.4)
            
            with self.lock:
                current = self.current_area
            
            # 检查面积是否接近0，表示拉线阶段结束，应该进入收线阶段
            # 只有在未进入收线阶段时才执行这个检查
            near_zero_threshold = self._get_scaled_threshold("near_zero_2")
            if current < near_zero_threshold and not self.reeling:  # 使用缩放后的阈值
                print(f"面积接近0 ({current} < {near_zero_threshold})，拉线阶段结束，进入收线阶段")
                self.reeling = True
                entered_reeling = True
                self._press_alternating_keys(0.5)
                return True
            
            # 检查面积是否减少
            area_decrease_threshold = self._get_scaled_threshold("area_decrease")
            if last_check_area - current > area_decrease_threshold:  # 面积有效减少，使用缩放后的阈值
                print(f"面积有效减少: {last_check_area - current} > {area_decrease_threshold}")
                last_check_area = current  # 更新上次检查的面积
                no_decrease_count = 0  # 重置计数器
            else:
                # 面积没有减少，增加计数
                no_decrease_count += 1
                print(f"面积未减少，当前计数: {no_decrease_count}")
                # 如果连续2次没有减少，认为已经不再减少
                if no_decrease_count >= 2:
                    print(f"面积不再减少，停止按键")
                    return True
        
        print(f"达到最大尝试次数，停止按键")
        with self.lock:
            final_area = self.current_area
        
        area_decrease_threshold = self._get_scaled_threshold("area_decrease")
        return start_area - final_area > area_decrease_threshold * 1.5  # 返回是否有效减少过面积，使用缩放后的阈值
    
    def _press_alternating_keys(self, duration):
        """交替按A和D键指定时间"""
        start_time = time.time()
        while time.time() - start_time < duration and not self.stop_flag and not self.reset_flag:
            self.input_handler.press('a', tm=0.08)
            self.input_handler.press('d', tm=0.08)

