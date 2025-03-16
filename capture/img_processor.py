from numpy import ndarray

from capture import *

class ImageProcessor:
    """图像处理类，负责图像采集和处理"""

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self.window_rect = win32gui.GetWindowRect(hwnd)
        windll.user32.SetProcessDPIAware()
        self.window_width = self.window_rect[2] - self.window_rect[0]
        self.window_height = self.window_rect[3] - self.window_rect[1]

    def capture_region(self, region_config: dict) -> np.ndarray:
        """单区域直接截图模式
        :param region_config: 截图区域配置{
            "x_offset": int,  # 相对窗口的X偏移
            "y_offset": int,  # 相对窗口的Y偏移
            "width": int,     # 区域宽度
            "height": int     # 区域高度
        }"""
        region = {
            "left": self.window_rect[0] + region_config["x_offset"],
            "top": self.window_rect[1] + region_config["y_offset"],
            "width": region_config["width"],
            "height": region_config["height"]
        }
        return self._grab_region(region)

    @staticmethod
    def _grab_region(region: dict) -> np.ndarray:
        """通用截图方法"""
        with mss.mss() as sct:
            screenshot = sct.grab(region)
            pil_image = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    def get_window_rect(self):
        """获取窗口矩形区域"""
        # 更新窗口位置
        self.window_rect = win32gui.GetWindowRect(self.hwnd)
        self.window_width = self.window_rect[2] - self.window_rect[0]
        self.window_height = self.window_rect[3] - self.window_rect[1]
        return self.window_rect

"""
# 单区域截图
single_area = processor.capture_region({
    "x_offset": 100,
    "y_offset": 200,
    "width": 300,
    "height": 400
})

# 多区域截图
multi_areas = processor.capture_multiple_regions([
    {"x": 0, "y": 0, "w": 100, "h": 100},
    {"x": 200, "y": 300, "w": 50, "h": 80}
])

"""