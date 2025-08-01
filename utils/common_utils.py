"""
通用工具模块 - 减少代码冗余
包含常用的错误处理、状态检查和日志记录功能
"""

import logging
import functools
import time
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


def retry_on_failure(max_attempts: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """
    重试装饰器 - 减少重复的重试逻辑
    
    参数:
        max_attempts: 最大尝试次数
        delay: 重试间隔（秒）
        exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(f"{func.__name__} 失败 (尝试 {attempt + 1}/{max_attempts}): {e}")
                        time.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} 最终失败: {e}")
            
            raise last_exception
        return wrapper
    return decorator


def safe_execute(func: Callable, default_return: Any = None, log_errors: bool = True) -> Any:
    """
    安全执行函数 - 统一错误处理
    
    参数:
        func: 要执行的函数
        default_return: 出错时的默认返回值
        log_errors: 是否记录错误日志
        
    返回:
        函数执行结果或默认值
    """
    try:
        return func()
    except Exception as e:
        if log_errors:
            logger.error(f"执行 {func.__name__ if hasattr(func, '__name__') else 'function'} 出错: {e}")
        return default_return


class StateValidator:
    """状态验证器 - 统一状态检查逻辑"""
    
    @staticmethod
    def is_valid_state(state: int, valid_states: list) -> bool:
        """检查状态是否有效"""
        return state in valid_states
    
    @staticmethod
    def is_fishing_state(state: int) -> bool:
        """检查是否为钓鱼相关状态"""
        fishing_states = [1, 2, 3, 4]  # 收竿/提竿, 拉扯鱼线, 收线, 跳过
        return state in fishing_states
    
    @staticmethod
    def is_reel_state(state: int) -> bool:
        """检查是否为收线状态"""
        return state == 3
    
    @staticmethod
    def is_jerky_state(state: int) -> bool:
        """检查是否为拉扯鱼线状态"""
        return state == 2


class ConfigValidator:
    """配置验证器 - 统一配置验证逻辑"""
    
    @staticmethod
    def validate_window_config(config: dict) -> bool:
        """验证窗口配置"""
        required_keys = ["window_class", "process_exe"]
        return all(key in config for key in required_keys)
    
    @staticmethod
    def validate_fishing_config(config: dict) -> bool:
        """验证钓鱼配置"""
        required_keys = ["reel_key", "region_area", "region_ocr"]
        return all(key in config for key in required_keys)
    
    @staticmethod
    def validate_region_config(config: dict) -> bool:
        """验证区域配置"""
        required_keys = ["x_offset", "y_offset", "width", "height"]
        return all(key in config for key in required_keys)


class LoggerHelper:
    """日志助手 - 统一日志格式和级别"""
    
    @staticmethod
    def log_state_change(old_state: int, new_state: int, state_names: dict):
        """记录状态变更"""
        old_name = state_names.get(old_state, f"未知状态({old_state})")
        new_name = state_names.get(new_state, f"未知状态({new_state})")
        logger.info(f"状态变更: [{old_name}] -> [{new_name}]")
    
    @staticmethod
    def log_operation_result(operation: str, success: bool, details: str = ""):
        """记录操作结果"""
        if success:
            logger.info(f"{operation} 成功{': ' + details if details else ''}")
        else:
            logger.error(f"{operation} 失败{': ' + details if details else ''}")
    
    @staticmethod
    def log_fishing_count(current: int, target: int):
        """记录钓鱼次数"""
        target_str = str(target) if target > 0 else "无限"
        logger.info(f"钓鱼进度: {current}/{target_str}")


class PerformanceMonitor:
    """性能监控器 - 监控方法执行时间"""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            logger.debug(f"{self.name} 执行时间: {duration:.3f}秒")


def timing_decorator(func: Callable) -> Callable:
    """计时装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with PerformanceMonitor(func.__name__):
            return func(*args, **kwargs)
    return wrapper


# 常用的状态名称映射
STATE_NAMES = {
    0: "未开始",
    1: "收竿/提竿", 
    2: "拉扯鱼线",
    3: "收线",
    4: "跳过"
}

# 常用的配置默认值
DEFAULT_CONFIG = {
    "fishing": {
        "reel_key": "right_click",
        "continuous": {
            "max_times": 10
        },
        "thresholds": {
            "area_decrease": 4
        }
    }
}
