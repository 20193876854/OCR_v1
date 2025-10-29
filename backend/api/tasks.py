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
from .label_studio_utils import LabelStudioClient
from django.utils import timezone

logger = logging.getLogger(__name__)

DATA_ROOT = settings.DATA_ROOT_PATH
BASE_OUTPUT_DIR = DATA_ROOT / 'data' / 'mineru_output'
POPPLER_PATH = os.getenv('POPPLER_PATH', None)
MINERU_COMMAND = 'mineru'
@shared_task
def process_pdf_with_mineru(doc_id):
    doc = None
    try:
        doc = OcrDocument.objects.get(id=doc_id)
        doc.status = 'processing'
        doc.processing_log = '[开始] 准备处理 PDF 文档...\n'
        doc.save(update_fields=['status', 'processing_log'])

        pdf_path = Path(doc.original_pdf_path)
        unique_folder_name = uuid.uuid4().hex[:12]
        task_output_dir = BASE_OUTPUT_DIR / unique_folder_name
        os.makedirs(task_output_dir, exist_ok=True)
        
        doc.processing_log += f'[信息] 创建输出目录: {unique_folder_name}\n'
        doc.save(update_fields=['processing_log'])

        command_str = f'"{MINERU_COMMAND}" -p "{str(pdf_path)}" -o "{str(task_output_dir)}"'

        logger.info(f"Executing command: {command_str}")
        doc.processing_log += f'[命令] 执行 MinerU\n'
        doc.processing_log += f'命令: {command_str}\n'
        doc.processing_log += f'{"-" * 60}\n'
        doc.save(update_fields=['processing_log'])
        
        # 使用 Popen 实现实时日志流式读取
        process = subprocess.Popen(
            command_str,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 合并 stderr 到 stdout
            text=True,
            bufsize=1,  # 行缓冲
            universal_newlines=True
        )
        
        log_lines = []
        line_count = 0
        last_save_time = time.time()
        
        try:
            # 实时读取输出
            for line in process.stdout:
                line = line.rstrip()
                if line:  # 跳过空行
                    logger.info(f"MinerU[{doc_id}]: {line}")
                    
                    # 格式化日志输出
                    if 'error' in line.lower() or 'fail' in line.lower():
                        formatted_line = f'❌ {line}'
                    elif 'warning' in line.lower() or 'warn' in line.lower():
                        formatted_line = f'⚠️  {line}'
                    elif 'success' in line.lower() or 'complete' in line.lower():
                        formatted_line = f'✅ {line}'
                    elif 'processing' in line.lower() or 'page' in line.lower():
                        formatted_line = f'⚙️  {line}'
                    else:
                        formatted_line = f'📝 {line}'
                    
                    log_lines.append(formatted_line)
                    line_count += 1
                    
                    # 每 3 行或每 1.5 秒保存一次到数据库 (更频繁以获得更实时的体验)
                    current_time = time.time()
                    if line_count >= 3 or (current_time - last_save_time) >= 1.5:
                        doc.refresh_from_db()
                        doc.processing_log += '\n'.join(log_lines) + '\n'
                        doc.save(update_fields=['processing_log'])
                        log_lines = []
                        line_count = 0
                        last_save_time = current_time
            
            # 保存剩余日志
            if log_lines:
                doc.refresh_from_db()
                doc.processing_log += '\n'.join(log_lines) + '\n'
                doc.save(update_fields=['processing_log'])
            
            # 等待进程结束
            return_code = process.wait(timeout=3600)
            
            if return_code != 0:
                doc.refresh_from_db()
                doc.processing_log += f'\n{"-" * 60}\n'
                doc.processing_log += f'[错误] MinerU 执行失败, 返回码: {return_code}\n'
                doc.save(update_fields=['processing_log'])
                raise RuntimeError(f"MinerU execution failed with return code {return_code}.")
                
        except subprocess.TimeoutExpired:
            process.kill()
            doc.refresh_from_db()
            doc.processing_log += f'\n[错误] MinerU 执行超时 (>3600秒)\n'
            doc.save(update_fields=['processing_log'])
            raise RuntimeError("MinerU execution timeout.")
        
        doc.refresh_from_db()
        doc.processing_log += f'{"-" * 60}\n'
        doc.processing_log += '[信息] MinerU 执行完成,正在查找输出文件...\n'
        doc.save(update_fields=['processing_log'])
        
        mineru_created_dir = task_output_dir / pdf_path.stem
        json_path = mineru_created_dir / "auto" / f"{pdf_path.stem}_middle.json"
        
        time.sleep(1)
        
        if not os.path.exists(json_path):
            # 如果文件依然不存在,抛出错误,此时日志中已有详细的 stdout/stderr
            doc.processing_log += f'[错误] 未找到输出文件: {json_path}\n'
            doc.save(update_fields=['processing_log'])
            raise FileNotFoundError(f"'_middle.json' not found at expected path: {json_path}. MinerU did not produce the expected output.")
            
        # ===================== 核心修改结束 =====================

        logger.info(f"Found OCR JSON file at: {json_path}. Reading content.")
        doc.processing_log += f'[成功] 找到 OCR 结果文件\n'
        doc.save(update_fields=['processing_log'])
        
        with open(json_path, 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)
        
        doc.raw_ocr_json = ocr_data
        doc.save(update_fields=['raw_ocr_json'])
        logger.info(f"Successfully saved raw_ocr_json to database for Doc ID {doc_id}.")
        
        logger.info(f"Converting PDF pages to images for Doc ID {doc_id}.")
        doc.processing_log += f'[信息] 正在转换 PDF 页面为图片...\n'
        doc.save(update_fields=['processing_log'])
        
        pages_dir = task_output_dir / "pages"
        os.makedirs(pages_dir, exist_ok=True)
        
        pil_images = convert_from_path(pdf_path, poppler_path=POPPLER_PATH, thread_count=4, fmt='jpeg')
        for i, image in enumerate(pil_images):
            page_num = i + 1
            filename = f"page-{str(page_num).zfill(4)}.jpg"
            image.save(pages_dir / filename, 'JPEG')
        
        logger.info(f"Successfully converted and saved {len(pil_images)} images.")
        doc.processing_log += f'[成功] 已转换 {len(pil_images)} 页图片\n'
        doc.save(update_fields=['processing_log'])

        # 自动推送到 Label Studio
        try:
            doc.processing_log += '[信息] 正在推送任务到 Label Studio...\n'
            doc.save(update_fields=['processing_log'])
            
            ls_client = LabelStudioClient()
            if ls_client.is_configured():
                # 使用 _generate_ls_tasks 函数生成带预标注的任务
                from .views import _generate_ls_tasks
                
                try:
                    # 生成包含 OCR 预标注的任务数据
                    tasks_data = _generate_ls_tasks(ocr_data, doc, unique_folder_name)
                    
                    if not tasks_data:
                        logger.warning(f"No valid tasks generated for Doc ID {doc_id}")
                        doc.processing_log += '⚠️  未能生成有效的任务数据\n'
                        doc.save(update_fields=['processing_log'])
                    else:
                        doc.processing_log += f'[信息] 已生成 {len(tasks_data)} 个任务(包含OCR预标注)\n'
                        doc.save(update_fields=['processing_log'])
                        
                        # 批量创建任务
                        result = ls_client.create_tasks_batch(tasks_data)
                        if result:
                            task_ids = result.get('task_ids', [])
                            doc.refresh_from_db()
                            doc.processing_log += f'✅ 已推送 {len(tasks_data)} 个任务到 Label Studio\n'
                            doc.processing_log += f'[信息] 每个任务包含 OCR 识别的文本框和内容\n'
                            doc.label_studio_synced = True
                            doc.label_studio_task_ids = task_ids
                            doc.label_studio_sync_time = timezone.now()
                            doc.save(update_fields=['processing_log', 'label_studio_synced', 'label_studio_task_ids', 'label_studio_sync_time'])
                        else:
                            doc.processing_log += '⚠️  推送到 Label Studio 失败,请手动重试\n'
                            doc.save(update_fields=['processing_log'])
                            
                except Exception as generate_error:
                    logger.error(f"Error generating Label Studio tasks: {generate_error}", exc_info=True)
                    doc.processing_log += f'⚠️  生成任务数据失败: {str(generate_error)}\n'
                    doc.save(update_fields=['processing_log'])
            else:
                doc.processing_log += '[跳过] Label Studio 未配置 API Key\n'
                doc.save(update_fields=['processing_log'])
        except Exception as ls_error:
            logger.warning(f"Label Studio 推送失败: {ls_error}")
            doc.processing_log += f'⚠️  Label Studio 推送失败: {str(ls_error)}\n'
            doc.save(update_fields=['processing_log'])

        doc.mineru_json_path = str(json_path)
        doc.status = 'processed'
        doc.processing_log += '[完成] 文档处理成功!\n'
        doc.save(update_fields=['mineru_json_path', 'status', 'processing_log'])
        
        logger.info(f"Celery Task fully succeeded for Doc ID {doc_id}.")
        return f"Success: {str(json_path)}"

    except Exception as e:
        if doc:
            doc.status = 'failed'
            doc.processing_log += f'[失败] 处理异常: {str(e)}\n'
            doc.save(update_fields=['status', 'processing_log'])
        # 错误日志现在会包含更丰富的信息
        logger.error(f"Error in Celery task for doc ID {doc_id if 'doc_id' in locals() else 'unknown'}: {e}", exc_info=True)
        raise e