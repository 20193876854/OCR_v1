import subprocess
import os
import json
import logging
from pathlib import Path
import requests
import uuid
import shutil
import mimetypes

from django.utils.text import get_valid_filename
import unidecode

from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.core.files.storage import FileSystemStorage
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from pdf2image import convert_from_path

from .models import OcrDocument
from .serializers import OcrDocumentSerializer
from .tasks import process_pdf_with_mineru
from .label_studio_utils import LabelStudioClient

logger = logging.getLogger(__name__)

DATA_ROOT = settings.DATA_ROOT_PATH
PDF_UPLOAD_DIR = DATA_ROOT / 'data' / 'pdfs_to_process'
BASE_OUTPUT_DIR = DATA_ROOT / 'data' / 'mineru_output'
POPPLER_PATH = os.getenv('POPPLER_PATH', None)

# The helper functions _create_ls_region and _generate_ls_tasks remain unchanged.
# ... (您的 _create_ls_region 和 _generate_ls_tasks 函数放在这里)
def _create_ls_region(bbox, page_dims, label, text_content=None):
    page_width, page_height = page_dims
    x1, y1, x2, y2 = bbox
    if page_width == 0 or page_height == 0: return []
    x = (x1 / page_width) * 100; y = (y1 / page_height) * 100
    width = ((x2 - x1) / page_width) * 100; height = ((y2 - y1) / page_height) * 100
    region_id = f"ls_{uuid.uuid4().hex[:10]}"
    results = [{"id": region_id, "from_name": "bbox", "to_name": "image", "type": "rectanglelabels", "value": {"x": x, "y": y, "width": width, "height": height, "rotation": 0, "rectanglelabels": [label]}}]
    if text_content and text_content.strip():
        results.append({"id": region_id, "from_name": "transcription", "to_name": "image", "type": "textarea", "value": {"text": [text_content.strip()]}})
    return results

def _generate_ls_tasks(mineru_data, doc: OcrDocument, unique_folder_name: str):
    ls_tasks = []
    task_output_dir = BASE_OUTPUT_DIR / unique_folder_name
    pdf_info = mineru_data.get('pdf_info', [])
    if not pdf_info: raise ValueError("Invalid MinerU JSON format: 'pdf_info' key missing.")
    # 映射到 label_studio_config.xml 中定义的标签名称
    type_mapping = {
        'text': 'Para',      # 对应 <Label value="Para" />
        'title': 'Title', 
        'list': 'List', 
        'figure': 'Figure', 
        'foot': 'Footer',    # 对应 <Label value="Footer" />
        'head': 'Header',    # 对应 <Label value="Header" />
        'equation': 'Formula',  # 对应 <Label value="Formula" />
        'table': 'Table'
    }
    
    # 获取 PDF 文件名
    pdf_path = Path(doc.original_pdf_path)
    total_pages = len(pdf_info)
    
    for page_data in pdf_info:
        page_index = page_data.get('page_idx', 0)
        page_num = page_index + 1
        page_size = page_data.get('page_size')
        if not page_size or len(page_size) != 2 or page_size[0] == 0 or page_size[1] == 0:
            logger.warning(f"Page size missing or invalid for page {page_index}. Skipping."); continue
        page_dims = (page_size[0], page_size[1])
        page_filename = f"page-{str(page_num).zfill(4)}.jpg"
        image_path = task_output_dir / "pages" / page_filename
        if not image_path.exists():
            logger.warning(f"Could not find image for page {page_num} at expected path: {image_path}"); continue
        
        # 使用 HTTP URL 格式访问图片
        backend_url = os.getenv('BACKEND_EXTERNAL_URL', 'http://localhost:8010')
        image_url = f"{backend_url}/api/images/{unique_folder_name}/{page_filename}"
        
        # 添加完整的元数据
        task = {
            "data": {
                "image": image_url,
                "doc_id": doc.id,
                "page_num": page_num,
                "total_pages": total_pages,
                "filename": pdf_path.name
            },
            "predictions": [{"result": []}]
        }
        
        all_blocks = page_data.get('para_blocks', []) + page_data.get('preproc_blocks', [])
        for block in all_blocks:
            block_type = block.get('type')
            label = type_mapping.get(block_type, 'Unknown')
            if block_type == 'figure':
                if 'bbox' in block: task["predictions"][0]["result"].extend(_create_ls_region(block['bbox'], page_dims, 'Figure'))
                for line in block.get('lines', []):
                    if 'bbox' in line: task["predictions"][0]["result"].extend(_create_ls_region(line['bbox'], page_dims, 'Text', ''.join(s.get('content', '') for s in line.get('spans', []))))
            elif block_type in ['text', 'title', 'list', 'foot', 'head']:
                for line in block.get('lines', []):
                    if 'bbox' in line: task["predictions"][0]["result"].extend(_create_ls_region(line['bbox'], page_dims, label, ''.join(s.get('content', '') for s in line.get('spans', []))))
            elif 'bbox' in block:
                task["predictions"][0]["result"].extend(_create_ls_region(block['bbox'], page_dims, label))
        if task["predictions"][0]["result"]: ls_tasks.append(task)
    return ls_tasks


