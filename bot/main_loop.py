import logging
import threading
import time
import ctypes
from ctypes import wintypes
from controller.MouseController import mouse

# 定义鼠标输入结构，用于快速点击
if ctypes.sizeof(ctypes.c_void_p) == 4:
    ULONG_PTR = ctypes.c_ulong  
else:
    ULONG_PTR = ctypes.c_ulonglong  

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx', wintypes.LONG),
        ('dy', wintypes.LONG),
        ('mouseData', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ULONG_PTR),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ('type', wintypes.DWORD),
        ('mi', MOUSEINPUT),
    ]

logger = logging.getLogger(__name__)

class MainLoopHandler:
    """处理钓鱼机器人主循环的类"""

    def __init__(self, state_handler, input_handler, line_handler):
        """初始化主循环处理器
        
        参数:
            state_handler: 状态处理器
            input_handler: 输入控制器
            line_handler: 鱼线处理器
        """
        self.state_handler = state_handler
        self.input_handler = input_handler
        self.line_handler = line_handler
        
        # 连续钓鱼设置
        self.continuous_fishing = False
        self.max_continuous_count = 3
        
        # 运行控制
        self.running = False
        self.stop_flag = False
        
        # 主循环线程
        self.main_thread = None
        
        # 从配置文件获取收线按键设置
        from config_manager import config_manager
        self.reel_key = config_manager.get("fishing.reel_key", "right_click")
        logger.info(f"收线按键设置为: {self.reel_key}")
    
    def set_continuous_fishing(self, continuous, max_count=3):
        """设置连续钓鱼
        
        参数:
            continuous: 是否开启连续钓鱼
            max_count: 最大连续钓鱼次数
        """
        self.continuous_fishing = continuous
        self.max_continuous_count = max_count
        logger.info(f"连续钓鱼功能已{'启用' if continuous else '禁用'}, 最大次数: {max_count}")
    
    def set_running_state(self, running, stop_flag=False):
        """设置运行状态"""
        self.running = running
        self.stop_flag = stop_flag

    def _check_current_template(self):
        """检查当前是否仍然检测到模板

        返回:
            str: 当前检测到的模板名称，如果没有检测到则返回None
        """
        try:
            # 获取当前屏幕截图
            captures = self.state_handler.ocr_capture.capture_one_shot()
            if not captures or 'full_region' not in captures or not captures['full_region']:
                logger.debug("无法获取屏幕截图进行模板检查")
                return None

            # 转换为OpenCV格式
            import cv2
            import numpy as np
            template_img_cv = cv2.cvtColor(np.array(captures['full_region']), cv2.COLOR_RGB2BGR)

            # 使用模板匹配器检测当前模板
            match_result = self.state_handler.template_matcher.match_template(template_img_cv)

            if match_result and match_result.get("score", 0) >= 0.8:
                template_name = match_result.get("name")
                score = match_result.get("score", 0)
                logger.debug(f"当前检测到模板: {template_name}, 得分: {score:.2f}")
                return template_name
            else:
                logger.debug("当前未检测到有效模板")
                return None

        except Exception as e:
            logger.error(f"检查当前模板时出错: {e}")
            return None
    
    def start_main_loop(self):
        """启动主循环"""
        if self.main_thread and self.main_thread.is_alive():
            self.stop_flag = True
            self.main_thread.join(timeout=2)
        
        self.stop_flag = False
        self.main_thread = threading.Thread(target=self._main_loop, daemon=True)
        self.main_thread.start()
        logger.info("钓鱼机器人主循环已启动")
    
    def stop_main_loop(self):
        """停止主循环"""
        self.stop_flag = True
        if self.main_thread and self.main_thread.is_alive():
            self.main_thread.join(timeout=2)
        logger.info("钓鱼机器人主循环已停止")
    
    def _main_loop(self):
        """主循环，根据状态执行对应操作"""
        logger.info("钓鱼机器人主循环已启动")
        
        # 错误计数器和最大错误次数
        error_count = 0
        max_errors = 5
        
        while self.running and not self.stop_flag and not self.input_handler.stop_flag:
            try:
                # 检查InputHandler的stop_flag，如果被设置则停止
                if self.input_handler.stop_flag:
                    logger.info("检测到InputHandler停止信号，停止主循环")
                    self.stop_flag = True
                    break
                if self.state_handler.running_state == 0 and self.continuous_fishing and self.state_handler.fishing_count > 0:
                    # 未开始且开启了连续钓鱼且已经钓过鱼
                    
                    # 如果已达到目标次数，则停止并重置钓鱼计数
                    if self.state_handler.target_fishing_count > 0 and self.state_handler.fishing_count >= self.state_handler.target_fishing_count:
                        logger.info(f"已达到目标钓鱼次数: {self.state_handler.target_fishing_count}，停止钓鱼")
                        self.state_handler.fishing_count = 0  # 重置钓鱼计数为0
                        self.stop_flag = True
                        continue
                        
                    # 开始新一轮钓鱼 - 使用优化的抛竿方法
                    if not self._cast_fishing_rod():
                        logger.warning("抛竿失败，跳过本轮")
                        continue
                                
                elif self.state_handler.running_state == 4:  # 跳过
                    logger.info("执行跳过操作")

                    # 检查是否仍然检测到跳过模板
                    current_template = self._check_current_template()
                    if current_template and current_template == "跳过":
                        # 确保有足够的按键间隔，使游戏能够响应
                        self.input_handler.press('f', 0.15)
                        time.sleep(0.2)  # 增加等待时间
                        self.input_handler.press('f', 0.15)
                        time.sleep(0.5)
                        self.input_handler.press('f', 0.15)
                        logger.info(f"跳过操作完成，按F键3次")

                        # 检查收线标志，如果为true则重置状态为未开始
                        if self.state_handler.line_retrieved_flag:
                            logger.info("检测到收线标志为true，重置状态为未开始")
                            self.state_handler.running_state = 0
                            self.state_handler.line_retrieved_flag = False  # 重置收线标志
                    else:
                        logger.info("未检测到跳过模板，跳过F键操作")
                        # 如果没有检测到模板，等待状态自动重置
                        self.input_handler.press('f', 0.15)
                        time.sleep(0.5)
                    
                elif self.state_handler.running_state == 1:  # 收竿/提竿
                    logger.info("执行收竿/提竿操作 - 按S键")
                    self.input_handler.press('s', 0.2)
                    time.sleep(0.2)
                    logger.info("收竿/提竿操作完成")
                    
                elif self.state_handler.running_state == 2:  # 拉扯鱼线
                    logger.info("执行拉扯鱼线操作 - 开始处理鱼线")
                    self.line_handler.handle_jerky_line(self.state_handler.jerky_line_flag)
                    logger.info("拉扯鱼线操作处理完成")
                    
                elif self.state_handler.running_state == 3:  # 收线
                    logger.info(f"执行收线操作 - 开始快速{self.reel_key}点击")
                    current_state = self.state_handler.running_state  # 记录当前状态

                    # 先激活一次窗口，避免重复激活
                    if self.reel_key == "right_click":
                        # 激活窗口但不点击
                        mouse._activate_window()

                    # 增加点击次数到50次，并减少间隔时间以提高响应速度
                    for i in range(50):
                        # 检查状态是否已经改变，如果改变则退出循环
                        if self.state_handler.running_state != current_state:
                            old_state_name = self.state_handler.state_names.get(current_state, f"未知状态({current_state})")
                            new_state_name = self.state_handler.state_names.get(self.state_handler.running_state, f"未知状态({self.state_handler.running_state})")
                            logger.info(f"收线操作被中断 - 状态已从 [{old_state_name}] 变更为 [{new_state_name}]，点击次数: {i+1}/50")
                            break

                        # 根据配置使用正确的收线按键
                        if self.reel_key == "right_click":
                            # 使用鼠标右键点击，进一步减少点击持续时间和间隔以提高响应速度
                            mouse.press_right()
                            time.sleep(0.01)  # 进一步减少按下时间
                            mouse.release_right()
                        else:
                            # 使用键盘按键
                            self.input_handler.press(self.reel_key, 0.01)  # 进一步减少按键时间

                        time.sleep(0.01)  # 进一步减少等待时间，提高收线响应速度
                        logger.debug(f"收线点击 {i+1}/50")

                error_count = 0
                time.sleep(0.05)
                
            except Exception as e:
                logger.error(f"主循环执行出错: {e}")
                error_count += 1
                
                # 如果错误次数过多，重置状态
                if error_count >= max_errors:
                    logger.warning(f"错误次数过多({error_count}次)，重置状态")
                    self.state_handler.running_state = 0
                    error_count = 0
                    time.sleep(1.0)
                else:
                    time.sleep(0.5)  # 短暂延迟后重试
        
        logger.info("钓鱼机器人主循环已停止")

    def _cast_fishing_rod(self, max_attempts=3):
        """
        抛竿操作 - 优化版本，减少重复代码

        参数:
            max_attempts: 最大尝试次数

        返回:
            bool: True表示抛竿成功，False表示失败
        """
        from controller.MouseController import mouse

        logger.info("开始新一轮钓鱼 - 点击右键")
        time.sleep(1.0)  # 等待之前的状态完成

        for attempt in range(max_attempts):
            mouse.click_right(0.05)
            time.sleep(2.0)  # 等待钓鱼动作开始

            # 检查钓鱼动作是否开始
            if self.state_handler.running_state != 0:
                logger.info(f"抛竿成功，尝试次数: {attempt + 1}")
                return True

            if attempt < max_attempts - 1:
                logger.info(f"钓鱼动作未开始，重新抛竿 (尝试 {attempt + 2}/{max_attempts})")
            else:
                logger.warning("多次尝试后钓鱼动作仍未开始")

        # 重置状态并返回失败
        self.state_handler.running_state = 0
        time.sleep(1.0)
        return False

