import ctypes
import os
import sys
import time
from ctypes import wintypes
import win32api
import win32gui

from Ui_Manage.WindowManager import WinControl
from config_manager import CONFIG


def load_config():
    """从JSON文件加载配置"""
    try:
        # 获取配置文件路径
        try:
            # PyInstaller创建临时文件夹,将路径存储在_MEIPASS中
            base_path = sys._MEIPASS
            config_path = os.path.join(base_path, 'config.json')
        except Exception:
            # 如果不是打包的情况,就使用当前文件的目录
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_path, 'config.json')

        if not os.path.exists(config_path):
            print(f"配置文件不存在: {config_path}")
            sys.exit(1)

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        print(f"成功加载配置文件: {config_path}")
        return config
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        sys.exit(1)


CONFIG = load_config()


if ctypes.sizeof(ctypes.c_void_p) == 4:
    ULONG_PTR = ctypes.c_ulong  # 32-bit
else:
    ULONG_PTR = ctypes.c_ulonglong  # 64-bit
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx', wintypes.LONG),
        ('dy', wintypes.LONG),
        ('mouseData', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ULONG_PTR),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ('type', wintypes.DWORD),
        ('mi', MOUSEINPUT),
    ]


class MouseController:
    """鼠标控制类"""
    INPUT_MOUSE = 0
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_WHEEL = 0x0800
    WHEEL_DELTA = 120
    def __init__(self, window_manager: WinControl, config: dict = CONFIG):
        """
        初始化鼠标控制器
        :param window_manager: 窗口管理器实例
        :param config: 窗口配置信息
        """
        self.window_manager = window_manager
        self.config = config
        self.hwnd = None
        self._init_sendinput()
        self._set_dpi_awareness()

    def _set_dpi_awareness(self):
        """设置DPI感知以获取正确的物理分辨率"""
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            ctypes.windll.user32.SetProcessDPIAware()


    def _init_sendinput(self):
        """初始化SendInput函数"""
        self.SendInput = ctypes.windll.user32.SendInput
        self.SendInput.argtypes = [
            ctypes.c_uint,
            ctypes.POINTER(INPUT),
            ctypes.c_int
        ]
        self.SendInput.restype = ctypes.c_uint

    def _get_hwnd(self) -> int:
        """获取并缓存窗口句柄"""
        if not self.hwnd:
            self.hwnd = self.window_manager.find_target_window(self.config["window"])
            if not self.hwnd:
                raise ValueError("目标窗口未找到")
        return self.hwnd

    def _activate_window(self):
        """激活目标窗口"""
        hwnd = self._get_hwnd()
        self.window_manager.activate_window(hwnd)

    def _to_absolute_coordinates(self, x: int, y: int) -> tuple:
        """
        将窗口坐标转换为绝对坐标(0-65535)
        :return: (abs_x, abs_y)
        """
        hwnd = self._get_hwnd()
        client_rect = win32gui.GetClientRect(hwnd)
        left, top = win32gui.ClientToScreen(hwnd, (client_rect[0], client_rect[1]))

        # 获取物理分辨率
        screen_width = win32api.GetSystemMetrics(0)
        screen_height = win32api.GetSystemMetrics(1)

        abs_x = int((left + x) / screen_width * 65535)
        abs_y = int((top + y) / screen_height * 65535)
        return abs_x, abs_y

    def move_absolute(self, x: int, y: int):
        """
        绝对坐标移动
        :param x: 窗口客户区X坐标
        :param y: 窗口客户区Y坐标
        """
        self._activate_window()
        abs_x, abs_y = self._to_absolute_coordinates(x, y)

        # 构造输入事件
        mi = MOUSEINPUT(abs_x, abs_y, 0, self.MOUSEEVENTF_ABSOLUTE | self.MOUSEEVENTF_MOVE, 0, 0)
        input_struct = INPUT(self.INPUT_MOUSE, mi)

        self.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))

    def move_relative(self, dx: int, dy: int):
        """
        相对坐标移动（适用于视角控制）
        :param dx: X轴偏移量
        :param dy: Y轴偏移量
        """
        self._activate_window()

        # 构造输入事件
        mi = MOUSEINPUT(dx, dy, 0, self.MOUSEEVENTF_MOVE, 0, 0)
        input_struct = INPUT(self.INPUT_MOUSE, mi)

        self.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))

    def press_left(self):
        """按下左键"""
        self._activate_window()
        mi = MOUSEINPUT(0, 0, 0, self.MOUSEEVENTF_LEFTDOWN, 0, 0)
        input_struct = INPUT(self.INPUT_MOUSE, mi)
        self.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))

    def release_left(self):
        """释放左键"""
        self._activate_window()
        mi = MOUSEINPUT(0, 0, 0, self.MOUSEEVENTF_LEFTUP, 0, 0)
        input_struct = INPUT(self.INPUT_MOUSE, mi)
        self.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))

    def click_left(self, duration: float = 0.1):
        """
        单击左键（含按住时间）
        :param duration: 按键保持时间（秒）
        """
        self.press_left()
        time.sleep(duration)
        self.release_left()

    def press_right(self):
        """按下右键"""
        self._activate_window()
        mi = MOUSEINPUT(0, 0, 0, self.MOUSEEVENTF_RIGHTDOWN, 0, 0)
        input_struct = INPUT(self.INPUT_MOUSE, mi)
        self.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))

    def release_right(self):
        """释放右键"""
        self._activate_window()
        mi = MOUSEINPUT(0, 0, 0, self.MOUSEEVENTF_RIGHTUP, 0, 0)
        input_struct = INPUT(self.INPUT_MOUSE, mi)
        self.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))

    def click_right(self, duration: float = 0.1):
        """
        单击右键（含按住时间）
        :param duration: 按键保持时间（秒）
        """
        self.press_right()
        time.sleep(duration)
        self.release_right()

    def wheel(self, delta: int):
        """
        滚动鼠标滚轮
        :param delta: 滚动量（正数向上，负数向下）
        """
        self._activate_window()
        mi = MOUSEINPUT(0, 0, delta * self.WHEEL_DELTA, self.MOUSEEVENTF_WHEEL, 0, 0)
        input_struct = INPUT(self.INPUT_MOUSE, mi)
        self.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))



# 初始化窗口管理器
window_manager = WinControl()

# 创建鼠标控制器
mouse = MouseController(window_manager)

#time.sleep(3)
#mouse.press_right（）#按下右键
#mouse.release_right()#释放右键
#mouse.click_right(1)，#按住一秒后放开
#mouse.click_left()
#mouse.wheel(1)
# 绝对移动
#mouse.move_absolute(100, 100)  # 移动到窗口客户区(100,100)位置

# 相对移动
#mouse.move_relative(1118, 0)   # 4472 一圈  2236 半圈