import os
import time
import logging
import win32gui
import win32ui
import win32con
import ctypes
from PIL import Image
from collections import deque

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ScreenCaptureExtractor:
    """
    屏幕截图提取器
    用于指定窗口和区域的快速截图，自动计算大区域和小区域
    """
    # PrintWindow API 常量
    PW_CLIENTONLY = 1
    PW_RENDERFULLCONTENT = 2  # 仅在Win8.1及以上版本有效
    
    def __init__(self, hwnd=None, positions=None, region_size=80):
        """
        初始化截图提取器
        
        参数:
            hwnd: 窗口句柄，如果为None则需要在后续设置
            positions: 要截图的位置列表，每项为(x, y)坐标元组
            region_size: 小区域的大小（像素，宽高相等）
        """
        self.hwnd = hwnd
        self.region_size = region_size
        self.positions = positions or []
        self.capture_region = None  # 大区域坐标 (x, y, width, height)
        
        # 初始化窗口尺寸属性
        self.window_width = 1920  # 默认值
        self.window_height = 1080  # 默认值
        
        # 如果提供了窗口句柄，立即更新窗口尺寸
        if self.hwnd:
            self.update_window_size()
        
        # 性能测量
        self.frame_times = deque(maxlen=100)
        self.last_fps = 0
        
        # 如果提供了位置，计算大区域
        if self.positions:
            self.calculate_capture_region()
    
    def set_hwnd(self, hwnd):
        """设置窗口句柄"""
        self.hwnd = hwnd
    
    def set_positions(self, positions):
        """
        设置截图位置
        
        参数:
            positions: 要截图的位置列表，每项为(x, y)坐标元组
        """
        self.positions = positions
        self.calculate_capture_region()
    
    def set_region_size(self, size):
        """设置小区域大小"""
        self.region_size = size
        if self.positions:
            self.calculate_capture_region()
    
    def calculate_capture_region(self):
        """计算包含所有点的最小区域"""
        if not self.positions:
            logger.warning("没有提供任何位置坐标，无法计算大区域")
            return False
            
        # 获取所有X和Y坐标
        x_coords = [pos[0] for pos in self.positions]
        y_coords = [pos[1] for pos in self.positions]
        
        # 计算包含所有点的最小矩形
        min_x = min(x_coords)
        min_y = min(y_coords)
        max_x = max(x_coords)
        max_y = max(y_coords)
        
        # 计算大区域的宽高（加上区域大小的偏移）
        region_width = max_x - min_x + self.region_size
        region_height = max_y - min_y + self.region_size
        
        # 保存大区域坐标
        self.capture_region = (min_x, min_y, region_width, region_height)
        
        logger.info(f"计算得到的大区域: x={min_x}, y={min_y}, w={region_width}, h={region_height}")
        return True
    
    @staticmethod
    def force_window_update(hwnd):
        """强制窗口更新其内容"""
        try:
            # 尝试使用RedrawWindow API强制窗口重绘
            win32gui.RedrawWindow(
                hwnd, None, None, 
                win32con.RDW_UPDATENOW | 
                win32con.RDW_INTERNALPAINT | 
                win32con.RDW_INVALIDATE
            )
        except Exception as e:
            logger.debug(f"强制重绘窗口失败: {e}")
    
    def capture_window(self, method="auto"):
        """
        截取整个窗口
        
        参数:
            method: 截图方法，可以是"auto"、"printwindow"或"bitblt"
            
        返回:
            成功返回PIL Image对象，失败返回None
        """
        if not self.hwnd:
            logger.error("未设置窗口句柄")
            return None
            
        # 设置DPI感知 - 避免高DPI屏幕下的缩放问题
        old_context = None
        try:
            # 尝试获取DPI感知上下文常量
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
            SetThreadDpiAwarenessContext = getattr(ctypes.windll.user32, 'SetThreadDpiAwarenessContext', None)
            if SetThreadDpiAwarenessContext:
                old_context = SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        except Exception as e:
            logger.debug(f"设置DPI感知失败: {e}")
        
        try:
            # 强制窗口更新
            self.force_window_update(self.hwnd)
            
            # 获取窗口尺寸
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
            width, height = right - left, bottom - top
            
            if width <= 0 or height <= 0:
                logger.warning("窗口尺寸无效")
                return None
                
            # 创建设备上下文
            hwnd_dc = win32gui.GetWindowDC(self.hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            
            # 创建位图对象
            save_bitmap = win32ui.CreateBitmap()
            save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(save_bitmap)
            
            # 使用PrintWindow进行截图
            success = False
            
            # 先尝试使用完整内容渲染选项的PrintWindow (Win 8.1+)
            if method == "auto" or method == "printwindow":
                try:
                    result = ctypes.windll.user32.PrintWindow(
                        self.hwnd, save_dc.GetSafeHdc(), self.PW_RENDERFULLCONTENT
                    )
                    if result:
                        success = True
                except:
                    pass
            
            # 如果失败且为自动模式，尝试标准PrintWindow
            if not success and (method == "auto" or method == "printwindow"):
                try:
                    result = ctypes.windll.user32.PrintWindow(
                        self.hwnd, save_dc.GetSafeHdc(), 0
                    )
                    if result:
                        success = True
                except:
                    pass
            
            # 如果PrintWindow都失败，尝试BitBlt
            if not success and (method == "auto" or method == "bitblt"):
                try:
                    save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)
                    success = True
                except:
                    pass
            
            # 如果所有方法都失败
            if not success:
                logger.warning("所有截图方法都失败")
                win32gui.DeleteObject(save_bitmap.GetHandle())
                save_dc.DeleteDC()
                mfc_dc.DeleteDC()
                win32gui.ReleaseDC(self.hwnd, hwnd_dc)
                return None
            
            # 获取位图数据
            bmpinfo = save_bitmap.GetInfo()
            bmpstr = save_bitmap.GetBitmapBits(True)
            
            # 转换为PIL图像
            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1)
            
            # 清理资源
            win32gui.DeleteObject(save_bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hwnd_dc)
            
            # 更新FPS计算
            self.frame_times.append(time.time())
            if len(self.frame_times) >= 2:
                elapsed = self.frame_times[-1] - self.frame_times[0]
                if elapsed > 0:
                    self.last_fps = (len(self.frame_times) - 1) / elapsed
            
            return img
        except Exception as e:
            logger.error(f"窗口截图失败: {e}")
            return None
        finally:
            # 恢复原始DPI感知状态
            if old_context and 'SetThreadDpiAwarenessContext' in locals():
                try:
                    SetThreadDpiAwarenessContext(old_context)
                except:
                    pass
    
    def capture_full_region(self):
        """
        截取大区域
        
        返回:
            成功返回PIL Image对象，失败返回None
        """
        if not self.hwnd:
            logger.error("未设置窗口句柄")
            return None
            
        if not self.capture_region:
            logger.error("未计算大区域")
            return None
        
        # 获取整个窗口的截图
        window_screenshot = self.capture_window()
        if not window_screenshot:
            return None
        
        try:
            # 截取大区域
            x, y, w, h = self.capture_region
            return window_screenshot.crop((x, y, x + w, y + h))
        except Exception as e:
            logger.error(f"截取大区域失败: {e}")
            return None
    
    def capture_sub_regions(self):
        """
        截取所有小区域
        
        返回:
            成功返回小区域图像和位置信息的列表，每项为 (image, position)，失败返回空列表
        """
        if not self.positions:
            logger.error("未设置位置坐标")
            return []
            
        if not self.capture_region:
            logger.error("未计算大区域")
            return []
        
        # 获取大区域截图
        full_region = self.capture_full_region()
        if not full_region:
            return []
        
        capture_x, capture_y, capture_w, capture_h = self.capture_region
        
        # 截取小区域
        results = []
        for i, (x, y) in enumerate(self.positions):
            try:
                # 计算在大区域内的相对坐标
                relative_x = x - capture_x
                relative_y = y - capture_y
                
                # 检查相对坐标是否在大区域内
                if (relative_x < 0 or relative_y < 0 or 
                    relative_x + self.region_size > capture_w or 
                    relative_y + self.region_size > capture_h):
                    logger.warning(f"位置 #{i+1} ({x},{y}) 的裁剪区域超出大区域范围")
                    continue
                
                # 从大区域截图中裁剪子区域
                region_img = full_region.crop((
                    relative_x, 
                    relative_y, 
                    relative_x + self.region_size, 
                    relative_y + self.region_size
                ))
                results.append((region_img, (x, y)))
            except Exception as e:
                logger.error(f"裁剪子区域 #{i+1} 失败: {e}")
        
        return results
    
    def capture_one_shot(self):
        """
        一次性截取大区域和所有小区域
        
        返回:
            字典，包含大区域和小区域的截图
            {
                'full_region': Image对象,
                'sub_regions': [(Image对象, 位置元组), ...]
            }
        """
        # 获取大区域截图
        full_region = self.capture_full_region()
        if not full_region:
            return {'full_region': None, 'sub_regions': []}
        
        capture_x, capture_y, capture_w, capture_h = self.capture_region
        
        # 截取小区域
        sub_regions = []
        for i, (x, y) in enumerate(self.positions):
            try:
                # 计算在大区域内的相对坐标
                relative_x = x - capture_x
                relative_y = y - capture_y
                
                # 检查相对坐标是否在大区域内
                if (relative_x < 0 or relative_y < 0 or 
                    relative_x + self.region_size > capture_w or 
                    relative_y + self.region_size > capture_h):
                    logger.warning(f"位置 #{i+1} ({x},{y}) 的裁剪区域超出大区域范围")
                    continue
                
                # 从大区域截图中裁剪子区域
                region_img = full_region.crop((
                    relative_x, 
                    relative_y, 
                    relative_x + self.region_size, 
                    relative_y + self.region_size
                ))
                sub_regions.append((region_img, (x, y)))
            except Exception as e:
                logger.error(f"裁剪子区域 #{i+1} 失败: {e}")
        
        return {
            'full_region': full_region,
            'sub_regions': sub_regions
        }
    
    def get_fps(self):
        """获取当前FPS"""
        return self.last_fps
    
    def update_window_size(self):
        """更新窗口尺寸
        
        获取窗口的当前尺寸，用于调整捕获区域
        """
        if not self.hwnd:
            logger.warning("未设置窗口句柄，无法更新窗口尺寸")
            return False
            
        try:
            # 检查窗口句柄是否有效
            if not win32gui.IsWindow(self.hwnd):
                logger.warning("窗口句柄无效，使用默认尺寸")
                self.window_width = 1920  # 设置默认值
                self.window_height = 1080
                return False

            # 获取窗口尺寸
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
            self.window_width = right - left
            self.window_height = bottom - top

            logger.info(f"更新窗口尺寸: {self.window_width}x{self.window_height}")
            return True
        except Exception as e:
            logger.error(f"获取窗口尺寸失败: {e}")
            self.window_width = 1920  # 设置默认值
            self.window_height = 1080
            return False
    
    def adjust_region_to_window_bounds(self):
        """调整捕获区域到窗口边界内
        
        确保捕获区域不超出窗口边界
        """
        if not hasattr(self, 'window_width') or not hasattr(self, 'window_height'):
            if not self.update_window_size():
                logger.warning("无法获取窗口尺寸，无法调整区域")
                return False
                
        if not self.capture_region:
            logger.warning("未设置捕获区域，无法进行调整")
            return False
            
        x, y, width, height = self.capture_region
        
        # 确保区域不超出窗口边界
        if x < 0:
            logger.warning(f"捕获区域X坐标 ({x}) 小于0，已调整为0")
            x = 0
        if y < 0:
            logger.warning(f"捕获区域Y坐标 ({y}) 小于0，已调整为0")
            y = 0
        
        if x + width > self.window_width:
            logger.warning(f"捕获区域右边界 ({x + width}) 超出窗口宽度 ({self.window_width})，已调整")
            width = self.window_width - x
        
        if y + height > self.window_height:
            logger.warning(f"捕获区域下边界 ({y + height}) 超出窗口高度 ({self.window_height})，已调整")
            height = self.window_height - y
        
        # 更新捕获区域
        self.capture_region = (x, y, width, height)
        logger.info(f"调整后的捕获区域: x={x}, y={y}, w={width}, h={height}")
        return True
    
    @staticmethod
    def list_windows():
        """
        列出所有可见窗口
        
        返回:
            窗口列表，每项为 (窗口标题, 句柄)
        """
        window_list = []
        
        def enum_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title.strip():  # 忽略空标题窗口
                    results.append((title, hwnd))
            return True
        
        win32gui.EnumWindows(enum_callback, window_list)
        
        # 按标题排序
        window_list.sort(key=lambda x: x[0].lower())
        
        return window_list 