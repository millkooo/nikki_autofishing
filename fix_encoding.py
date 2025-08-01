import os
import sys
import logging
import shutil
import re

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_template_encoding():
    """修复模板文件名编码问题"""
    try:
        # 模板目录路径
        template_dirs = [
            os.path.join("img", "templates", "1080p"),
            os.path.join("img", "templates", "720p"),
            os.path.join("img", "templates", "1440p"),
            os.path.join("img", "templates", "4k")
        ]
        
        # 文件名映射字典
        filename_mapping = {}
        
        for template_dir in template_dirs:
            if not os.path.exists(template_dir):
                logger.warning(f"目录不存在: {template_dir}")
                continue
                
            logger.info(f"处理目录: {template_dir}")
            
            # 获取目录中的所有文件
            files = os.listdir(template_dir)
            
            for file_name in files:
                if not file_name.endswith(".png"):
                    continue
                    
                # 检查文件名是否包含中文
                try:
                    # 尝试将文件名编码为ASCII，如果成功则不是中文
                    file_name.encode('ascii')
                    continue  # 不是中文文件名，跳过
                except UnicodeEncodeError:
                    # 包含中文，需要修复
                    old_path = os.path.join(template_dir, file_name)
                    
                    # 创建一个英文文件名
                    new_file_name = ""
                    if "跳过" in file_name:
                        new_file_name = "skip.png"
                    elif "提竿" in file_name:
                        new_file_name = "cast.png"
                    elif "收线" in file_name:
                        new_file_name = "reel.png"
                    elif "收竿" in file_name:
                        new_file_name = "collect.png"
                    elif "拉扯鱼线" in file_name:
                        new_file_name = "pull.png"
                    else:
                        # 如果无法识别，使用原文件名的拼音首字母
                        new_file_name = f"template_{len(file_name)}.png"
                    
                    new_path = os.path.join(template_dir, new_file_name)
                    
                    # 记录映射关系
                    filename_mapping[file_name] = new_file_name
                    
                    # 复制文件而不是重命名，保留原始文件
                    logger.info(f"复制文件: {old_path} -> {new_path}")
                    shutil.copy2(old_path, new_path)
                    
        logger.info("文件名编码修复完成")
        return filename_mapping
    except Exception as e:
        logger.error(f"修复文件名编码时出错: {e}")
        return {}

def update_fishing_bot_file(filename_mapping):
    """更新fishing_bot.py文件中的模板路径"""
    try:
        # 读取fishing_bot.py文件
        bot_file_path = os.path.join("bot", "fishing_bot.py")
        if not os.path.exists(bot_file_path):
            logger.error(f"找不到文件: {bot_file_path}")
            return False
            
        logger.info(f"正在更新文件: {bot_file_path}")
        
        # 读取文件内容
        with open(bot_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 备份原文件
        backup_path = f"{bot_file_path}.bak"
        shutil.copy2(bot_file_path, backup_path)
        logger.info(f"已备份原文件: {backup_path}")
        
        # 替换模板路径
        new_content = content
        for old_name, new_name in filename_mapping.items():
            # 移除.png后缀进行替换
            old_name_without_ext = old_name.replace('.png', '')
            new_name_without_ext = new_name.replace('.png', '')
            
            # 使用正则表达式替换模板路径
            pattern = f'{{"name": "{old_name_without_ext}", "path": os\\.path\\.join\\(template_dir, "{old_name_without_ext}\\.png"\\)'
            replacement = f'{{"name": "{old_name_without_ext}", "path": os.path.join(template_dir, "{new_name_without_ext}.png")'
            new_content = re.sub(pattern, replacement, new_content)
            
        # 写入新文件
        with open(bot_file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logger.info(f"已更新文件: {bot_file_path}")
        return True
    except Exception as e:
        logger.error(f"更新fishing_bot.py文件时出错: {e}")
        return False

if __name__ == "__main__":
    logger.info("开始修复模板文件名编码问题...")
    filename_mapping = fix_template_encoding()
    
    if filename_mapping:
        if update_fishing_bot_file(filename_mapping):
            logger.info("所有修复完成，请重新启动钓鱼机器人")
        else:
            logger.error("更新代码文件失败，请手动修改模板路径")
            logger.info("文件名映射关系:")
            for old_name, new_name in filename_mapping.items():
                logger.info(f"{old_name} -> {new_name}")
    else:
        logger.error("修复失败或没有需要修复的文件") 