class DocumentListView(APIView):
    def get(self, request, *args, **kwargs):
        documents = OcrDocument.objects.all().order_by('-created_at')
        serializer = OcrDocumentSerializer(documents, many=True)
        return Response(serializer.data)

class DocumentDetailView(APIView):
    def get_object(self, pk):
        try:
            return OcrDocument.objects.get(pk=pk)
        except OcrDocument.DoesNotExist:
            return None

    def get(self, request, pk, *args, **kwargs):
        doc = self.get_object(pk)
        if doc is None:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = OcrDocumentSerializer(doc)
        return Response(serializer.data)

    def delete(self, request, pk, *args, **kwargs):
        doc = self.get_object(pk)
        if doc is None:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            if doc.original_pdf_path and os.path.exists(doc.original_pdf_path):
                os.remove(doc.original_pdf_path)
            if doc.mineru_json_path:
                output_dir_parent = Path(doc.mineru_json_path).parents[2] 
                if os.path.isdir(output_dir_parent) and output_dir_parent.name != 'mineru_output':
                    shutil.rmtree(output_dir_parent)
        except Exception as e:
            logger.error(f"Error deleting associated files for doc ID {pk}: {e}")
        
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentUploadView(APIView):
    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        ascii_name = unidecode.unidecode(file_obj.name)
        safe_filename = get_valid_filename(ascii_name)

        os.makedirs(PDF_UPLOAD_DIR, exist_ok=True)
        fs = FileSystemStorage(location=str(PDF_UPLOAD_DIR))
        
        filename = fs.save(safe_filename, file_obj)
        uploaded_file_path = fs.path(filename)
        
        doc = OcrDocument.objects.create(
            original_pdf_path=uploaded_file_path,
            status='pending'
        )
        process_pdf_with_mineru.delay(doc.id)
        serializer = OcrDocumentSerializer(doc)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

