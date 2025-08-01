import os
import sys
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """主函数，启动钓鱼机器人UI"""
    try:
        # 导入FishingBot类（推迟导入，避免循环依赖）
        from bot import FishingBot
        bot = FishingBot()

        # 启动UI界面
        try:
            from PyQt5.QtWidgets import QApplication, QMessageBox
            from PyQt5.QtCore import Qt
            from Ui_Manage.FishingUI import FishingUI

            logger.info("正在启动...")

            # 设置DPI缩放支持（必须在QApplication创建之前）
            if hasattr(QApplication, 'setAttribute'):
                QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
                QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

            # 确保QApplication只创建一次
            app = QApplication.instance()
            if not app:
                app = QApplication(sys.argv)

            # 获取窗口配置
            from config_manager import config_manager
            window_config = config_manager.get_window_config()

            # 创建新的钓鱼UI，并传入钓鱼机器人实例
            fishing_ui = FishingUI(bot, window_config)

            # 连接信号到机器人的方法 - 正常钓鱼模式
            fishing_ui.start_signal.connect(lambda: bot.start(
                fishing_ui.target_count_spin.value(),
                fishing_ui.continuous_fishing_check.isChecked()
            ))
            fishing_ui.stop_signal.connect(bot.stop)

            # 显示UI
            fishing_ui.show()

            # 如果未找到游戏窗口，弹出提示对话框
            if not bot.game_window_found:
                QMessageBox.warning(fishing_ui, "警告", "未找到游戏窗口，请先打开游戏！")

            # 运行事件循环前确保按钮状态正确
            fishing_ui.update_status()

            # 运行事件循环
            sys.exit(app.exec_())
        except ImportError as e:
            logger.error(f"启动UI失败: {e}")
            logger.error("请确保已安装PyQt5依赖")
        except Exception as e:
            logger.error(f"UI运行出错: {e}")

    except KeyboardInterrupt:
        logger.info("用户中断，退出程序")
    except Exception as e:
        logger.critical(f"程序出现严重错误: {e}")
    finally:
        logger.info("程序已退出")

if __name__ == "__main__":
    main() 