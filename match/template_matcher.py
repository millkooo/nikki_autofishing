import cv2
import numpy as np
import logging
import os

logger = logging.getLogger(__name__)

class TemplateMatcher:
    """模板匹配类，支持带透明度的图像匹配和不同分辨率模板"""

    def __init__(self):
        self.templates = {}
        self.last_match = None
        self.base_resolution = (1920, 1080)  # 基准分辨率
        self.resolution_folders = {
            (1280, 720): "720p",
            (1920, 1080): "1080p",
            (2560, 1440): "1440p",
            (3840, 2160): "4k"
        }

    def load_templates(self, template_configs, window_size=None):
        """加载模板配置，根据窗口尺寸选择合适的模板
        :param template_configs: 模板配置列表，每个元素包含name, path, threshold
        :param window_size: 窗口尺寸元组 (width, height)
        """
        # 清空已加载的模板
        self.templates = {}
        
        # 确定使用哪个分辨率文件夹
        resolution_folder = self._get_resolution_folder(window_size)
        logger.info(f"根据窗口尺寸 {window_size} 选择模板分辨率: {resolution_folder}")
        
        for config in template_configs:
            try:
                # 修改路径以使用对应分辨率的模板
                original_path = config["path"]
                dir_path = os.path.dirname(original_path)
                file_name = os.path.basename(original_path)
                
                # 尝试在分辨率文件夹中查找模板
                resolution_path = os.path.join(dir_path, resolution_folder, file_name)
                
                # 如果分辨率特定的模板不存在，则使用原始路径
                template_path = resolution_path if os.path.exists(resolution_path) else original_path
                
                # 确保路径是正确的编码格式
                template_path = os.path.abspath(template_path)
                
                # 读取图像，保留透明通道
                template_img = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
                if template_img is None:
                    logger.error(f"无法加载模板图像: {template_path}")
                    # 尝试使用不同的编码方式读取
                    try:
                        # 尝试使用utf-8编码路径
                        utf8_path = template_path.encode('utf-8').decode('utf-8')
                        template_img = cv2.imread(utf8_path, cv2.IMREAD_UNCHANGED)
                        if template_img is not None:
                            logger.info(f"使用UTF-8编码成功加载模板: {utf8_path}")
                        else:
                            logger.error(f"使用UTF-8编码仍无法加载模板: {utf8_path}")
                    except Exception as e:
                        logger.error(f"尝试使用UTF-8编码加载模板失败: {str(e)}")
                    continue

                # 存储模板信息
                self.templates[config["name"]] = {
                    "image": template_img,
                    "threshold": config["threshold"],
                    "path": template_path
                }
                logger.info(f"已加载模板: {config['name']} (使用: {template_path})")
            except Exception as e:
                logger.error(f"加载模板 {config['name']} 失败: {str(e)}")

    def _get_resolution_folder(self, window_size):
        """根据窗口尺寸确定使用哪个分辨率文件夹
        :param window_size: 窗口尺寸元组 (width, height)
        :return: 分辨率文件夹名称
        """
        if not window_size:
            return "1080p"  # 默认使用1080p
            
        width, height = window_size
        
        # 计算与已知分辨率的接近程度
        closest_resolution = None
        min_diff = float('inf')
        
        for res, folder in self.resolution_folders.items():
            res_width, res_height = res
            # 计算差异（使用面积比例）
            diff = abs((width * height) - (res_width * res_height))
            if diff < min_diff:
                min_diff = diff
                closest_resolution = folder
                
        logger.info(f"窗口尺寸 {window_size} 最接近的分辨率文件夹: {closest_resolution}")
        return closest_resolution

    def match_template(self, frame, template_name=None):
        """匹配模板
        :param frame: 输入图像帧
        :param template_name: 指定模板名称，如果为None则匹配所有模板
        :return: 匹配结果字典或None
        """
            
        best_match = None
        best_score = 0

        # 确定要匹配的模板
        templates_to_match = {}
        if template_name:
            if template_name in self.templates:
                templates_to_match[template_name] = self.templates[template_name]
            else:
                logger.warning(f"未找到指定模板: {template_name}")
                return None
        else:
            templates_to_match = self.templates

        # 对每个模板进行匹配
        for name, template_info in templates_to_match.items():
            template_img = template_info["image"]
            threshold = template_info["threshold"]
            
            # 处理带透明度的模板
            result = self._match_with_alpha(frame, template_img, threshold)
            
            if result and result["score"] > best_score:
                best_score = result["score"]
                best_match = {
                    "name": name,
                    "score": result["score"],
                    "location": result["location"],
                    "size": (template_img.shape[1], template_img.shape[0])
                }

        self.last_match = best_match
        return best_match

    def _match_with_alpha(self, frame, template, threshold):
        """带透明度的模板匹配
        :param frame: 输入图像
        :param template: 模板图像（可能带透明通道）
        :param threshold: 匹配阈值
        :return: 匹配结果或None
        """
        # 对输入图像进行二值化预处理
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        _, frame_binary = cv2.threshold(frame_gray, 210, 255, cv2.THRESH_BINARY)

        # 检查模板是否有透明通道
        has_alpha = template.shape[2] == 4 if len(template.shape) > 2 else False

        if has_alpha:
            # 分离RGB和Alpha通道
            bgr = template[:, :, 0:3]
            alpha = template[:, :, 3]

            # 对模板图像进行二值化预处理
            bgr_gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            _, bgr_binary = cv2.threshold(bgr_gray, 210, 255, cv2.THRESH_BINARY)

            # 创建掩码（只考虑非透明区域）
            mask = np.uint8(alpha > 0) * 255

            # 使用掩码进行模板匹配
            result = cv2.matchTemplate(frame_binary, bgr_binary, cv2.TM_SQDIFF_NORMED, mask=mask)
        else:
            # 对模板图像进行二值化预处理
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if len(template.shape) == 3 else template
            _, template_binary = cv2.threshold(template_gray, 210, 255, cv2.THRESH_BINARY)

            # 无透明通道，直接匹配
            result = cv2.matchTemplate(frame_binary, template_binary, cv2.TM_SQDIFF_NORMED)

        # 查找最佳匹配位置
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # 使用TM_SQDIFF_NORMED方法，值越小越好，需要转换为相似度分数
        score = 1.0 - min_val  # 转换为相似度分数，值越大越好
        location = min_loc     # TM_SQDIFF_NORMED使用min_loc作为最佳匹配位置

        if score >= threshold:
            return {
                "score": score,
                "location": location
            }
        return None