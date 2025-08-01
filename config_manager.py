import json
import os
import sys
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理类，负责加载、保存和管理配置"""
    
    def __init__(self):
        """初始化配置管理器"""
        self.config = self.load_config()
    
    def load_config(self):
        """从JSON文件加载配置
        
        Returns:
            dict: 配置字典
        """
        try:
            # 获取配置文件路径
            config_path = self.get_config_path()
                
            if not os.path.exists(config_path):
                logger.warning(f"配置文件不存在: {config_path}，将创建基本配置")
                # 创建基本配置
                basic_config = self._create_basic_config()
                
                # 尝试保存基本配置
                try:
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(basic_config, f, ensure_ascii=False, indent=4)
                    logger.info(f"成功创建基本配置文件: {config_path}")
                except Exception as e:
                    logger.error(f"创建基本配置文件失败: {e}")
                
                return basic_config
                
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            logger.info(f"成功加载配置文件: {config_path}")
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}，将使用基本配置")
            return self._create_basic_config()
    
    def _create_basic_config(self):
        """创建基本配置
        
        Returns:
            dict: 基本配置字典
        """
        return {
            "window": {
                "comment": "窗口配置 - 用于定位游戏窗口",
                "title_part": "无限暖暖",
                "window_class": "UnrealWindow",
                "process_exe": "X6Game-Win64-Shipping.exe"
            },
            "fishing": {
                "comment": "钓鱼相关配置",
                "reel_key": "right_click",
                "region_area": {
                    "x_offset": 270,
                    "y_offset": 220,
                    "width": 1000,
                    "height": 400
                },
                "region_ocr": {
                    "x_offset": 1477,
                    "y_offset": 936,
                    "width": 426,
                    "height": 144
                },
                "thresholds": {
                    "area_decrease": 5
                },
                "continuous": {
                    "max_times": 10
                },
                "auto_keys": {
                    "press_f_when_w": False,
                    "press_wf_toggle": False,
                    "toggle_key": "q"
                }
            }
        }
    
    def get_config_path(self):
        """获取配置文件路径
        
        Returns:
            str: 配置文件的完整路径
        """
        try:
            # 获取程序所在目录（而不是当前工作目录）
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, 'config.json')
            
            # 记录详细的路径信息以便调试
            logger.info(f"脚本目录: {script_dir}")
            logger.info(f"当前工作目录: {os.getcwd()}")
            logger.info(f"配置文件路径: {config_path}")
            
            # 检查路径是否可写
            try:
                if os.path.exists(config_path):
                    # 检查文件是否可写
                    if not os.access(config_path, os.W_OK):
                        logger.warning(f"警告: 配置文件 {config_path} 不可写")
                else:
                    # 检查目录是否可写
                    if not os.access(os.path.dirname(config_path), os.W_OK):
                        logger.warning(f"警告: 目录 {os.path.dirname(config_path)} 不可写")
            except Exception as e:
                logger.warning(f"检查文件权限时出错: {e}")
            
            return config_path
        except Exception as e:
            # 如果出错，回退到当前工作目录
            fallback_path = os.path.join(os.getcwd(), 'config.json')
            logger.error(f"获取配置路径出错: {e}，回退到: {fallback_path}")
            return fallback_path
    
    def save_config(self):
        """保存配置到JSON文件
        
        Returns:
            bool: 保存成功返回True，否则返回False
        """
        try:
            config_path = self.get_config_path()
            
            # 备份原配置文件
            if os.path.exists(config_path):
                backup_path = f"{config_path}.bak"
                try:
                    os.replace(config_path, backup_path)
                except:
                    os.rename(config_path, backup_path)
            
            # 保存新配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
                
            logger.info(f"配置已保存到: {config_path}")
            return True
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def get(self, key, default=None):
        """获取配置项，支持多级键，使用点号分隔
        
        Args:
            key (str): 配置键，如"fishing.region_ocr.x_offset"
            default: 如果键不存在，返回的默认值
            
        Returns:
            配置值或默认值
        """
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key, value):
        """设置配置项，支持多级键，使用点号分隔
        
        Args:
            key (str): 配置键，如"fishing.region_ocr.x_offset"
            value: 要设置的值
            
        Returns:
            bool: 设置成功返回True，否则返回False
        """
        keys = key.split('.')
        current = self.config
        
        try:
            # 遍历键路径，直到倒数第二级
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
                
            # 设置最后一级的值
            current[keys[-1]] = value
            return True
        except Exception as e:
            logger.error(f"设置配置项失败: {e}")
            return False
    
    def get_window_config(self):
        """获取窗口配置"""
        return self._get_config_section("window")

    def get_fishing_config(self):
        """获取钓鱼配置"""
        return self._get_config_section("fishing")

    def _get_config_section(self, section_name, default=None):
        """
        通用的配置段获取方法 - 减少重复代码

        参数:
            section_name: 配置段名称
            default: 默认值

        返回:
            dict: 配置段内容
        """
        if default is None:
            default = {}
        return self.config.get(section_name, default)
    
    def get_region_config(self, region_type):
        """获取区域配置
        
        Args:
            region_type (str): 区域类型，"ocr"或"area"
            
        Returns:
            dict: 区域配置
        """
        fishing_config = self.get_fishing_config()
        region_key = f"region_{region_type}"
        
        return fishing_config.get(region_key, {})
    
    def calculate_relative_region(self, region_type, window_width, window_height):
        """计算相对位置的区域

        Args:
            region_type (str): 区域类型，"ocr"或"area"
            window_width (int): 窗口宽度
            window_height (int): 窗口高度

        Returns:
            tuple: (x, y, width, height) 计算后的区域
        """
        if region_type == "ocr":
            # 模板匹配区域：右下角区域，宽度为窗口的1/4，高度为窗口的1/6
            width = int(window_width * 0.4)
            height = int(window_height * 0.12)
            
            # 从右下角定位，留出一点边距
            x = window_width - width - 20
            y = window_height - height - 20
            
        elif region_type == "area":
            # 面积检测区域：窗口中心区域，宽度和高度为窗口的1/3
            width = int(window_width * 0.43)
            height = int(window_height * 0.43)
            
            # 居中定位
            x = (window_width - width) // 2
            y = (window_height - height) // 2
        else:
            logger.warning(f"未知的区域类型: {region_type}")
            return (0, 0, 0, 0)
        
        return (x, y, width, height)

    def get_scaled_region(self, region_type, scale_x, scale_y):
        """获取按比例缩放后的区域配置
        
        Args:
            region_type (str): 区域类型，"ocr"或"area"
            scale_x (float): X轴缩放比例
            scale_y (float): Y轴缩放比例
            
        Returns:
            tuple: (x, y, width, height) 缩放后的区域
        """
        # 直接使用实际窗口尺寸计算区域，忽略配置文件中的位置设置
        window_width = int(1920 * scale_x)
        window_height = int(1080 * scale_y)
        
        # 使用相对位置计算区域
        return self.calculate_relative_region(region_type, window_width, window_height)
    
    def get_scaled_threshold(self, threshold_key, scale_x, scale_y, default_value=None):
        """获取按比例缩放后的阈值
        
        Args:
            threshold_key (str): 阈值键名，如"fishing.thresholds.area_decrease"
            scale_x (float): X轴缩放比例
            scale_y (float): Y轴缩放比例
            default_value: 如果键不存在，返回的默认值
            
        Returns:
            float: 缩放后的阈值
        """
        # 获取原始阈值
        base_value = self.get(threshold_key, default_value)
        
        # 如果原始值为None或非数值，直接返回
        if base_value is None or not isinstance(base_value, (int, float)):
            return base_value
        
        # 计算面积缩放因子（面积是二维的，所以使用面积比例）
        area_scale = scale_x * scale_y
        
        # 缩放阈值
        scaled_value = base_value * area_scale
        
        # 确保缩放后的值至少为1
        return max(1.0, scaled_value)
        
    def save_region_settings(self, region_type, x, y, width, height):
        """此方法已禁用，不再保存区域设置到配置文件
        
        Args:
            region_type (str): 区域类型，"ocr"或"area"
            x (int): X坐标
            y (int): Y坐标
            width (int): 宽度
            height (int): 高度
            
        Returns:
            bool: 总是返回True
        """
        logger.info(f"区域设置不再保存到配置文件")
        return True

# 创建全局配置管理器实例
config_manager = ConfigManager()
CONFIG = config_manager.config 