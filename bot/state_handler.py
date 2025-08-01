import logging
import threading
import time
import numpy as np
import cv2

logger = logging.getLogger(__name__)

class StateHandler:
    """处理钓鱼状态的类"""

    def __init__(self, template_matcher, ocr_capture, input_handler=None):
        """初始化状态处理器

        参数:
            template_matcher: 模板匹配器
            temp_capture: OCR区域截图器
            input_handler: 输入控制器（可选，用于检查F9停止信号）
        """
        self.template_matcher = template_matcher
        self.ocr_capture = ocr_capture
        self.input_handler = input_handler
        
        # 状态变量
        self.running_state = 0  # 0:未开始，1:收竿/提竿，2:拉扯鱼线，3:收线，4:跳过
        self.jerky_line_flag = False  # 是否在拉扯鱼线状态
        self.line_retrieved_flag = False  # 收线操作标志
        
        # 钓鱼计数相关变量
        self.fishing_count = 0  # 钓鱼成功次数
        self.target_fishing_count = 0  # 目标钓鱼次数 (0表示无限)
        
        # 运行控制
        self.running = False
        self.stop_flag = False
        
        # 检测线程
        self.template_thread = None
        
        # 使用统一的状态名称映射
        try:
            from utils import STATE_NAMES
            self.state_names = STATE_NAMES
        except ImportError:
            # 如果utils模块不可用，使用本地定义
            self.state_names = {0: "未开始", 1: "收竿/提竿", 2: "拉扯鱼线", 3: "收线", 4: "跳过"}
    
    def set_running_state(self, running, stop_flag=False):
        """设置运行状态"""
        self.running = running
        self.stop_flag = stop_flag
    
    def reset_state(self):
        """重置状态"""
        self.running_state = 0
        self.jerky_line_flag = False
        self.line_retrieved_flag = False
        self.fishing_count = 0
    
    def start_detection(self):
        """启动模板匹配检测线程"""
        if self.template_thread and self.template_thread.is_alive():
            self.stop_flag = True
            self.template_thread.join(timeout=2)
        
        self.stop_flag = False
        self.template_thread = threading.Thread(target=self._template_detection_loop, daemon=True)
        self.template_thread.start()
        logger.info("模板匹配检测线程已启动")
    
    def stop_detection(self):
        """停止模板匹配检测线程"""
        self.stop_flag = True
        if self.template_thread and self.template_thread.is_alive():
            self.template_thread.join(timeout=2)
        logger.info("模板匹配检测线程已停止")
    
    def _template_detection_loop(self):
        """模板匹配检测循环，负责状态管理"""
        logger.info("模板匹配检测线程已启动")
        
        # 记录上次检测到的状态，避免重复日志
        last_detected_template = None
        # 计时器，用于检测长时间无匹配的情况
        no_match_timer = time.time()
        # 错误计数器
        error_count = 0
        
        while not self.stop_flag:
            try:
                # 检查InputHandler的stop_flag，如果被设置则停止
                if self.input_handler and self.input_handler.stop_flag:
                    logger.info("检测到InputHandler停止信号，停止状态检测")
                    self.stop_flag = True
                    break
                # 截取检测区域的屏幕
                captures = self.ocr_capture.capture_one_shot()
                if not captures or 'full_region' not in captures or not captures['full_region']:
                    time.sleep(0.3)
                    continue
                
                # 获取完整区域图像，而不是子区域
                template_img = captures['full_region']
                
                # 确保图像是numpy数组格式，这是OpenCV的要求
                if not isinstance(template_img, np.ndarray):
                    # 如果是PIL Image，转换为numpy数组
                    template_img_cv = cv2.cvtColor(np.array(template_img), cv2.COLOR_RGB2BGR)
                else:
                    # 已经是numpy数组，确保颜色通道正确
                    if len(template_img.shape) == 3 and template_img.shape[2] == 3:
                        template_img_cv = template_img.copy()
                    else:
                        # 如果是灰度图或其他格式，可能需要转换
                        template_img_cv = cv2.cvtColor(template_img, cv2.COLOR_RGB2BGR)
                
                # 获取窗口尺寸，用于模板匹配
                window_size = (self.ocr_capture.window_width, self.ocr_capture.window_height)
                
                # 使用模板匹配检测
                match_result = self.template_matcher.match_template(template_img_cv)
                
                # 重置错误计数
                error_count = 0
                
                if not match_result:
                    # 长时间无匹配，重置状态为未开始
                    if time.time() - no_match_timer > 4:  # 4秒无匹配则重置状态
                        if self.running_state != 0:
                            old_state_name = self.state_names.get(self.running_state, f"未知状态({self.running_state})")
                            
                            logger.info(f"4s无匹配，状态变更: [{old_state_name}] -> [未开始]")
                            self.running_state = 0
                            self.line_retrieved_flag = False  # 重置收线标志
                            no_match_timer = time.time()  # 重置计时器
                            # 将上次检测到的状态记录为"未开始"
                            last_detected_template = "未开始"
                            logger.info("无匹配，当前模板：未开始")
                    # 减少空检测时的等待时间
                    time.sleep(0.05)
                    continue
                
                # 有匹配，重置计时器
                no_match_timer = time.time()
                
                # 解析模板匹配结果，更新状态
                template_name = match_result["name"]
                match_score = match_result["score"]
                
                # 设置匹配得分阈值，避免误识别 (使用TM_SQDIFF_NORMED方法，阈值0.8以上表示成功匹配)
                min_score_threshold = 0.8

                # 只有当得分超过阈值，并且与上次检测到的状态不同时，才记录日志和切换状态
                if match_score >= min_score_threshold and template_name != last_detected_template:
                    old_state = self.running_state
                    old_state_name = self.state_names.get(old_state, f"未知状态({old_state})")
                    
                    logger.info(f"检测到模板: {template_name}, 得分: {match_score:.2f}, 准备切换状态")
                    last_detected_template = template_name
                    
                    # 根据模板名称更新状态 - 使用优化的状态变更方法
                    if template_name == "收线":
                        self._change_state_to_reel(old_state_name)
                    elif template_name == "跳过":
                        self._change_state_to_skip(old_state_name)
                        
                        # 如果已经检测到收线操作，则计为一次成功钓鱼
                        if self.line_retrieved_flag:
                            self.fishing_count += 1
                            logger.info(f"成功钓鱼! 当前次数: {self.fishing_count}/{self.target_fishing_count}")
                            
                            # 重置收线标志
                            self.line_retrieved_flag = False
                            
                            # 如果达到目标次数，发出信号
                            if self.target_fishing_count > 0 and self.fishing_count >= self.target_fishing_count:
                                logger.info(f"已达到目标钓鱼次数: {self.target_fishing_count}")
                                self.on_target_reached()
                        else:
                            logger.info("检测到跳过操作，但没有先检测到收线操作，不计入钓鱼次数")
                            # 重置收线标志
                            self.line_retrieved_flag = False
                    elif template_name == "收竿" or template_name == "提竿":
                        self.running_state = 1
                        self.jerky_line_flag = False
                        new_state_name = self.state_names.get(self.running_state, f"未知状态({self.running_state})")
                        logger.info(f"状态变更: [{old_state_name}] -> [{new_state_name}], 检测到收竿/提竿操作")
                    elif template_name == "拉扯鱼线":
                        self.running_state = 2
                        self.jerky_line_flag = True
                        new_state_name = self.state_names.get(self.running_state, f"未知状态({self.running_state})")
                        logger.info(f"状态变更: [{old_state_name}] -> [{new_state_name}], 检测到拉扯鱼线操作")
                    
                elif match_score >= min_score_threshold:
                    # 相同状态但匹配度高，只在调试级别记录
                    logger.debug(f"持续检测到模板: {template_name}, 得分: {match_score:.2f}")
                else:
                    # 匹配度不够高，可能是误识别
                    logger.debug(f"检测到可能的模板: {template_name}, 但得分较低: {match_score:.2f}")
                    # 设置为"未开始"状态，因为匹配度不够高
                    if last_detected_template != "未开始":
                        last_detected_template = "未开始"
                        logger.info("匹配度不够高，当前模板：未开始")
            
            except Exception as e:
                logger.error(f"模板匹配检测出错: {e}")
                # 增加错误计数
                error_count += 1
                
                # 如果连续错误次数过多，进行额外处理
                if error_count > 5:
                    logger.warning(f"连续错误次数过多 ({error_count})，尝试重置模板匹配")
                    # 尝试清空缓存的缩放模板
                    if hasattr(self.template_matcher, 'scaled_templates'):
                        self.template_matcher.scaled_templates.clear()
                    # 额外等待时间，让系统有机会恢复
                    time.sleep(1.0)
                    # 如果错误次数极多，可能需要重置状态
                    if error_count > 20:
                        self.running_state = 0
                        self.jerky_line_flag = False
                        self.line_retrieved_flag = False
                        logger.warning("由于持续错误，已重置钓鱼状态")
                        error_count = 0
            
            time.sleep(0.1)
        
        logger.info("模板匹配检测线程已停止")
    
    def on_target_reached(self):
        """达到目标钓鱼次数时的回调，可被子类重写"""
        self.stop_flag = True
        self.fishing_count = 0  # 重置钓鱼计数为0
        self.running_state = 0  # 将运行阶段设为未开始
        logger.info("已达到目标钓鱼次数，重置钓鱼计数为0，并将运行阶段设为未开始")
    
    def set_target_count(self, count):
        """设置目标钓鱼次数"""
        self.target_fishing_count = count
        logger.info(f"设置目标钓鱼次数: {count if count > 0 else '无限'}")
    
    def get_current_state(self):
        """获取当前状态名称"""
        return self.state_names.get(self.running_state, f"未知状态({self.running_state})")
    
    def get_fishing_count(self):
        """获取当前钓鱼次数"""
        return self.fishing_count

    def _change_state_to_reel(self, old_state_name):
        """
        切换到收线状态 - 优化版本，减少重复代码

        参数:
            old_state_name: 旧状态名称
        """
        old_running_state = self.running_state
        self.running_state = 3
        self.jerky_line_flag = False
        self.line_retrieved_flag = True  # 设置收线标志为True

        # 使用统一的日志记录方法
        self._log_state_change(old_state_name, "收线", "检测到收线操作，设置收线标志")

        # 如果之前处于拉扯鱼线状态，立即通知所有相关组件停止a/d键操作
        if old_running_state == 2:
            logger.info("从拉扯鱼线状态切换到收线状态，立即停止所有a/d键操作")

    def _change_state_to_skip(self, old_state_name):
        """
        切换到跳过状态 - 优化版本，减少重复代码

        参数:
            old_state_name: 旧状态名称
        """
        self.running_state = 4
        self.jerky_line_flag = False
        self._log_state_change(old_state_name, "跳过")

    def _log_state_change(self, old_state_name, new_state_name, additional_info=""):
        """
        统一的状态变更日志记录

        参数:
            old_state_name: 旧状态名称
            new_state_name: 新状态名称
            additional_info: 附加信息
        """
        info_str = f"状态变更: [{old_state_name}] -> [{new_state_name}]"
        if additional_info:
            info_str += f", {additional_info}"
        logger.info(info_str)