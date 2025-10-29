# api/models.py
from django.db import models

class OcrDocument(models.Model):
    """
    Represents a single document processing workflow.
    """
    original_pdf_path = models.CharField(max_length=1024)
    mineru_json_path = models.CharField(max_length=1024, blank=True, null=True)

    # FIX: 添加此字段以存储来自 MinerU 的原始 OCR JSON。
    # 这修复了 celery 任务中一个潜在的保存错误,并有助于调试。
    raw_ocr_json = models.JSONField(null=True, blank=True, verbose_name="原始OCR JSON")

    # NEW: 添加此字段以存储用户从 Label Studio 提交的、校对后的 JSON 数据。
    corrected_label_studio_json = models.JSONField(null=True, blank=True, verbose_name="校对后的JSON")

    # UPDATED: 状态选项已更新,增加了 'corrected'。
    status = models.CharField(max_length=50, default='pending')
    
    # NEW: 处理日志,用于实时显示 MinerU 处理进度
    processing_log = models.TextField(blank=True, default='', verbose_name="处理日志")
    
    # NEW: Label Studio 推送状态
    label_studio_synced = models.BooleanField(default=False, verbose_name="已推送到Label Studio")
    label_studio_task_ids = models.JSONField(null=True, blank=True, verbose_name="Label Studio任务ID列表")
    label_studio_sync_time = models.DateTimeField(null=True, blank=True, verbose_name="推送时间")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_pdf_path
