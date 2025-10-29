from django.urls import path
from .views import (
    DocumentListView, 
    DocumentDetailView, 
    DocumentUploadView, 
    LabelStudioTaskView,
    SubmitCorrectionView,
    GenerateRAGFlowPayloadView,
    IngestToRagflowView,  # 新增: 接收校对数据并转换为 RAGFlow 格式
    PushToLabelStudioView,  # 新增: 手动推送到 Label Studio
    ServeImageView  # 新增: 静态图片服务
)

urlpatterns = [
    path('documents/', DocumentListView.as_view(), name='document_list'),
    path('documents/upload/', DocumentUploadView.as_view(), name='document_upload'),
    path('documents/<int:pk>/', DocumentDetailView.as_view(), name='document_detail'),
    
    path('documents/<int:pk>/to-label-studio/', LabelStudioTaskView.as_view(), name='download_raw_ocr'),
    
    path('documents/<int:pk>/submit-correction/', SubmitCorrectionView.as_view(), name='submit_correction'),
    
    # 接收校对数据并转换为 RAGFlow 格式
    path('documents/<int:pk>/ingest-to-ragflow/', IngestToRagflowView.as_view(), name='ingest_to_ragflow'),

    # RAGFlow 转换和下载的端点
    path('documents/<int:pk>/to-ragflow/', GenerateRAGFlowPayloadView.as_view(), name='generate_ragflow_payload'),
    
    # 新增: 手动推送到 Label Studio
    path('documents/<int:pk>/push-to-labelstudio/', PushToLabelStudioView.as_view(), name='push_to_labelstudio'),
    
    # 新增: 静态图片服务 (为 Label Studio 提供图片访问)
    path('images/<str:document_id>/<str:filename>', ServeImageView.as_view(), name='serve_image'),
]
