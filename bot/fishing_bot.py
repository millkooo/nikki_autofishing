import logging
import os

from Ui_Manage.WindowManager import WinControl
from bot.line_handler import LineHandler
from bot.main_loop import MainLoopHandler
from bot.state_handler import StateHandler
from capture.ScreenCaptureExtractor import ScreenCaptureExtractor
from config_manager import config_manager, CONFIG
from controller.KeyboardController import get_input_handler
from match.template_matcher import TemplateMatcher

# 配置日志
logger = logging.getLogger(__name__)

class FishingBot:
    """钓鱼机器人类，实现自动钓鱼功能"""
    
    def __init__(self):
        """初始化钓鱼机器人"""
        self.running = False
        self.stop_flag = False
        
        # 使用配置管理器获取配置
        self.config = CONFIG
        
        # 打印配置内容，检查是否正确加载
        logger.info(f"配置项: {list(self.config.keys())}")
        
        # 获取fishing配置并检查是否存在必要的配置项
        fishing_config = config_manager.get_fishing_config()
        if not fishing_config:
            logger.warning("警告: 配置中缺少fishing项")
        
        # 增加钓鱼计数相关变量
        self.fishing_count = 0  # 钓鱼成功次数
        self.target_fishing_count = 0  # 目标钓鱼次数 (0表示无限)
        self.continuous_fishing = False  # 是否开启连续钓鱼
        
        # 从配置文件中加载最大连续钓鱼次数
        self.max_continuous_count = config_manager.get("fishing.continuous.max_times", 3)
        # 确保最大连续钓鱼次数有一个有效值
        if not isinstance(self.max_continuous_count, int) or self.max_continuous_count <= 0:
            self.max_continuous_count = 3
            logger.info(f"设置默认最大连续钓鱼次数: {self.max_continuous_count}")
        else:
            logger.info(f"从配置加载最大连续钓鱼次数: {self.max_continuous_count}")
        
        # 初始化窗口管理器
        self.window_manager = WinControl()
        self.hwnd = self.window_manager.find_target_window(config_manager.get_window_config())
        
        # 添加游戏窗口存在标志
        self.game_window_found = self.hwnd is not None
        
        if not self.game_window_found:
            logger.error("未找到游戏窗口")
            # 不再退出，继续初始化其他组件
            
        # 初始化输入控制器
        self.input_handler = get_input_handler(self.config)

        # 设置F9键停止回调
        self.input_handler.external_on_key_press = self._on_f9_key_press

        # 初始化模板匹配器，设置各种状态的模板
        self.template_matcher = TemplateMatcher()

        # 获取窗口尺寸
        window_width, window_height = self._get_window_size()

        # 加载模板配置
        self._load_templates(window_width, window_height)
        
        # 直接计算区域位置，不使用配置文件中的设置
        # 面积检测区域：窗口中心区域，宽度和高度为窗口的1/3
        area_width = int(window_width * 0.33)
        area_height = int(window_height * 0.33)
        area_x = (window_width - area_width) // 2
        area_y = (window_height - area_height) // 2
        
        # 模板匹配区域：右下角区域，宽度为窗口的1/5，高度为窗口的1/6
        ocr_width = int(window_width * 0.33)
        ocr_height = int(window_height * 0.16)
        ocr_x = window_width - ocr_width
        ocr_y = window_height - ocr_height
        
        logger.info(f"模板匹配检测区域: x={ocr_x}, y={ocr_y}, w={ocr_width}, h={ocr_height}")
        logger.info(f"面积检测区域: x={area_x}, y={area_y}, w={area_width}, h={area_height}")
        
        # 初始化屏幕截图提取器，为不同区域创建不同的提取器
        self.temp_capture = ScreenCaptureExtractor(self.hwnd)
        self.temp_capture.capture_region = (ocr_x, ocr_y, ocr_width, ocr_height)
        # 设置提取器的位置为区域内的位置，而不是区域的左上角
        self.temp_capture.positions = [(ocr_x + ocr_width // 2, ocr_y + ocr_height // 2)]
        self.temp_capture.region_size = min(ocr_width, ocr_height) // 2  # 减小区域大小，避免超出范围
        # 确保获取窗口尺寸并调整区域
        self.temp_capture.update_window_size()
        self.temp_capture.adjust_region_to_window_bounds()
        
        self.area_capture = ScreenCaptureExtractor(self.hwnd)
        self.area_capture.capture_region = (area_x, area_y, area_width, area_height)
        # 设置提取器的位置为区域内的位置，而不是区域的左上角
        self.area_capture.positions = [(area_x + area_width//2, area_y + area_height//2)]
        self.area_capture.region_size = min(area_width, area_height) // 2  # 减小区域大小，避免超出范围
        # 确保获取窗口尺寸并调整区域
        self.area_capture.update_window_size()
        self.area_capture.adjust_region_to_window_bounds()
        
        # 初始化子模块
        self.state_handler = StateHandler(self.template_matcher, self.temp_capture, self.input_handler)
        self.line_handler = LineHandler(self.input_handler, self.area_capture, self.state_handler)
        self.main_loop_handler = MainLoopHandler(self.state_handler, self.input_handler, self.line_handler)

        # 初始化键盘监听器
        self.keyboard_listener = None
        
        # 添加向后兼容的属性代理
        self._setup_compatibility()
    
    def _setup_compatibility(self):
        """设置向后兼容性属性和方法"""
        # 为了与旧代码兼容，让running_state等属性可以直接通过FishingBot访问
        self.__class__.running_state = property(
            lambda self: self.state_handler.running_state,
            lambda self, value: setattr(self.state_handler, 'running_state', value)
        )
        
        self.__class__.jerky_line_flag = property(
            lambda self: self.state_handler.jerky_line_flag,
            lambda self, value: setattr(self.state_handler, 'jerky_line_flag', value)
        )
        
        self.__class__.line_retrieved_flag = property(
            lambda self: self.state_handler.line_retrieved_flag,
            lambda self, value: setattr(self.state_handler, 'line_retrieved_flag', value)
        )
        
        # 确保fishing_count一致性
        self.__class__.fishing_count = property(
            lambda self: self.state_handler.fishing_count,
            lambda self, value: setattr(self.state_handler, 'fishing_count', value)
        )
        
        # 传递init_area属性
        self.__class__.init_area = property(
            lambda self: self.line_handler.init_area,
            lambda self, value: setattr(self.line_handler, 'init_area', value)
        )

    def _get_template_dir(self):
        """获取模板目录路径"""
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_dir = os.path.join(base_path, "img", "templates")

        # 确保模板目录存在
        if not os.path.exists(template_dir):
            os.makedirs(template_dir)
            logger.info(f"创建模板目录: {template_dir}")

        return template_dir

    def _get_window_size(self):
        """获取窗口尺寸"""
        window_width = 1920
        window_height = 1080

        if self.game_window_found:
            window_rect = self.window_manager.get_window_rect(self.hwnd)
            if window_rect:
                window_width = window_rect[2] - window_rect[0]
                window_height = window_rect[3] - window_rect[1]
                logger.info(f"窗口实际尺寸: {window_width}x{window_height}")
            else:
                logger.warning("无法获取窗口尺寸，使用默认尺寸: 1920x1080")
        else:
            logger.warning("未找到游戏窗口，使用默认尺寸: 1920x1080")

        return window_width, window_height

    def _get_template_configs(self, threshold=0.9):
        """获取模板配置"""
        template_dir = self._get_template_dir()

        return [
            {"name": "收竿", "path": os.path.join(template_dir, "collect.png"), "threshold": threshold},
            {"name": "提竿", "path": os.path.join(template_dir, "cast.png"), "threshold": threshold},
            {"name": "拉扯鱼线", "path": os.path.join(template_dir, "pull.png"), "threshold": threshold},
            {"name": "收线", "path": os.path.join(template_dir, "reel.png"), "threshold": threshold},
            {"name": "跳过", "path": os.path.join(template_dir, "skip.png"), "threshold": threshold},
        ]

    def _load_templates(self, window_width, window_height):
        """加载模板配置"""
        template_configs = self._get_template_configs()
        window_size = (window_width, window_height)
        self.template_matcher.load_templates(template_configs, window_size)

    def _ensure_game_window(self):
        """确保游戏窗口存在，如果不存在则尝试重新查找"""
        if not self.game_window_found:
            # 重新尝试查找游戏窗口
            self.hwnd = self.window_manager.find_target_window(config_manager.get_window_config())
            self.game_window_found = self.hwnd is not None

            if not self.game_window_found:
                logger.error("未找到游戏窗口")
                return False
        return True

    def _prepare_for_start(self, threshold=0.88):
        """准备启动的通用逻辑"""
        # 检查游戏窗口
        if not self._ensure_game_window():
            return False

        # 获取窗口尺寸并加载模板
        window_width, window_height = self._get_window_size()
        self._load_templates(window_width, window_height)

        # 设置运行状态
        self.running = True
        self.stop_flag = False

        # 重置状态
        self.state_handler.reset_state()

        # 激活游戏窗口
        self.window_manager.activate_window(self.hwnd)

        return True
    
    def start(self, target_count=0, continuous=False):
        """
        开始钓鱼机器人
        
        参数:
            target_count: 目标钓鱼次数，0表示无限次
            continuous: 是否开启连续钓鱼
        """
        if self.running:
            logger.warning("钓鱼机器人已经在运行")
            return
        
        # 准备启动（使用较高的阈值以提高准确性）
        if not self._prepare_for_start(threshold=0.9):
            logger.error("未找到游戏窗口，无法启动钓鱼机器人")
            return

        # 设置目标钓鱼次数和连续钓鱼标志
        self.state_handler.set_target_count(target_count)
        self.main_loop_handler.set_continuous_fishing(continuous, self.max_continuous_count)

        # 设置各个处理器的运行状态
        self.state_handler.set_running_state(True)
        self.main_loop_handler.set_running_state(True)
        
        # 启动状态检测线程
        self.state_handler.start_detection()
        
        # 启动主循环线程
        self.main_loop_handler.start_main_loop()

        logger.info(f"钓鱼机器人已启动 - 目标钓鱼次数: {target_count if target_count > 0 else '无限'}, 连续钓鱼: {'开启' if continuous else '关闭'}")
    
    def stop(self):
        """停止钓鱼机器人"""
        self.stop_flag = True
        self.running = False
        
        # 停止各个处理器
        self.state_handler.set_running_state(False, True)
        self.main_loop_handler.set_running_state(False, True)
        # 记录钓鱼次数
        fishing_count_record = self.state_handler.get_fishing_count()
        
        # 停止状态检测线程
        self.state_handler.stop_detection()
        
        # 停止主循环线程
        self.main_loop_handler.stop_main_loop()
        
        # 停止键盘监听
        self._stop_keyboard_listener()
            
        logger.info(f"钓鱼机器人已停止 - 成功钓鱼次数: {fishing_count_record}")

    def start_template_only(self):
        """
        仅启动模板识别线程，不执行任何钓鱼操作
        """
        if self.running:
            logger.warning("钓鱼机器人已经在运行")
            return
        
        # 准备启动（使用较低的阈值以提高检测灵敏度）
        if not self._prepare_for_start(threshold=0.8):
            logger.error("未找到游戏窗口，无法启动模板识别")
            return

        # 只设置状态处理器的运行状态
        self.state_handler.set_running_state(True)
        
        # 启动状态检测线程
        self.state_handler.start_detection()
        
        logger.info("已启动仅模板识别模式 - 不会执行任何钓鱼操作")
    
    def _on_f9_key_press(self, key, key_char):
        """F9键按下回调，处理停止信号"""
        from pynput.keyboard import Key
        if key == Key.f9:
            logger.info("检测到F9键，执行停止操作")
            if self.running:
                self.stop()
            else:
                logger.info("钓鱼机器人未运行，忽略F9键")

    def _stop_keyboard_listener(self):
        """停止键盘监听器"""
        if self.keyboard_listener and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()
            logger.info("键盘监听器已停止")

    def get_fishing_count(self):
        """获取当前钓鱼次数"""
        return self.state_handler.get_fishing_count()

    def get_current_state_name(self):
        """获取当前状态名称"""
        return self.state_handler.get_current_state()