import subprocess
import os
import time
import uuid
import json
from celery import shared_task
from .models import OcrDocument
from django.conf import settings
from pathlib import Path
import logging
from pdf2image import convert_from_path
import requests

logger = logging.getLogger(__name__)

DATA_ROOT = settings.DATA_ROOT_PATH
BASE_OUTPUT_DIR = DATA_ROOT / 'data' / 'mineru_output'
POPPLER_PATH = os.getenv('POPPLER_PATH', None)
MINERU_COMMAND = 'mineru'

# Label Studio 配置
LABEL_STUDIO_URL = os.getenv('LABEL_STUDIO_URL', 'http://label-studio:8081')
LABEL_STUDIO_API_TOKEN = os.getenv('LABEL_STUDIO_API_TOKEN', '')
LABEL_STUDIO_PROJECT_ID = os.getenv('LABEL_STUDIO_PROJECT_ID', '')
AUTO_IMPORT_TO_LABEL_STUDIO = os.getenv('AUTO_IMPORT_TO_LABEL_STUDIO', 'true').lower() == 'true'

# GPU检测和配置
def check_gpu_available():
    """检测GPU是否可用"""
    try:
        import torch
        gpu_available = torch.cuda.is_available()
        if gpu_available:
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"✓ GPU可用: {gpu_count} 个设备, 主设备: {gpu_name}")
            return True
        else:
            logger.info("✗ GPU不可用，将使用CPU模式")
            return False
    except Exception as e:
        logger.warning(f"GPU检测失败: {e}，将使用CPU模式")
        return False

def _create_ls_region(bbox, page_dims, label, text_content=None):
    """创建Label Studio的区域标注"""
    page_width, page_height = page_dims
    x1, y1, x2, y2 = bbox
    if page_width == 0 or page_height == 0:
        return []
    
    x = (x1 / page_width) * 100
    y = (y1 / page_height) * 100
    width = ((x2 - x1) / page_width) * 100
    height = ((y2 - y1) / page_height) * 100
    
    region_id = f"ls_{uuid.uuid4().hex[:10]}"
    
    results = [{
        "id": region_id,
        "from_name": "bbox",
        "to_name": "image",
        "type": "rectanglelabels",
        "value": {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "rotation": 0,
            "rectanglelabels": [label]
        }
    }]
    
    if text_content and text_content.strip():
        results.append({
            "id": region_id,
            "from_name": "transcription",
            "to_name": "image",
            "type": "textarea",
            "value": {
                "text": [text_content.strip()]
            }
        })
    
    return results

def _generate_ls_tasks(mineru_data, doc, unique_folder_name):
    """从MinerU数据生成Label Studio任务"""
    ls_tasks = []
    task_output_dir = BASE_OUTPUT_DIR / unique_folder_name
    
    pdf_info = mineru_data.get('pdf_info', [])
    if not pdf_info:
        raise ValueError("Invalid MinerU JSON format: 'pdf_info' key missing.")
    
    type_mapping = {
        'text': 'Text',
        'title': 'Title',
        'list': 'List',
        'figure': 'Figure',
        'foot': 'Footer',
        'head': 'Header',
        'equation': 'Equation',
        'table': 'Table'
    }
    
    for page_data in pdf_info:
        page_index = page_data.get('page_idx', 0)
        page_size = page_data.get('page_size')
        
        if not page_size or len(page_size) != 2 or page_size[0] == 0 or page_size[1] == 0:
            logger.warning(f"Page size missing or invalid for page {page_index}. Skipping.")
            continue
        
        page_dims = (page_size[0], page_size[1])
        page_filename = f"page-{str(page_index + 1).zfill(4)}.jpg"
        image_path = task_output_dir / "pages" / page_filename
        
        if not image_path.exists():
            logger.warning(f"Could not find image for page {page_index + 1} at expected path: {image_path}")
            continue
        
        relative_image_path = Path('data') / 'mineru_output' / unique_folder_name / 'pages' / page_filename
        image_url = f"/data/local-files/?d={relative_image_path.as_posix()}"
        
        task = {
            "data": {"image": image_url},
            "predictions": [{"result": []}]
        }
        
        all_blocks = page_data.get('para_blocks', []) + page_data.get('preproc_blocks', [])
        
        for block in all_blocks:
            block_type = block.get('type')
            label = type_mapping.get(block_type, 'Unknown')
            
            if block_type == 'figure':
                if 'bbox' in block:
                    task["predictions"][0]["result"].extend(
                        _create_ls_region(block['bbox'], page_dims, 'Figure')
                    )
                for line in block.get('lines', []):
                    if 'bbox' in line:
                        text = ''.join(s.get('content', '') for s in line.get('spans', []))
                        task["predictions"][0]["result"].extend(
                            _create_ls_region(line['bbox'], page_dims, 'Text', text)
                        )
            elif block_type in ['text', 'title', 'list', 'foot', 'head']:
                for line in block.get('lines', []):
                    if 'bbox' in line:
                        text = ''.join(s.get('content', '') for s in line.get('spans', []))
                        task["predictions"][0]["result"].extend(
                            _create_ls_region(line['bbox'], page_dims, label, text)
                        )
            elif 'bbox' in block:
                task["predictions"][0]["result"].extend(
                    _create_ls_region(block['bbox'], page_dims, label)
                )
        
        if task["predictions"][0]["result"]:
            ls_tasks.append(task)
    
    return ls_tasks

