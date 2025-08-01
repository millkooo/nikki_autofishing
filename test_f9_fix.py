#!/usr/bin/env python3
"""
测试F9键停止功能的修复
"""
import logging
import time
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_f9_functionality():
    """测试F9键功能"""
    try:
        logger.info("开始测试F9键功能...")
        
        # 导入FishingBot
        from bot import FishingBot
        
        # 创建机器人实例
        bot = FishingBot()
        
        logger.info("机器人已创建，测试F9键监听...")
        logger.info("请按F9键测试停止功能（10秒后自动结束测试）")
        
        # 模拟运行状态
        bot.running = True
        
        # 等待10秒，期间可以按F9测试
        start_time = time.time()
        while time.time() - start_time < 10:
            if bot.input_handler.stop_flag:
                logger.info("✓ F9键功能正常！检测到停止信号")
                break
            time.sleep(0.1)
        else:
            logger.info("测试结束，未检测到F9键按下")
        
        # 清理
        bot.input_handler.close()
        logger.info("测试完成")
        
    except Exception as e:
        logger.error(f"测试出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_f9_functionality()
