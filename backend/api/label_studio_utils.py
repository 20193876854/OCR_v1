"""
Label Studio 集成工具
用于自动创建和同步 OCR 任务到 Label Studio
"""
import requests
import logging
from django.conf import settings
from datetime import datetime, timezone
import jwt

logger = logging.getLogger(__name__)


class LabelStudioClient:
    """Label Studio API 客户端"""
    
    def __init__(self):
        self.base_url = settings.LABEL_STUDIO_URL
        self.api_key = settings.LABEL_STUDIO_API_KEY
        self.project_id = settings.LABEL_STUDIO_PROJECT_ID
        self._access_token = None
        self._token_expiry = None
    
    def is_configured(self):
        """检查是否配置了 Label Studio"""
        return bool(self.api_key and self.base_url)
    
    def _is_jwt_token(self):
        """检查 API key 是否是 JWT 格式 (Personal Access Token)"""
        try:
            # JWT tokens 以 'eyJ' 开头
            return self.api_key.startswith('eyJ')
        except:
            return False
    
    def _get_access_token(self):
        """
        如果使用 Personal Access Token (JWT),则获取 access token
        否则直接返回 API key (Legacy Token)
        """
        if not self._is_jwt_token():
            # Legacy token,直接使用
            return self.api_key
        
        # 检查现有 access token 是否仍然有效
        if self._access_token and self._token_expiry:
            if datetime.now(timezone.utc).timestamp() < self._token_expiry - 60:  # 提前60秒刷新
                return self._access_token
        
        # 使用 refresh token 获取新的 access token
        try:
            url = f"{self.base_url}/api/token/refresh"
            response = requests.post(
                url,
                json={"refresh": self.api_key},
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            self._access_token = result.get('access')
            
            # 解析 access token 的过期时间
            try:
                decoded = jwt.decode(self._access_token, options={"verify_signature": False})
                self._token_expiry = decoded.get('exp')
            except:
                # 如果无法解析,默认5分钟后过期
                self._token_expiry = datetime.now(timezone.utc).timestamp() + 300
            
            logger.info("成功获取 Label Studio access token")
            return self._access_token
            
        except Exception as e:
            logger.error(f"获取 Label Studio access token 失败: {e}")
            return None
    
    def _get_headers(self):
        """获取请求头,根据 token 类型使用不同的格式"""
        access_token = self._get_access_token()
        if not access_token:
            return None
        
        if self._is_jwt_token():
            # Personal Access Token - 使用 Bearer
            auth_header = f'Bearer {access_token}'
        else:
            # Legacy Token - 使用 Token
            auth_header = f'Token {access_token}'
        
        return {
            'Authorization': auth_header,
            'Content-Type': 'application/json'
        }
    
    def create_task(self, task_data):
        """
        创建 Label Studio 任务
        
        Args:
            task_data (dict): 任务数据,格式:
                {
                    "data": {
                        "image": "http://example.com/image.jpg",
                        "text": "Sample text"
                    },
                    "annotations": [...],  # 可选
                    "predictions": [...]   # 可选
                }
        
        Returns:
            dict: 创建的任务信息
        """
        if not self.is_configured():
            logger.warning("Label Studio 未配置,跳过任务创建")
            return None
        
        headers = self._get_headers()
        if not headers:
            logger.error("无法获取 Label Studio 认证信息")
            return None
        
        url = f"{self.base_url}/api/projects/{self.project_id}/tasks"
        
        try:
            response = requests.post(url, json=task_data, headers=headers, timeout=10)
            response.raise_for_status()
            
            task_info = response.json()
            logger.info(f"成功创建 Label Studio 任务: ID={task_info.get('id')}")
            return task_info
            
        except requests.exceptions.RequestException as e:
            logger.error(f"创建 Label Studio 任务失败: {e}")
            return None
    
    def create_tasks_batch(self, tasks_data_list):
        """
        批量创建 Label Studio 任务
        
        Args:
            tasks_data_list (list): 任务数据列表
        
        Returns:
            dict: 包含任务ID列表和其他信息, 格式: 
                {
                    'task_count': 10,
                    'task_ids': [123, 124, 125, ...],
                    'annotation_count': 0,
                    'prediction_count': 0,
                    'duration': 0.5,
                    'file_upload_ids': [],
                    'could_be_tasks_list': False,
                    'found_formats': [],
                    'data_columns': []
                }
        """
        if not self.is_configured():
            logger.warning("Label Studio 未配置,跳过批量任务创建")
            return None
        
        headers = self._get_headers()
        if not headers:
            logger.error("无法获取 Label Studio 认证信息")
            return None
        
        url = f"{self.base_url}/api/projects/{self.project_id}/import"
        
        try:
            # 记录推送前的任务数量
            tasks_before = self._get_project_task_count()
            
            response = requests.post(url, json=tasks_data_list, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            task_count = result.get('task_count', len(tasks_data_list))
            task_ids = result.get('task_ids', [])
            
            # 如果 API 没有返回 task_ids (import API 通常不返回)
            # 尝试获取最新创建的任务 IDs
            if not task_ids and task_count > 0:
                logger.info("API 未返回 task_ids，尝试获取最新创建的任务...")
                task_ids = self._get_latest_task_ids(count=task_count, tasks_before=tasks_before)
                result['task_ids'] = task_ids
            
            logger.info(f"成功批量创建 {task_count} 个 Label Studio 任务, IDs: {task_ids}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"批量创建 Label Studio 任务失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"错误详情: {error_detail}")
                except:
                    logger.error(f"响应内容: {e.response.text[:500]}")
            return None
    
    def _get_project_task_count(self):
        """获取项目当前的任务数量"""
        try:
            headers = self._get_headers()
            url = f"{self.base_url}/api/projects/{self.project_id}"
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            project_info = response.json()
            return project_info.get('task_number', 0)
        except Exception as e:
            logger.warning(f"获取项目任务数量失败: {e}")
            return 0
    
    def _get_latest_task_ids(self, count, tasks_before=0):
        """获取最新创建的任务 IDs"""
        try:
            headers = self._get_headers()
            # 获取最新的任务，按 ID 降序排列
            url = f"{self.base_url}/api/projects/{self.project_id}/tasks"
            params = {
                'page_size': count + 10,  # 多获取一些以防万一
                'ordering': '-id'  # 按 ID 降序
            }
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            tasks = response.json()
            if isinstance(tasks, dict):
                tasks = tasks.get('tasks', [])
            
            # 取最新的 count 个任务的 ID
            task_ids = [task['id'] for task in tasks[:count]]
            logger.info(f"获取到最新创建的 {len(task_ids)} 个任务 IDs")
            return task_ids
            
        except Exception as e:
            logger.error(f"获取最新任务 IDs 失败: {e}")
            return []
    
    def get_task(self, task_id):
        """获取任务详情"""
        if not self.is_configured():
            return None
        
        headers = self._get_headers()
        if not headers:
            return None
        
        url = f"{self.base_url}/api/tasks/{task_id}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"获取 Label Studio 任务失败: {e}")
            return None
    
    def delete_task(self, task_id):
        """删除任务"""
        if not self.is_configured():
            return False
        
        headers = self._get_headers()
        if not headers:
            return False
        
        url = f"{self.base_url}/api/tasks/{task_id}"
        
        try:
            response = requests.delete(url, headers=headers, timeout=10)
            response.raise_for_status()
            logger.info(f"成功删除 Label Studio 任务: ID={task_id}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"删除 Label Studio 任务失败: {e}")
            return False
    
    def get_tasks(self):
        """获取项目中的所有任务"""
        if not self.is_configured():
            return []
        
        headers = self._get_headers()
        if not headers:
            return []
        
        url = f"{self.base_url}/api/projects/{self.project_id}/tasks"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            # Label Studio API 可能返回字典或列表
            if isinstance(result, dict):
                return result.get('tasks', [])
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"获取 Label Studio 任务列表失败: {e}")
            return []
    
    def update_task(self, task_id, update_data):
        """更新任务数据"""
        if not self.is_configured():
            return False
        
        headers = self._get_headers()
        if not headers:
            return False
        
        url = f"{self.base_url}/api/tasks/{task_id}"
        
        try:
            response = requests.patch(url, json=update_data, headers=headers, timeout=10)
            response.raise_for_status()
            logger.info(f"成功更新 Label Studio 任务: ID={task_id}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"更新 Label Studio 任务失败: {e}")
            return False
    
    def test_connection(self):
        """测试连接"""
        if not self.is_configured():
            return False, "Label Studio 未配置"
        
        headers = self._get_headers()
        if not headers:
            return False, "无法获取认证信息"
        
        url = f"{self.base_url}/api/projects/{self.project_id}"
        
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            project_info = response.json()
            return True, f"连接成功! 项目: {project_info.get('title', 'Unknown')}"
        except requests.exceptions.RequestException as e:
            return False, f"连接失败: {str(e)}"


def convert_ocr_to_label_studio_tasks(ocr_json, doc_id, base_url):
    """
    将 MinerU OCR JSON 转换为 Label Studio 任务格式
    
    Args:
        ocr_json (dict): MinerU 输出的 JSON
        doc_id (int): 文档 ID
        base_url (str): 图片访问基础 URL (例如: http://localhost:8010/media/pages)
    
    Returns:
        list: Label Studio 任务列表
    """
    tasks = []
    pdf_info = ocr_json.get('pdf_info', [])
    
    for page_idx, page_data in enumerate(pdf_info):
        page_num = page_idx + 1
        
        # 构建任务数据
        task = {
            "data": {
                "image": f"{base_url}/doc_{doc_id}/page-{str(page_num).zfill(4)}.jpg",
                "doc_id": doc_id,
                "page_num": page_num,
                "total_pages": len(pdf_info)
            }
        }
        
        # 添加预标注 (从 OCR 结果)
        predictions = []
        for layout_item in page_data.get('layout_dets', []):
            bbox = layout_item.get('bbox', [])
            category = layout_item.get('category_type', 'text')
            
            if bbox and len(bbox) == 4:
                # 转换为 Label Studio 格式
                x, y, w, h = bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]
                
                prediction = {
                    "type": "rectanglelabels",
                    "value": {
                        "x": x * 100,  # 转换为百分比
                        "y": y * 100,
                        "width": w * 100,
                        "height": h * 100,
                        "rectanglelabels": [category]
                    },
                    "from_name": "label",
                    "to_name": "image"
                }
                predictions.append(prediction)
        
        if predictions:
            task["predictions"] = [{"result": predictions}]
        
        tasks.append(task)
    
    return tasks
