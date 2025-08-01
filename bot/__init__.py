import os
import logging

logger = logging.getLogger(__name__)

# 确保分辨率文件夹存在
def ensure_resolution_folders():
    try:
        from config_manager import config_manager
        
        # 获取模板目录路径
        template_dir = config_manager.get("paths.templates", "./img/templates")
        
        # 创建分辨率文件夹
        resolutions = ["720p", "1080p", "1440p", "4k"]
        for res in resolutions:
            res_dir = os.path.join(template_dir, res)
            if not os.path.exists(res_dir):
                os.makedirs(res_dir)
                logger.info(f"创建分辨率模板文件夹: {res_dir}")
        
        # 检查是否有模板文件，如果没有，则复制默认模板到各个分辨率文件夹
        template_files = [f for f in os.listdir(template_dir) if f.endswith(".png")]
        if template_files:
            logger.info(f"找到 {len(template_files)} 个模板文件")
        else:
            logger.warning("未找到模板文件，请确保模板文件存在")
    except Exception as e:
        logger.error(f"创建分辨率文件夹时出错: {e}")

# 在导入时执行
ensure_resolution_folders()

from .fishing_bot import FishingBot

__all__ = ['FishingBot'] 