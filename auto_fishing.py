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
from config_manager import CONFIG

class AutoFishing:
    def __init__(self):
        # 使用全局配置
        self.config = CONFIG
        
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
        
        # 从配置文件中读取基准阈值
        self.base_thresholds = self.config["fishing"]["thresholds"]
        print("成功加载基准阈值配置")
        
        # 获取收线键位配置，默认为右键
        self.reel_key = self.config["fishing"].get("reel_key", "right_click")
        print(f"收线键位: {self.reel_key}")
        
        # 颜色范围参数 - 用于检测钓鱼进度
        self.lower = np.array([22, 54, 250])
        self.upper = np.array([25, 88, 255])
        
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
        """重置钓鱼状态"""
        print("重置钓鱼状态")
        print(f"当前状态 - fishing: {self.fishing}, fish_caught: {self.fish_caught}, reeling: {self.reeling}")
        self.initial_area = 0
        self.current_area = 0
        self.last_area = 0
        self.fish_caught = False
        self.reeling = False
        self.reset_flag = False
        print(f"重置后状态 - fishing: {self.fishing}, fish_caught: {self.fish_caught}, reeling: {self.reeling}")
        # 保留fishing状态，由外部控制
    
    def start(self):
        """开始钓鱼"""
        print("开始钓鱼")
        print(f"当前状态 - fishing: {self.fishing}, fish_caught: {self.fish_caught}, reeling: {self.reeling}")
        
        # 重置停止标志
        self.stop_flag = False
        self.reset_flag = False
        
        # 开始钓鱼循环
        try:
            print("开始钓鱼循环")
            self._fishing_loop()
        except Exception as e:
            print(f"钓鱼过程出错: {e}")
            import traceback
            print(traceback.format_exc())
    
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
                
            # 使用配置文件中的检测区域参数
            region = self.config["fishing"]["region"]
            scaled_region = self._calculate_scaled_region(
                region["x_offset"],
                region["y_offset"],
                region["width"],
                region["height"]
            )
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
        print(f"当前状态 - fishing: {self.fishing}, fish_caught: {self.fish_caught}, reeling: {self.reeling}")
        
        # 如果已经在钓鱼状态，则不需要等待右键点击
        if self.fishing:
            print("已经在钓鱼状态，跳过等待右键点击")
            # 循环按S键等待鱼上钩
            attempts = 0
            max_attempts = 30  # 最多等待约9秒
            
            while not self.stop_flag and not self.reset_flag and attempts < max_attempts:
                attempts += 1
                self.input_handler.press('s', tm=0.2)
                time.sleep(0.3)
                
                # 检查是否有面积出现（鱼上钩）
                with self.lock:
                    fish_hook_threshold = self._get_scaled_threshold("fish_hook")
                    if self.current_area > fish_hook_threshold:  # 使用缩放后的阈值
                        self.initial_area = self.current_area
                        print(f"鱼已上钩！初始面积: {self.initial_area}, 阈值: {fish_hook_threshold}")
                        return True
            
            # 如果超过最大尝试次数仍未上钩
            if attempts >= max_attempts:
                print("等待鱼上钩超时，重置钓鱼状态")
                self.reset_flag = True
            
            # 检查是否需要重置
            if self.reset_flag:
                return False
            
            self.fishing = False
            return False
            
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
        
        # 等待右键点击
        while not right_clicked and not self.stop_flag and not self.reset_flag:
            time.sleep(0.1)
        
        # 停止监听器
        if listener.is_alive():
            listener.stop()
        
        # 检查是否需要重置或停止
        if self.reset_flag or self.stop_flag:
            return False
        
        print("已检测到右键点击，等待鱼上钩...")
        self.fishing = True
        time.sleep(1)
        # 循环按S键等待鱼上钩
        while not self.stop_flag and not self.reset_flag:
            self.input_handler.press('s', tm=0.2)
            time.sleep(0.2)
            
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
        
        self.fishing = False
        return False
    
    def _fishing_process(self):
        """完整的钓鱼流程"""
        if not self.fishing:
            print("当前不在钓鱼状态，退出钓鱼流程")
            return
        
        print("开始钓鱼流程...")
        print(f"当前状态 - fishing: {self.fishing}, fish_caught: {self.fish_caught}, reeling: {self.reeling}")
        print(f"当前面积: {self.current_area}, 初始面积: {self.initial_area}")
        
        self.fish_caught = False
        self.reeling = False
        
        # 拉鱼阶段
        print("进入拉鱼阶段")
        while not self.stop_flag and not self.reset_flag and not self.fish_caught:
            # 检查是否需要重置
            if self.reset_flag:
                print("检测到重置标志，退出拉鱼阶段")
                break
                
            # 检查面积变化，决定按哪个键
            with self.lock:
                current = self.current_area
                last = self.last_area
                
            print(f"当前面积: {current}, 上次面积: {last}, 差值: {current - last}")
            
            # 如果面积接近0，表示拉线阶段结束，应该进入收线阶段
            near_zero_threshold = self._get_scaled_threshold("near_zero_1")
            if current < near_zero_threshold and not self.reeling:  # 使用缩放后的阈值
                print(f"面积接近0 ({current} < {near_zero_threshold})，拉线阶段结束，进入收线阶段")
                self._press_alternating_keys(0.8)
                self.reeling = True
                # 立即跳转到收线阶段处理
                continue
            
            # 根据面积变化决定按哪个键
            if not self.reeling:
                # 尝试按A键，看面积是否减少
                print("尝试按A键")
                self.input_handler.press('a', tm=0.5)             
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
                    
                    # 根据配置使用不同的收线方式
                    if self.reel_key == "right_click":
                        mouse.click_right(0.02)
                    else:
                        # 使用键盘按键
                        self.input_handler.press(self.reel_key, tm=0.02)
                    
                    self.reeling_clicks += 1
                    print(f"---------正在收线 {self.reeling_clicks} 次 (键位: {self.reel_key})--------")
                    time.sleep(0.04)
                
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
                        time.sleep(0.8)
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
            
            time.sleep(0.06)  # 控制循环速度
        
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
                self._press_alternating_keys(0.8)
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
                # 如果连续1次没有减少，认为已经不再减少
                if no_decrease_count >= 1:
                    print(f"面积不再减少，停止按键")
                    return True
        
        print(f"达到最大尝试次数，停止按键")
        with self.lock:
            final_area = self.current_area
        
        area_decrease_threshold = self._get_scaled_threshold("area_decrease")
        return start_area - final_area > area_decrease_threshold * 1.5  # 返回是否有效减少过面积，使用缩放后的阈值
    
    def _press_alternating_keys(self, duration):
        """交替按A和D键指定时间，同时进行收线操作"""
        start_time = time.time()
        
        # 使用鱼上钩时记录的初始面积，而不是当前面积
        initial_area = self.initial_area
        
        # 计算阈值：初始面积的九分之一
        threshold = initial_area / 9
        print(f"交替按键阈值设置为初始面积的九分之一: {threshold} (初始面积: {initial_area})")
        
        while time.time() - start_time < duration and not self.stop_flag and not self.reset_flag:
            # 按A键
            self.input_handler.press('a', tm=0.08)
            # 同时进行收线操作
            if self.reel_key == "right_click":
                mouse.click_right(0.02)
            else:
                self.input_handler.press(self.reel_key, tm=0.02)
            
            # 检查面积是否大于阈值
            with self.lock:
                current_area = self.current_area
                if current_area > threshold:
                    print(f"交替按键过程中检测到面积大于阈值: {current_area} > {threshold}，立即进入收线阶段")
                    self.reeling = True
                    return
            
            # 按D键
            self.input_handler.press('d', tm=0.08)
            # 同时进行收线操作
            if self.reel_key == "right_click":
                mouse.click_right(0.02)
            else:
                self.input_handler.press(self.reel_key, tm=0.02)
        
            # 再次检查面积是否大于阈值
            with self.lock:
                current_area = self.current_area
                if current_area > threshold:
                    print(f"交替按键过程中检测到面积大于阈值: {current_area} > {threshold}，立即进入收线阶段")
                    self.reeling = True
                    return
                        
    def _fishing_loop(self):
        """钓鱼主循环"""
        print("进入钓鱼主循环")
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_area)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        print("监控线程已启动")
        
        # 主循环
        try:
            while not self.stop_flag:
                # 检查是否需要重置
                if self.reset_flag:
                    print("检测到重置标志，重置钓鱼状态")
                    self.reset()
                    # 如果fishing状态为True，说明是连续钓鱼模式，不需要等待右键点击
                    if self.fishing:
                        print("连续钓鱼模式，跳过等待右键点击")
                        # 直接进入钓鱼流程
                        if self._wait_for_fishing_start() and not self.stop_flag and not self.reset_flag:
                            print("开始钓鱼流程")
                            self._fishing_process()
                    continue
                
                # 等待右键按下开始钓鱼
                print("等待右键按下开始钓鱼...")
                if self._wait_for_fishing_start() and not self.stop_flag and not self.reset_flag:
                    # 开始钓鱼流程
                    print("右键已按下，开始钓鱼流程")
                    self._fishing_process()
                
                # 等待一段时间再开始下一轮
                time.sleep(1)
        except KeyboardInterrupt:
            print("程序被手动中断")
        finally:
            print("钓鱼循环结束")
            self.stop()