def auto_import_to_label_studio(doc_id, ls_tasks):
    """自动将OCR结果导入Label Studio"""
    if not AUTO_IMPORT_TO_LABEL_STUDIO:
        logger.info(f"自动导入功能已禁用，跳过文档 {doc_id}")
        return False
    
    if not LABEL_STUDIO_API_TOKEN or not LABEL_STUDIO_PROJECT_ID:
        logger.warning(f"Label Studio配置不完整，跳过自动导入文档 {doc_id}")
        return False
    
    try:
        import_url = f"{LABEL_STUDIO_URL}/api/projects/{LABEL_STUDIO_PROJECT_ID}/import"
        headers = {
            "Authorization": f"Token {LABEL_STUDIO_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(import_url, json=ls_tasks, headers=headers, timeout=30)
        
        if response.status_code in [200, 201]:
            logger.info(f"✓ 成功自动导入 {len(ls_tasks)} 个任务到Label Studio (文档 {doc_id})")
            return True
        else:
            logger.error(f"Label Studio API返回错误 (文档 {doc_id}): {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"自动导入到Label Studio失败 (文档 {doc_id}): {e}", exc_info=True)
        return False

@shared_task
def process_pdf_with_mineru(doc_id):
    doc = None
    try:
        # 检测GPU可用性
        gpu_available = check_gpu_available()
        if gpu_available:
            logger.info(f"文档 {doc_id} 将使用GPU加速处理")
        else:
            logger.info(f"文档 {doc_id} 将使用CPU处理")
        
        doc = OcrDocument.objects.get(id=doc_id)
        doc.status = 'processing'
        doc.save(update_fields=['status'])

        pdf_path = Path(doc.original_pdf_path)
        unique_folder_name = uuid.uuid4().hex[:12]
        task_output_dir = BASE_OUTPUT_DIR / unique_folder_name
        os.makedirs(task_output_dir, exist_ok=True)

        command_str = f'"{MINERU_COMMAND}" -p "{str(pdf_path)}" -o "{str(task_output_dir)}"'

        logger.info(f"Executing command: {command_str}")
        result = subprocess.run(command_str, shell=True, capture_output=True, text=True, timeout=3600)

        # ==================== 核心修改开始 ====================
        
        # 无论成功与否，都先记录 stdout 和 stderr，便于调试
        if result.stdout:
            logger.info(f"MinerU STDOUT for Doc ID {doc_id}:\n{result.stdout}")
        if result.stderr:
            # 将 stderr 记录为警告，即使命令没有失败
            logger.warning(f"MinerU STDERR for Doc ID {doc_id}:\n{result.stderr}")

        if result.returncode != 0:
            # 如果返回码不为0，说明是明确的失败
            raise RuntimeError(f"MinerU execution failed with return code {result.returncode}.")

        mineru_created_dir = task_output_dir / pdf_path.stem
        json_path = mineru_created_dir / "auto" / f"{pdf_path.stem}_middle.json"
        
        time.sleep(1)
        
        if not os.path.exists(json_path):
            # 如果文件依然不存在，抛出错误，此时日志中已有详细的 stdout/stderr
            raise FileNotFoundError(f"'_middle.json' not found at expected path: {json_path}. MinerU did not produce the expected output.")
            
        # ===================== 核心修改结束 =====================

        logger.info(f"Found OCR JSON file at: {json_path}. Reading content.")
        with open(json_path, 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)
        
        doc.raw_ocr_json = ocr_data
        doc.save(update_fields=['raw_ocr_json'])
        logger.info(f"Successfully saved raw_ocr_json to database for Doc ID {doc_id}.")
        
        logger.info(f"Converting PDF pages to images for Doc ID {doc_id}.")
        pages_dir = task_output_dir / "pages"
        os.makedirs(pages_dir, exist_ok=True)
        
        pil_images = convert_from_path(pdf_path, poppler_path=POPPLER_PATH, thread_count=4, fmt='jpeg')
        for i, image in enumerate(pil_images):
            page_num = i + 1
            filename = f"page-{str(page_num).zfill(4)}.jpg"
            image.save(pages_dir / filename, 'JPEG')
        
        logger.info(f"Successfully converted and saved {len(pil_images)} images.")

        doc.mineru_json_path = str(json_path)
        doc.status = 'processed'
        doc.save(update_fields=['mineru_json_path', 'status'])
        
        logger.info(f"Celery Task fully succeeded for Doc ID {doc_id}.")
        
        # ============ 新增：自动导入Label Studio ============
        if AUTO_IMPORT_TO_LABEL_STUDIO:
            try:
                logger.info(f"开始自动导入文档 {doc_id} 到Label Studio...")
                
                # 生成Label Studio任务
                mineru_json_path = Path(doc.mineru_json_path)
                unique_folder_name = mineru_json_path.parents[1].name
                ls_tasks = _generate_ls_tasks(ocr_data, doc, unique_folder_name)
                
                # 自动导入
                if auto_import_to_label_studio(doc_id, ls_tasks):
                    doc.label_studio_project_id = LABEL_STUDIO_PROJECT_ID
                    doc.save(update_fields=['label_studio_project_id'])
                    logger.info(f"✓ 文档 {doc_id} 已自动导入到Label Studio项目 {LABEL_STUDIO_PROJECT_ID}")
                else:
                    logger.warning(f"⚠ 文档 {doc_id} 自动导入Label Studio失败，但OCR处理已完成")
            except Exception as e:
                logger.error(f"自动导入Label Studio时出错 (文档 {doc_id}): {e}", exc_info=True)
                # 不抛出异常，因为OCR处理已完成
        # ==================================================
        
        return f"Success: {str(json_path)}"

    except Exception as e:
        if doc:
            doc.status = 'failed'
            doc.save(update_fields=['status'])
        # 错误日志现在会包含更丰富的信息
        logger.error(f"Error in Celery task for doc ID {doc_id if 'doc_id' in locals() else 'unknown'}: {e}", exc_info=True)
        raise e