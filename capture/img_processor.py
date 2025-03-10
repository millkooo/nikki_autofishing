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

    def capture_multiple_regions(self, regions: list) -> list:
        """
        全窗口截图+多区域裁剪模式
        :param regions: 区域定义列表，每个元素为{
            "x": int,   # 相对窗口的X偏移
            "y": int,   # 相对窗口的Y偏移
            "w": int,   # 区域宽度
            "h": int    # 区域高度
        }"""
        full_region = {
            "left": self.window_rect[0],
            "top": self.window_rect[1],
            "width": self.window_width,
            "height": self.window_height
        }
        full_image = self._grab_region(full_region)

        return [self._crop_image(full_image, region) for region in regions]

    def _crop_image(self, full_image: np.ndarray, region: dict) -> np.ndarray:
        """图像裁剪辅助方法"""
        x = max(0, min(region["x"], self.window_width))
        y = max(0, min(region["y"], self.window_height))
        w = max(0, min(region["w"], self.window_width - x))
        h = max(0, min(region["h"], self.window_height - y))
        return full_image[y:y+h, x:x+w]

    @staticmethod
    def _grab_region(region: dict) -> np.ndarray:
        """通用截图方法"""
        with mss.mss() as sct:
            screenshot = sct.grab(region)
            pil_image = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    # 以下静态方法保持原有功能不变
    @staticmethod
    def circle_crop(image: np.ndarray, diameter: int) -> np.ndarray:
        """将图像裁剪为圆形"""
        height, width = image.shape[:2]
        mask = np.zeros((height, width), dtype=np.uint8)
        radius = diameter // 2
        cv2.circle(mask, (width//2, height//2), radius, 255, -1)
        return cv2.bitwise_and(image, image, mask=mask)

    @staticmethod
    def compute_image_hash(image: np.ndarray) -> str:
        """计算图像的快速哈希值（aHash算法）"""
        resized = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (8, 8))
        avg = resized.mean()
        return ''.join(['1' if pixel > avg else '0' for row in resized for pixel in row])

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