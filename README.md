# nikki_autofishing
由minimap拆分出的半自动钓鱼工具

## 项目说明
这是一个用于游戏"无限暖暖"的自动钓鱼辅助工具，可以帮助玩家自动完成钓鱼过程。

## 安装与使用

### 依赖安装
1. 确保已安装Python 3.8或更高版本
2. 使用pip安装依赖：
```bash
pip install -r requirements.txt
```

### 配置说明
1. 在`config.json`文件中配置游戏窗口和钓鱼参数
2. 窗口配置部分用于定位游戏窗口
3. 钓鱼配置部分用于调整钓鱼检测区域和判定阈值

### 运行方式
1. 解压压缩包并运行可执行文件（管理员模式）
```bash
fishing_app.exe
```

2. 或者通过Python运行
```bash
python FishingAdapter.py
```

## 代码结构
- `auto_fishing.py`: 自动钓鱼核心逻辑
- `FishingAdapter.py`: 钓鱼适配器，连接UI和钓鱼逻辑
- `FishingOverlay.py`: 钓鱼覆盖层UI
- `config_manager.py`: 配置管理模块
- `controller/`: 鼠标和键盘控制模块
- `capture/`: 屏幕捕获和图像处理模块
- `Ui_Manage/`: UI管理模块