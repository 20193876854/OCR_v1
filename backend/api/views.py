import subprocess
import os
import json
import logging
from pathlib import Path
import requests
import uuid
import shutil

from django.utils.text import get_valid_filename
import unidecode

from django.http import JsonResponse, HttpResponse
from django.core.files.storage import FileSystemStorage
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from pdf2image import convert_from_path

from .models import OcrDocument
from .serializers import OcrDocumentSerializer
from .tasks import process_pdf_with_mineru

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
    type_mapping = {'text': 'Text', 'title': 'Title', 'list': 'List', 'figure': 'Figure', 'foot': 'Footer', 'head': 'Header', 'equation': 'Equation', 'table': 'Table'}
    for page_data in pdf_info:
        page_index = page_data.get('page_idx', 0)
        page_size = page_data.get('page_size')
        if not page_size or len(page_size) != 2 or page_size[0] == 0 or page_size[1] == 0:
            logger.warning(f"Page size missing or invalid for page {page_index}. Skipping."); continue
        page_dims = (page_size[0], page_size[1])
        page_filename = f"page-{str(page_index + 1).zfill(4)}.jpg"
        image_path = task_output_dir / "pages" / page_filename
        if not image_path.exists():
            logger.warning(f"Could not find image for page {page_index + 1} at expected path: {image_path}"); continue
        relative_image_path = Path('data') / 'mineru_output' / unique_folder_name / 'pages' / page_filename
        image_url = f"/data/local-files/?d={relative_image_path.as_posix()}"
        task = {"data": {"image": image_url}, "predictions": [{"result": []}]}
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


class UploadToLabelStudioView(APIView):
    """
    手动触发上传任务到 Label Studio
    """
    def post(self, request, pk, *args, **kwargs):
        logger.info(f"--- [POST] 手动触发上传到 Label Studio，文档ID: {pk} ---")
        try:
            doc = OcrDocument.objects.get(pk=pk)
            
            if not doc.raw_ocr_json:
                return Response(
                    {"error": "未找到原始OCR JSON，无法生成Label Studio任务"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not doc.mineru_json_path:
                return Response(
                    {"error": "文档处理未完成"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 获取 unique_folder_name
            json_path = Path(doc.mineru_json_path)
            unique_folder_name = json_path.parents[2].name
            
            # 生成 Label Studio 任务
            ls_tasks = _generate_ls_tasks(doc.raw_ocr_json, doc, unique_folder_name)
            
            if not ls_tasks:
                return Response(
                    {"error": "无法生成Label Studio任务"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # 上传到 Label Studio
            from .tasks import upload_to_label_studio
            success = upload_to_label_studio(doc.id, ls_tasks)
            
            if success:
                return Response({
                    "message": f"成功上传 {len(ls_tasks)} 个任务到 Label Studio",
                    "task_count": len(ls_tasks)
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "上传到 Label Studio 失败，请检查配置和日志"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
        except OcrDocument.DoesNotExist:
            return Response({"error": "文档未找到"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"手动上传到Label Studio时出错，文档ID {pk}: {e}", exc_info=True)
            return Response(
                {"error": f"发生意外错误: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
