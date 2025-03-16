import json
import os
import sys
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    """从JSON文件加载配置
    
    Returns:
        dict: 配置字典
        
    Raises:
        SystemExit: 如果配置文件不存在或加载失败
    """
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
            logger.error(f"配置文件不存在: {config_path}")
            sys.exit(1)
            
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        logger.info(f"成功加载配置文件: {config_path}")
        return config
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        sys.exit(1)

# 全局配置对象
CONFIG = load_config() 