class LabelStudioTaskView(APIView):
    """
    处理对原始OCR JSON数据的请求。
    此视图现在将原始JSON文件作为附件提供下载，
    以支持更稳定的人工处理流程。
    """
    def get(self, request, pk, *args, **kwargs):
        logger.info(f"--- [GET] 开始为文档ID为 {pk} 的文件提供原始OCR JSON下载 ---")
        try:
            doc = OcrDocument.objects.get(pk=pk)

            # 现在的失败条件更简单：只检查原始JSON是否存在
            if not doc.raw_ocr_json:
                return Response(
                    {"error": "未找到此文档的原始OCR JSON。可能在处理过程中失败。"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 将JSON数据（Python字典/列表）转换回字符串
            json_string = json.dumps(doc.raw_ocr_json, indent=4, ensure_ascii=False)

            # 为下载的文件创建一个名称
            original_filename = Path(doc.original_pdf_path).stem
            download_filename = f"{original_filename}_raw_ocr.json"

            # 创建一个HttpResponse对象，设置内容类型和Content-Disposition头
            # 以便浏览器触发下载操作
            response = HttpResponse(json_string, content_type='application/json; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{download_filename}"'
            
            return response

        except OcrDocument.DoesNotExist:
            return Response({"error": "文档未找到"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"在为文档ID {pk} 提供下载时发生意外错误: {e}", exc_info=True)
            return Response({"error": f"发生意外的服务器错误: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# --- REPLACED RAGFLOW VIEW WITH THIS ---
class SubmitCorrectionView(APIView):
    """
    Handles uploading the corrected JSON file from Label Studio.
    """
    def post(self, request, pk, *args, **kwargs):
        try:
            doc = OcrDocument.objects.get(pk=pk)
        except OcrDocument.DoesNotExist:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)

        # 1. 从 request.FILES 获取上传的文件
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No JSON file provided in 'file' field"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 2. 从上传的文件对象中读取并解析JSON
            corrected_data = json.load(file_obj)
            
            # 简单的验证，确保它是一个列表 (Label Studio 导出的是任务列表)
            if not isinstance(corrected_data, list):
                return Response({"error": "Invalid JSON format. Expected a list of tasks."}, status=status.HTTP_400_BAD_REQUEST)

            # 3. 保存数据并更新状态
            doc.corrected_label_studio_json = corrected_data
            doc.status = 'corrected'
            doc.save()
            
            serializer = OcrDocumentSerializer(doc)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except json.JSONDecodeError:
            return Response({"error": "Uploaded file is not a valid JSON."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in SubmitCorrectionView for doc ID {pk}: {e}", exc_info=True)
            return Response({"error": f"An unexpected server error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class GenerateRAGFlowPayloadView(APIView):
    """
    将校对后的 Label Studio JSON 转换为 RAGFlow 兼容的
    add_chunk payload，并提供为可下载的文件。
    """
    def get(self, request, pk, *args, **kwargs):
        logger.info(f"--- [GET] 开始为文档ID {pk} 生成RAGFlow入库文件 ---")
        try:
            doc = OcrDocument.objects.get(pk=pk)

            # 1. 检查是否存在校对后的数据
            if not doc.corrected_label_studio_json:
                return Response(
                    {"error": "未找到校对后的数据(Corrected JSON)。请先上传校对文件。"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 2. 转换逻辑
            pages = {}
            all_tasks_data = doc.corrected_label_studio_json
            
            for i, task_data in enumerate(all_tasks_data):
                annotations = task_data.get('completions') or task_data.get('annotations')
                if not annotations: continue

                result = annotations[0].get('result', [])
                page_num = i + 1

                for item in result:
                    if item.get('type') == 'textarea':
                        if page_num not in pages:
                            pages[page_num] = []
                        text_list = item.get('value', {}).get('text', [])
                        if text_list:
                            pages[page_num].append(text_list[0])
            
            chunks = []
            for page_num in sorted(pages.keys()):
                page_text = "\n".join(pages[page_num])
                chunks.append({"content_ltxt": page_text})
            
            ragflow_payload = {
                "doc_id": Path(doc.original_pdf_path).name,
                "kb_name": "test_kb", # 您可以稍后将其更改为动态值
                "chunks": chunks
            }
            
            # 3. 更新状态为 'ingested'
            doc.status = 'ingested'
            doc.save(update_fields=['status'])

            # 4. 将结果作为可下载文件提供
            json_string = json.dumps(ragflow_payload, indent=4, ensure_ascii=False)
            original_filename = Path(doc.original_pdf_path).stem
            download_filename = f"{original_filename}_ragflow_payload.json"

            response = HttpResponse(json_string, content_type='application/json; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{download_filename}"'
            
            return response

        except OcrDocument.DoesNotExist:
            return Response({"error": "文档未找到"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"在为文档ID {pk} 生成RAGFlow文件时发生意外错误: {e}", exc_info=True)
            return Response({"error": f"发生意外的服务器错误: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IngestToRagflowView(APIView):
    """
    接收校对后的 Label Studio JSON 数据，保存并转换为 RAGFlow 格式
    支持两种方式：
    1. 上传 JSON 文件 (multipart/form-data)
    2. 直接 POST JSON 数据 (application/json)
    """
    def post(self, request, pk, *args, **kwargs):
        logger.info(f"--- [POST] 开始处理文档ID {pk} 的校对数据 ---")
        try:
            doc = OcrDocument.objects.get(pk=pk)
        except OcrDocument.DoesNotExist:
            return Response({"error": "文档未找到"}, status=status.HTTP_404_NOT_FOUND)

        try:
            # 尝试从上传的文件中读取数据
            file_obj = request.FILES.get('file')
            if file_obj:
                logger.info(f"从上传文件中读取校对数据")
                corrected_data = json.load(file_obj)
            else:
                # 尝试从 request body 中读取 JSON
                corrected_data = request.data
                logger.info(f"从 request body 中读取校对数据")
            
            # 验证数据格式
            if not isinstance(corrected_data, list):
                return Response({
                    "error": "Invalid JSON format. Expected a list of tasks."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"收到 {len(corrected_data)} 个任务的校对数据")
            
            # 保存校对后的数据
            doc.corrected_label_studio_json = corrected_data
            
            # 转换为 RAGFlow 格式
            pages = {}
            
            for i, task_data in enumerate(corrected_data):
                # Label Studio 导出的数据可能使用 'annotations' 或 'completions'
                annotations = task_data.get('annotations') or task_data.get('completions')
                
                if not annotations:
                    logger.warning(f"任务 {i} 没有标注数据，跳过")
                    continue
                
                # 获取第一个标注结果
                result = annotations[0].get('result', [])
                page_num = task_data.get('data', {}).get('page_num', i + 1)
                
                logger.debug(f"处理第 {page_num} 页，包含 {len(result)} 个标注项")
                
                # 提取文本内容
                for item in result:
                    if item.get('type') == 'textarea':
                        if page_num not in pages:
                            pages[page_num] = []
                        text_list = item.get('value', {}).get('text', [])
                        if text_list:
                            pages[page_num].append(text_list[0])
            
            # 生成 RAGFlow chunks
            chunks = []
            for page_num in sorted(pages.keys()):
                page_text = "\n".join(pages[page_num])
                if page_text.strip():  # 只添加非空内容
                    chunks.append({"content_ltxt": page_text})
            
            logger.info(f"生成了 {len(chunks)} 个文本块")
            
            # 构建 RAGFlow payload
            ragflow_payload = {
                "doc_id": Path(doc.original_pdf_path).name,
                "kb_name": "test_kb",
                "chunks": chunks
            }
            
            # 更新状态
            doc.status = 'ingested'
            doc.save()
            
            logger.info(f"文档 {pk} 校对数据已保存，状态更新为 'ingested'")
            
            # 返回成功响应
            serializer = OcrDocumentSerializer(doc)
            return Response({
                "message": "校对数据已保存并转换为 RAGFlow 格式",
                "document": serializer.data,
                "chunks_count": len(chunks),
                "ragflow_payload": ragflow_payload
            }, status=status.HTTP_200_OK)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            return Response({
                "error": "上传的文件不是有效的 JSON 格式"
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"处理文档 {pk} 校对数据时发生错误: {e}", exc_info=True)
            return Response({
                "error": f"处理失败: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PushToLabelStudioView(APIView):
    """
    手动推送文档到 Label Studio
    支持检查是否已推送和强制重新推送
    """
    def post(self, request, pk, *args, **kwargs):
        try:
            doc = OcrDocument.objects.get(id=pk)
            
            # 检查文档是否已处理完成
            if doc.status not in ['processed', 'corrected', 'ingested']:
                return Response({
                    "error": "文档还未处理完成,无法推送",
                    "status": doc.status
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 检查是否强制推送
            force = request.data.get('force', False)
            
            # 如果已推送且不是强制推送,返回提示
            if doc.label_studio_synced and not force:
                return Response({
                    "message": "文档已推送到 Label Studio",
                    "synced": True,
                    "task_ids": doc.label_studio_task_ids,
                    "sync_time": doc.label_studio_sync_time,
                    "hint": "如需重新推送,请设置 force=true"
                }, status=status.HTTP_200_OK)
            
            # 执行推送
            from django.utils import timezone
            ls_client = LabelStudioClient()
            
            if not ls_client.is_configured():
                return Response({
                    "error": "Label Studio 未配置,请设置 LABEL_STUDIO_API_KEY"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 读取 MinerU JSON 并生成包含预标注的任务
            if not doc.mineru_json_path:
                return Response({
                    "error": "未找到处理结果文件"
                }, status=status.HTTP_404_NOT_FOUND)
            
            mineru_json_path = Path(doc.mineru_json_path)
            
            if not mineru_json_path.exists():
                return Response({
                    "error": "处理结果文件不存在"
                }, status=status.HTTP_404_NOT_FOUND)
            
            # 读取 MinerU JSON 数据
            try:
                with open(mineru_json_path, 'r', encoding='utf-8') as f:
                    mineru_data = json.load(f)
            except Exception as e:
                logger.error(f"读取 MinerU JSON 失败: {e}")
                return Response({
                    "error": f"读取处理结果失败: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # 使用 _generate_ls_tasks 生成包含预标注的任务
            output_dir = mineru_json_path.parents[2]
            unique_folder_name = output_dir.name
            
            try:
                tasks_data = _generate_ls_tasks(mineru_data, doc, unique_folder_name)
            except Exception as e:
                logger.error(f"生成 Label Studio 任务失败: {e}", exc_info=True)
                return Response({
                    "error": f"生成任务失败: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # 批量创建任务
            result = ls_client.create_tasks_batch(tasks_data)
            
            if result:
                task_ids = result.get('task_ids', [])
                doc.label_studio_synced = True
                doc.label_studio_task_ids = task_ids
                doc.label_studio_sync_time = timezone.now()
                doc.save(update_fields=['label_studio_synced', 'label_studio_task_ids', 'label_studio_sync_time'])
                
                return Response({
                    "message": f"成功推送 {len(tasks_data)} 个任务到 Label Studio",
                    "task_count": len(tasks_data),
                    "task_ids": task_ids,
                    "sync_time": doc.label_studio_sync_time
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "error": "推送到 Label Studio 失败,请检查配置和日志"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except OcrDocument.DoesNotExist:
            return Response({"error": "文档未找到"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"推送文档 {pk} 到 Label Studio 失败: {e}", exc_info=True)
            return Response({
                "error": f"推送失败: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ServeImageView(APIView):
    """
    静态图片服务
    为 Label Studio 提供图片访问
    URL 格式: /api/images/{document_id}/{filename}
    """
    
    def options(self, request, document_id, filename):
        """处理 CORS 预检请求"""
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response
    
    def get(self, request, document_id, filename):
        """提供图片文件"""
        try:
            # 构建图片路径
            image_path = BASE_OUTPUT_DIR / document_id / 'pages' / filename
            
            # 检查文件是否存在
            if not image_path.exists():
                logger.warning(f"图片不存在: {image_path}")
                raise Http404("图片不存在")
            
            # 检查文件安全性（防止路径遍历攻击）
            if not str(image_path.resolve()).startswith(str(BASE_OUTPUT_DIR.resolve())):
                logger.warning(f"非法路径访问尝试: {image_path}")
                raise Http404("非法路径")
            
            # 获取文件的 MIME 类型
            content_type, _ = mimetypes.guess_type(str(image_path))
            if not content_type:
                content_type = 'application/octet-stream'
            
            # 返回文件并设置 CORS 头（允许 Label Studio 跨域访问）
            response = FileResponse(
                open(image_path, 'rb'),
                content_type=content_type,
                as_attachment=False
            )
            # 设置 CORS 头，允许所有来源访问
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response['Access-Control-Allow-Headers'] = '*'
            return response
            
        except Http404:
            raise
        except Exception as e:
            logger.error(f"提供图片失败: {e}", exc_info=True)
            raise Http404("图片加载失败")
