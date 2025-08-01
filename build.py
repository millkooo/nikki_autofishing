import os
import subprocess
import sys

# 确保当前目录是项目根目录
root_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(root_dir)

# 定义输出目录和应用名称
output_name = "auto_fishing"
main_script = "fishing_bot.py"

# 检查PyInstaller是否已安装
try:
    import PyInstaller
except ImportError:
    print("正在安装PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    print("PyInstaller安装完成")

# 构建PyInstaller命令
cmd = [
    "pyinstaller",
    "--name", output_name,  # 指定输出名称为auto_fishing
    "--icon=img/fishing.ico" if os.path.exists("img/fishing.ico") else "",  # 如果存在图标则使用
    "--add-data", f"img{os.pathsep}img",              # 添加img目录
    "--add-data", f"match{os.pathsep}match",          # 添加match目录
    "--add-data", f"config.json{os.pathsep}.",        # 添加配置文件
    "--hidden-import", "PIL._tkinter_finder",         # 隐式导入
    main_script                                       # 主脚本
]

# 移除空选项
cmd = [item for item in cmd if item]

print(f"开始打包 {main_script} 为 {output_name}.exe")
print(f"打包命令: {' '.join(cmd)}")

# 执行打包命令
subprocess.run(cmd)

print(f"打包完成，输出文件位于 dist/{output_name}.exe") 