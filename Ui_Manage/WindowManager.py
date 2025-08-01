import ctypes
import logging
import psutil
import pythoncom
import win32con
import win32gui
import win32print
import win32process
import time

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WinControl:
    """窗口管理类，负责窗口查找和操作"""
    @staticmethod
    def find_target_window(config: dict) -> int | None:
        """根据配置查找目标窗口句柄
        
        Args:
            config: 包含window_class和process_exe的配置字典
            
        Returns:
            int | None: 找到的窗口句柄，如果未找到则返回None
            
        Raises:
            ValueError: 配置参数无效时抛出
        """
        if not isinstance(config, dict) or "window_class" not in config or "process_exe" not in config:
            raise ValueError("无效的窗口配置")

        def callback(hwnd: int, hwnd_list: list) -> bool:
            if not win32gui.IsWindowVisible(hwnd):
                return True
                
            try:
                current_class = win32gui.GetClassName(hwnd).strip()
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                
                if (current_class == config["window_class"] and
                        WinControl._check_process_exe(pid, config["process_exe"])):
                    hwnd_list.append(hwnd)
            except Exception as e:
                logger.error(f"查找窗口时发生错误: {str(e)}")
            return True

        hwnd_list = []
        try:
            win32gui.EnumWindows(callback, hwnd_list)
            return hwnd_list[0] if hwnd_list else None
        except Exception as e:
            logger.error(f"枚举窗口失败: {str(e)}")
            return None

    @staticmethod
    def _check_process_exe(pid: int, target_exe: str) -> bool:
        """验证进程可执行文件
        
        Args:
            pid: 进程ID
            target_exe: 目标可执行文件名
            
        Returns:
            bool: 如果进程可执行文件匹配则返回True
        """
        if not target_exe:
            return False
            
        try:
            process = psutil.Process(pid)
            exe_name = process.exe().split('\\')[-1].lower()
            return exe_name == target_exe.lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.debug(f"检查进程可执行文件失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"检查进程可执行文件时发生未知错误: {str(e)}")
            return False

    @staticmethod
    def activate_window(hwnd: int) -> bool:
        """激活并置顶窗口
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            bool: 操作是否成功
        """
        if not hwnd:
            logger.error("无效的窗口句柄")
            return False
            
        try:
            pythoncom.CoInitialize()
            # 检查窗口是否最小化
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            # 检查窗口是否可见
            if not win32gui.IsWindowVisible(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            # 激活窗口
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as e:
            logger.error(f"窗口激活失败: {str(e)}")
            return False
        finally:
            pythoncom.CoUninitialize()

    @staticmethod
    def close_window(hwnd: int) -> None:
        """关闭指定窗口句柄对应的窗口"""
        try:
            import win32gui
            import win32con
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            print("游戏窗口已关闭")
        except Exception as e:
            print(f"关闭窗口失败: {e}")

    @staticmethod
    def is_window_minimized(hwnd: int) -> bool:
        """检测窗口是否处于最小化状态"""
        try:
            import win32gui
            import win32con
            placement = win32gui.GetWindowPlacement(hwnd)
            return placement[1] == win32con.SW_SHOWMINIMIZED
        except:
            return False

    @staticmethod
    def get_scaling_factor(hwnd: int) -> float:
        """获取dpi"""
        try:
            dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
            return round(dpi / 96.0, 2)
        except AttributeError:
            hdc = win32gui.GetDC(hwnd)
            dpi = win32print.GetDeviceCaps(hdc, win32con.LOGPIXELSX)
            win32gui.ReleaseDC(hwnd, hdc)
            return round(dpi / 96.0, 2)

    @staticmethod
    def get_window_rect(hwnd: int) -> tuple:
        """获取窗口的位置和大小

        Args:
            hwnd: 窗口句柄

        Returns:
            tuple: (x, y, width, height) 窗口的位置和大小，无效句柄返回None
        """
        # 首先检查窗口句柄是否有效
        if not hwnd or not WinControl.is_window_valid(hwnd):
            logger.warning("无效的窗口句柄，使用默认位置")
            return None

        try:
            # 获取窗口矩形
            rect = win32gui.GetWindowRect(hwnd)
            x = rect[0]
            y = rect[1]
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            return (x, y, width, height)
        except Exception as e:
            logger.error(f"获取窗口位置和大小失败: {str(e)}")
            return None

    @staticmethod
    def get_window_title(hwnd: int) -> str | None:
        """获取窗口标题
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            str | None: 窗口标题，获取失败返回None
        """
        try:
            return win32gui.GetWindowText(hwnd)
        except Exception as e:
            logger.error(f"获取窗口标题失败: {str(e)}")
            return None

    @staticmethod
    def is_window_valid(hwnd: int) -> bool:
        """检查窗口是否有效
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            bool: 窗口是否有效
        """
        try:
            return bool(win32gui.IsWindow(hwnd))
        except Exception:
            return False

    @staticmethod
    def get_window_process_info(hwnd: int) -> dict | None:
        """获取窗口进程信息
        
        Args:
            hwnd: 窗口句柄
            
        Returns:
            dict | None: 包含进程信息的字典，获取失败返回None
        """
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            return {
                "pid": pid,
                "name": process.name(),
                "exe": process.exe(),
                "create_time": process.create_time(),
                "status": process.status()
            }
        except Exception as e:
            logger.error(f"获取窗口进程信息失败: {str(e)}")
            return None

    @staticmethod
    def wait_for_window(config: dict, timeout: float = 10.0, check_interval: float = 0.5) -> int | None:
        """等待目标窗口出现
        
        Args:
            config: 窗口配置
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）
            
        Returns:
            int | None: 窗口句柄，超时返回None
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            hwnd = WinControl.find_target_window(config)
            if hwnd:
                return hwnd
            time.sleep(check_interval)
        logger.warning(f"等待窗口超时: {config}")
        return None
