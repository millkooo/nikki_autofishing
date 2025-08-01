import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class LineHandler:
    """处理鱼线拉扯的类"""

    def __init__(self, input_handler, area_capture, state_handler=None):
        """初始化鱼线处理器

        参数:
            input_handler: 输入处理器
            area_capture: 区域截图器
            state_handler: 状态处理器（用于检查收线状态）
        """
        self.input_handler = input_handler
        self.area_capture = area_capture
        self.state_handler = state_handler

        # 初始面积
        self.init_area = 0

        # HSV阈值（用于面积检测）
        self.lower = np.array([22, 54, 250])
        self.upper = np.array([25, 88, 255])

        # 基准分辨率
        self.base_resolution = (1920, 1080)

        # 当前缩放因子
        self.scale_x = 1.0
        self.scale_y = 1.0

        # 尝试获取窗口尺寸并计算缩放因子
        #self._update_scale_factors()
    
    def _update_scale_factors(self):
        """更新缩放因子"""
        try:
            # 尝试获取窗口尺寸
            from config_manager import config_manager
            window_width = self.area_capture.window_width
            window_height = self.area_capture.window_height
            
            if window_width and window_height:
                self.scale_x = window_width / self.base_resolution[0]
                self.scale_y = window_height / self.base_resolution[1]
                logger.info(f"更新缩放因子: ({self.scale_x:.2f}, {self.scale_y:.2f})")
        except Exception as e:
            logger.error(f"更新缩放因子出错: {e}")

    def handle_jerky_line(self, jerky_line_flag):
        """处理拉扯鱼线状态
        
        参数:
            jerky_line_flag: 当前是否处于拉扯鱼线状态
        """
        # 只有当jerky_line_flag为True时才执行
        if not jerky_line_flag:
            return
            
        # 快速检查是否处于收线状态，如果是则立即返回
        if self._is_line_retrieved_state():
            logger.info("立即检测到收线状态，放弃执行拉扯鱼线操作")
            return
            
        # 最大尝试次数
        max_attempts = 3
        attempt = 0
        
        # 创建局部变量存储状态，因为参数无法被修改
        current_jerky_state = jerky_line_flag
        
        while attempt < max_attempts and current_jerky_state:
            # 先检查是否已经进入收线状态 - 使用双重检查
            if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
                logger.info("检测到收线状态，立即中断拉扯鱼线操作")
                return

            # 按下a键
            self._press_keys('a')

            # 再次检查是否已经进入收线状态 - 使用双重检查
            if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
                logger.info("按下a键后检测到收线状态，立即中断拉扯鱼线操作")
                return

            # 检查剩余面积
            area_status = self.check_remain_area()
            if area_status == 2:  # 检测到收线状态
                logger.info("面积检测过程中发现收线状态，立即中断拉扯鱼线操作")
                return
            elif area_status == 0:  # 面积足够大
                # 再次检查收线状态
                if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
                    logger.info("按下d键前检测到收线状态，立即中断拉扯鱼线操作")
                    return

                # 如果面积足够大，按下d键
                self._press_keys('d')

                # 再次检查是否已经进入收线状态 - 使用双重检查
                if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
                    logger.info("按下d键后检测到收线状态，立即中断拉扯鱼线操作")
                    return

                # 再次检查面积
                area_status = self.check_remain_area()
                if area_status == 2:  # 检测到收线状态
                    logger.info("第二次面积检测过程中发现收线状态，立即中断拉扯鱼线操作")
                    return
                elif area_status == 0:  # 面积仍然足够大
                    # 再次检查收线状态
                    if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
                        logger.info("第二次按下a键前检测到收线状态，立即中断拉扯鱼线操作")
                        return

                    # 如果面积还是足够大，再次按下a键
                    self._press_keys('a')

                    # 再次检查是否已经进入收线状态 - 使用双重检查
                    if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
                        logger.info("第二次按下a键后检测到收线状态，立即中断拉扯鱼线操作")
                        return
            else:  # area_status == 1，面积很小
                # 直接使用新添加的交替按键方法
                if self._perform_ad_key_combination():
                    # 如果_perform_ad_key_combination()返回True，说明检测到收线状态
                    logger.info("交替按键过程中检测到收线状态，立即中断拉扯鱼线操作")
                    return
                # 检查是否成功退出拉扯鱼线状态
                current_jerky_state = self._check_jerky_line_state()
                if not current_jerky_state:
                    logger.info("执行交替按键后成功退出拉扯鱼线状态")
                    break

            attempt += 1
            import time
            time.sleep(0.05)  # 减少延迟时间，更频繁检查状态
    
    def check_remain_area(self):
        """
        检测剩余面积是否小于初始面积的十分之一
        返回:
            0: 面积大于十分之一初始面积
            1: 面积小于十分之一初始面积
            2: 检测到收线状态，应立即中断当前操作
        """
        try:
            # 首先检查是否已经进入收线状态 - 使用双重检查
            if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
                logger.info("面积检测开始前发现收线状态，立即返回")
                return 2

            # 使用区域截图器获取当前屏幕
            captures = self.area_capture.capture_one_shot()
            if not captures['full_region']:
                logger.info("无法捕获面积检测区域的图像")
                # 修改：无法捕获图像时直接执行交替按键
                logger.info("无法捕获图像，开始交替按a-d键")
                if self._perform_ad_key_combination():
                    # 如果在交替按键过程中检测到收线状态
                    return 2
                return 0
                
            # 转换为OpenCV格式
            img = cv2.cvtColor(np.array(captures['full_region']), cv2.COLOR_RGB2BGR)

            # 优先检查收线状态（通过状态处理器）
            if self._is_line_retrieved_state():
                logger.info("面积检测过程中通过状态处理器发现收线状态，立即中断")
                return 2
            
            # 转换到HSV色彩空间
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # 提取指定颜色范围
            mask = cv2.inRange(hsv, self.lower, self.upper)
            
            # 寻找轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 如果未检测到轮廓，直接执行a-d交替按键
            if not contours:
                logger.info("未检测到轮廓，开始交替按a-d键")
                if self._perform_ad_key_combination():
                    # 如果在交替按键过程中检测到收线状态
                    return 2
                return 0
            
            # 计算最大轮廓面积
            max_area = max([cv2.contourArea(c) for c in contours])
                
            # 第一次运行时记录初始面积
            if self.init_area == 0:
                self.init_area = max_area
                logger.info(f"记录初始面积: {self.init_area}")
                return 0
            
            # 判断剩余面积比例
            if self.init_area > 0 and max_area < self.init_area / 10:
                logger.info(f"剩余面积很小: {max_area:.2f}/{self.init_area:.2f} ({max_area/self.init_area*100:.2f}%)")
                # 剩余面积很小时，直接开始交替按键
                logger.info("开始连续交替按键以尝试退出拉扯鱼线状态")
                if self._perform_ad_key_combination():
                    # 如果在交替按键过程中检测到收线状态
                    return 2
                return 1
                
            logger.info(f"剩余面积足够: {max_area:.2f}/{self.init_area:.2f} ({max_area/self.init_area*100:.2f}%)")
            return 0
                
        except Exception as e:
            logger.error(f"检查剩余面积出错: {e}")
            # 出错时也立即开始交替按键
            logger.info("检查面积出错，立即开始交替按a-d键")
            if self._perform_ad_key_combination():
                # 如果在交替按键过程中检测到收线状态
                return 2
            return 0
    
    # 添加新方法，将a-d交替按键逻辑封装为独立函数
    def _perform_ad_key_combination(self):
        """执行a-d交替按键并检测状态，尝试退出拉扯鱼线状态

        返回：
            True: 如果检测到收线状态
            False: 如果未检测到收线状态
        """
        # 最大按键次数限制
        max_presses = 3
        press_count = 0

        import time

        # 快速检查是否处于收线状态 - 使用双重检查
        if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
            logger.info("交替按键开始前检测到收线状态，立即返回")
            return True

        while press_count < max_presses:
            # 按下 a 键前再次检查收线状态
            if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
                logger.info("按下a键前检测到收线状态，立即返回")
                return True

            # 按下 a 键
            self.input_handler.press('a', 0.15)  # 恢复原来的按键时间
            time.sleep(0.05)  # 减少等待时间，更频繁检查

            # 检查是否已经进入收线状态 - 使用双重检查
            if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
                logger.info("按下a键后检测到收线状态，立即返回")
                return True

            # 检查状态
            if not self._check_jerky_line_state():
                logger.info(f"a键按下后，已退出拉扯鱼线状态")
                break

            # 按下 d 键前再次检查收线状态
            if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
                logger.info("按下d键前检测到收线状态，立即返回")
                return True

            # 按下 d 键
            self.input_handler.press('d', 0.15)  # 恢复原来的按键时间
            time.sleep(0.05)  # 减少等待时间，更频繁检查

            # 检查是否已经进入收线状态 - 使用双重检查
            if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
                logger.info("按下d键后检测到收线状态，立即返回")
                return True

            # 检查状态
            if not self._check_jerky_line_state():
                logger.info(f"d键按下后，已退出拉扯鱼线状态")
                break

            press_count += 1
            # 每次完成一对按键后检查状态
            logger.info(f"完成第 {press_count} 次 a-d 按键组合，拉扯状态: {'继续中' if self._check_jerky_line_state() else '已结束'}")

        if press_count >= max_presses:
            logger.info("达到最大按键尝试次数，可能仍处于拉扯鱼线状态")
        else:
            logger.info("成功退出拉扯鱼线状态")

        return False  # 未检测到收线状态
    
    def _press_keys(self, key, interval=0.3):
        """
        按下指定键，检测面积变化

        参数:
            key: 要按下的键
            interval: 按键间隔
        """
        try:
            from config_manager import config_manager

            # 检查是否已经进入收线状态
            if self._is_line_retrieved_state():
                logger.info(f"按键 {key} 操作前检测到收线状态，立即中断")
                return

            # 检查状态处理器的收线状态
            if self.state_handler and self.state_handler.running_state == 3:
                logger.info(f"按键 {key} 操作前检测到状态处理器已为收线状态(3)，立即中断")
                return

            logger.info(f"开始按键操作: 按下 {key} 键, 持续时间: {interval}秒")
            # 记录初始面积
            init_captures = self.area_capture.capture_one_shot()
            if not init_captures['full_region']:
                logger.info(f"按键 {key} 操作中无法捕获面积区域图像")
                return

            init_img = cv2.cvtColor(np.array(init_captures['full_region']), cv2.COLOR_RGB2BGR)
            init_hsv = cv2.cvtColor(init_img, cv2.COLOR_BGR2HSV)
            init_mask = cv2.inRange(init_hsv, self.lower, self.upper)
            init_contours, _ = cv2.findContours(init_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not init_contours:
                logger.info(f"按键 {key} 操作中未检测到轮廓")
                # 立即开始交替按a-d键
                logger.info("未检测到轮廓，立即开始交替按a-d键")
                return

            init_area = max([cv2.contourArea(c) for c in init_contours])
            logger.info(f"按键 {key} 操作前面积: {init_area:.2f}")

            # 按下指定键 - 使用原来的按键时间
            self.input_handler.press(key, interval)

            # 检查是否已经进入收线状态
            if self._is_line_retrieved_state():
                logger.info(f"按键 {key} 操作后检测到收线状态，立即中断")
                return

            # 检查状态处理器的收线状态
            if self.state_handler and self.state_handler.running_state == 3:
                logger.info(f"按键 {key} 操作后检测到状态处理器已为收线状态(3)，立即中断")
                return
                
            # 记录按键后的面积
            post_captures = self.area_capture.capture_one_shot()
            if not post_captures['full_region']:
                logger.info(f"按键 {key} 操作后无法捕获面积区域图像")
                return
                
            post_img = cv2.cvtColor(np.array(post_captures['full_region']), cv2.COLOR_RGB2BGR)
            post_hsv = cv2.cvtColor(post_img, cv2.COLOR_BGR2HSV)
            post_mask = cv2.inRange(post_hsv, self.lower, self.upper)
            post_contours, _ = cv2.findContours(post_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not post_contours:
                logger.info(f"按键 {key} 操作后未检测到轮廓")
                return
                
            post_area = max([cv2.contourArea(c) for c in post_contours])
            logger.info(f"按键 {key} 操作后面积: {post_area:.2f}, 变化: {init_area-post_area:.2f}")
            
            # 更新缩放因子
            self._update_scale_factors()
            
            # 获取缩放后的area_decrease值
            area_decrease = config_manager.get_scaled_threshold(
                "fishing.thresholds.area_decrease", 
                self.scale_x, 
                self.scale_y, 
                5
            )
            logger.info(f"使用缩放后的面积阈值: {area_decrease:.2f}, 缩放因子: ({self.scale_x:.2f}, {self.scale_y:.2f})")
            
            if init_area - post_area > area_decrease:
                logger.info(f"面积有效减少: {init_area:.2f} -> {post_area:.2f}, 减少: {init_area-post_area:.2f}, 继续按 {key}")
                # 持续按键直到面积不再减少，添加最大循环次数限制
                max_loops = 50  # 最大循环次数
                loop_count = 0
                while loop_count < max_loops:
                    # 先检查是否进入收线状态 - 使用双重检查
                    if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
                        logger.info(f"持续按住 {key} 过程中检测到收线状态，立即释放按键并中断")
                        self.input_handler.press_up(key)  # 确保释放按键
                        return

                    pre_area = post_area
                    # 修改为按下不释放
                    self.input_handler.press(key, 0, keyup=False)
                    logger.info(f"持续按住 {key} 键不释放")
                    # 继续保持按键按下，适当延迟以避免过度采样
                    import time
                    time.sleep(0.1)  # 减少延迟时间，更频繁检查状态

                    # 再次检查是否进入收线状态 - 使用双重检查
                    if self._is_line_retrieved_state() or (self.state_handler and self.state_handler.running_state == 3):
                        logger.info(f"持续按住 {key} 延迟后检测到收线状态，立即释放按键并中断")
                        self.input_handler.press_up(key)  # 确保释放按键
                        return
                    
                    # 检测面积
                    captures = self.area_capture.capture_one_shot()
                    if not captures['full_region']:
                        # 跳出循环前释放按键
                        self.input_handler.press_up(key)
                        logger.info(f"无法捕获面积区域图像，释放按键 {key}")
                        break
                        
                    img = cv2.cvtColor(np.array(captures['full_region']), cv2.COLOR_RGB2BGR)

                    # 再次检查是否进入收线状态（通过状态处理器）
                    if self._is_line_retrieved_state():
                        logger.info(f"持续按住 {key} 过程中通过状态处理器检测到收线状态，立即释放按键并中断")
                        self.input_handler.press_up(key)  # 确保释放按键
                        return
                    
                    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                    mask = cv2.inRange(hsv, self.lower, self.upper)
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    if not contours:
                        # 跳出循环前释放按键
                        self.input_handler.press_up(key)
                        logger.info(f"未检测到轮廓，释放按键 {key}")
                        break
                        
                    post_area = max([cv2.contourArea(c) for c in contours])
                    logger.info(f"持续按住 {key} 后面积: {post_area:.2f}, 变化: {pre_area-post_area:.2f}")
                    
                    # 如果面积不再减少，跳出循环
                    if pre_area - post_area <= area_decrease:
                        # 跳出循环前释放按键
                        self.input_handler.press_up(key)
                        logger.info(f"面积不再有效减少，释放按键 {key}, 最终面积: {post_area:.2f}")
                        break
                    
                    loop_count += 1
                    if loop_count >= max_loops:
                        self.input_handler.press_up(key)
                        logger.info(f"达到最大循环次数，释放按键 {key}")
                        break

            else:
                logger.info(f"面积未有效减少: {init_area:.2f} -> {post_area:.2f}, 变化: {init_area-post_area:.2f}")
                
        except Exception as e:
            # 确保异常情况下释放按键
            try:
                self.input_handler.press_up(key)
                logger.info(f"异常情况下释放按键 {key}")
            except:
                pass
            logger.error(f"按键操作出错: {e}") 

    def _check_jerky_line_state(self):
        """
        检查当前是否仍处于拉扯鱼线状态
        
        返回:
            True: 仍处于拉扯鱼线状态
            False: 已退出拉扯鱼线状态
        """
        try:
            # 使用区域截图器获取当前屏幕
            captures = self.area_capture.capture_one_shot()
            if not captures['full_region']:
                logger.info("无法捕获屏幕进行拉扯状态检测")
                return True  # 默认维持当前状态
            
            # 转换为OpenCV格式
            img = cv2.cvtColor(np.array(captures['full_region']), cv2.COLOR_RGB2BGR)
            
            # 方法1: 使用模板匹配检测状态
            from config_manager import config_manager
            import os
            
            # 获取模板目录路径
            template_dir = config_manager.get("paths.templates", "./img/templates")
            
            # 不同状态的模板文件名
            jerky_template = os.path.join(template_dir, "拉扯鱼线.png")
            other_templates = [
                os.path.join(template_dir, "收线.png"),
                os.path.join(template_dir, "跳过.png"),
                os.path.join(template_dir, "收竿.png"),
                os.path.join(template_dir, "提竿.png")
            ]
            
            # 使用基于不同分辨率的模板匹配
            from match.template_matcher import TemplateMatcher
            matcher = TemplateMatcher()
            window_size = (self.area_capture.window_width, self.area_capture.window_height)
            
            # 检查拉扯鱼线模板是否存在
            if os.path.exists(jerky_template):
                # 加载模板
                jerky_template_img = cv2.imread(jerky_template, cv2.IMREAD_COLOR)
                if jerky_template_img is not None:
                    # 添加模板到匹配器
                    matcher.load_templates([{"name": "拉扯鱼线", "path": jerky_template, "threshold": 0.8}], window_size)
                    
                    # 进行模板匹配
                    match_result = matcher.match_template(img, "拉扯鱼线")
                    
                    if match_result:
                        logger.info(f"模板匹配检测到拉扯鱼线状态，匹配度: {match_result['score']:.4f}")
                        return True
                    else:
                        logger.info(f"模板匹配未检测到拉扯鱼线状态")
            else:
                logger.debug(f"拉扯鱼线模板不存在: {jerky_template}")
            
            # 检查其他状态模板
            for template_path in other_templates:
                if os.path.exists(template_path):
                    template_img = cv2.imread(template_path, cv2.IMREAD_COLOR)
                    if template_img is not None:
                        # 添加模板到匹配器
                        template_name = os.path.basename(template_path).replace(".png", "")
                        matcher.load_templates([{"name": template_name, "path": template_path, "threshold": 0.8}], window_size)
                        
                        # 进行模板匹配
                        match_result = matcher.match_template(img, template_name)
                        
                        if match_result:
                            logger.info(f"检测到其他状态: {template_name}，匹配度: {match_result['score']:.4f}")
                            return False
                else:
                    logger.debug(f"状态模板不存在: {template_path}")
            
            # 方法2: 使用颜色特征检测
            # 如果模板匹配不可靠，可以通过检测屏幕上特定区域的颜色特征来判断
            
            # 定义拉扯鱼线状态的颜色特征 (根据实际情况调整)
            jerky_lower = np.array([22, 54, 250])  # HSV 下限
            jerky_upper = np.array([25, 88, 255])  # HSV 上限
            
            # 转换到HSV色彩空间
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # 提取指定颜色范围
            mask = cv2.inRange(hsv, jerky_lower, jerky_upper)
            
            # 计算特定颜色的像素占比
            total_pixels = mask.shape[0] * mask.shape[1]
            color_pixels = cv2.countNonZero(mask)
            color_ratio = color_pixels / total_pixels
            
            # 根据颜色占比判断状态
            color_threshold = 0.01  # 阈值，根据实际情况调整
            if color_ratio > color_threshold:
                logger.info(f"颜色特征检测到拉扯鱼线状态，颜色占比: {color_ratio:.4f}")
                return True
                
            logger.info(f"颜色特征未检测到拉扯鱼线状态，颜色占比: {color_ratio:.4f}")
            return False
            
        except Exception as e:
            logger.error(f"检查拉扯鱼线状态出错: {e}")
            return True  # 出错时默认维持当前状态 

    # 添加新方法，用于检测是否处于收线状态
    def _is_line_retrieved_state(self):
        """
        检查当前是否处于收线状态

        返回:
            True: 处于收线状态
            False: 不处于收线状态
        """
        try:
            # 优先检查状态处理器的状态
            if self.state_handler and hasattr(self.state_handler, 'running_state'):
                if self.state_handler.running_state == 3:  # 收线状态
                    logger.info("通过状态处理器检测到收线状态")
                    return True

            # 如果没有状态处理器或状态不是收线，返回False
            # 移除了冗余的模板匹配，因为状态处理器已经在做这个工作
            return False

        except Exception as e:
            logger.error(f"检查收线状态出错: {e}")
            return False  # 出错时默认不处于收线状态

    def _notify_line_retrieved_state(self):
        """
        当检测到收线状态时通知状态处理器，并立即中断所有正在进行的操作
        """
        try:
            logger.info("检测到收线状态，立即执行紧急停止程序")

            # 使用统一的按键释放方法
            self._release_all_keys("检测到收线状态")

            # 直接使用传入的状态处理器
            if self.state_handler:
                # 强制设置状态为收线状态
                self.state_handler.running_state = 3  # 收线状态
                self.state_handler.jerky_line_flag = False  # 关闭拉扯鱼线标志
                self.state_handler.line_retrieved_flag = True  # 设置收线标志

                logger.info("成功强制更新状态为收线状态，立即开始收线操作")

            # 直接开始执行收线操作，无需等待主循环
            from controller.MouseController import mouse
            logger.info("立即开始执行收线操作 - 直接点击右键")
            for i in range(5):  # 增加点击次数，确保能成功收线
                mouse.click_right(0.05)
                import time
                time.sleep(0.05)
            
        except Exception as e:
            logger.error(f"通知收线状态出错: {e}")
            # 即使出错，也尝试点击右键
            try:
                from controller.MouseController import mouse
                logger.info("尝试直接点击右键进行收线")
                for i in range(5):
                    mouse.click_right(0.05)
                    import time
                    time.sleep(0.05)
            except:
                pass

    def _release_all_keys(self, reason=""):
        """
        释放所有按键 - 统一的按键释放方法，减少重复代码

        参数:
            reason: 释放按键的原因，用于日志记录
        """
        all_keys = ['a', 'd', 's', 'w', 'f']
        for key in all_keys:
            try:
                self.input_handler.press_up(key)
                if reason:
                    logger.info(f"{reason}，强制释放按键: {key}")
                else:
                    logger.info(f"强制释放按键: {key}")
            except Exception as e:
                logger.debug(f"释放按键 {key} 时出错: {e}")