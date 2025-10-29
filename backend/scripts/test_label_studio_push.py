"""
测试 Label Studio API 推送
"""
import os
import sys
import django
import requests
import json

# 设置 Django 环境
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.models import OcrDocument
from api.views import _generate_ls_tasks
from api.label_studio_utils import LabelStudioClient

def test_label_studio_push():
    """测试推送到 Label Studio"""
    print("=" * 80)
    print("Label Studio API 推送测试")
    print("=" * 80)
    
    # 获取配置
    ls_url = os.getenv('LABEL_STUDIO_URL', '')
    ls_api_key = os.getenv('LABEL_STUDIO_API_KEY', '')
    ls_project_id = os.getenv('LABEL_STUDIO_PROJECT_ID', '1')
    backend_url = os.getenv('BACKEND_EXTERNAL_URL', 'http://localhost:8010')
    
    print(f"\n配置信息:")
    print(f"  LABEL_STUDIO_URL: {ls_url}")
    print(f"  LABEL_STUDIO_API_KEY: {ls_api_key[:20]}..." if ls_api_key else "  LABEL_STUDIO_API_KEY: (未设置)")
    print(f"  LABEL_STUDIO_PROJECT_ID: {ls_project_id}")
    print(f"  BACKEND_EXTERNAL_URL: {backend_url}")
    
    if not ls_api_key:
        print("\n❌ LABEL_STUDIO_API_KEY 未设置")
        return
    
    # 获取文档
    doc = OcrDocument.objects.filter(status='processed').order_by('-created_at').first()
    if not doc:
        print("\n❌ 没有找到已处理的文档")
        return
    
    print(f"\n使用文档 ID: {doc.id}")
    print(f"文件名: {doc.original_pdf_path}")
    
    # 生成任务数据（只生成1个任务用于测试）
    try:
        ocr_data = doc.raw_ocr_json
        import re
        match = re.search(r'mineru_output[/\\]([^/\\]+)', doc.mineru_json_path)
        if not match:
            print("❌ 无法提取文件夹名")
            return
        unique_folder_name = match.group(1)
        
        tasks_data = _generate_ls_tasks(ocr_data, doc, unique_folder_name)
        if not tasks_data:
            print("❌ 没有生成任务数据")
            return
        
        # 只取第一个任务
        test_task = tasks_data[0]
        print(f"\n✅ 生成了测试任务")
        print(f"  - 图片 URL: {test_task['data']['image']}")
        print(f"  - 预标注数量: {len(test_task['predictions'][0]['result'])}")
        
    except Exception as e:
        print(f"❌ 生成任务失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 测试 API 推送
    print(f"\n" + "=" * 80)
    print("测试推送单个任务到 Label Studio")
    print("=" * 80)
    
    ls_client = LabelStudioClient()
    
    # 方法1: 使用 import API（批量）
    print(f"\n方法1: 使用 /api/projects/{ls_project_id}/import")
    url = f"{ls_url}/api/projects/{ls_project_id}/import"
    headers = ls_client._get_headers()
    
    try:
        response = requests.post(
            url,
            json=[test_task],  # 注意：必须是数组
            headers=headers,
            timeout=30
        )
        print(f"  状态码: {response.status_code}")
        print(f"  响应内容:")
        result = response.json()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if response.status_code == 201:
            print("\n✅ 推送成功!")
            task_ids = result.get('task_ids', [])
            print(f"  创建的任务 IDs: {task_ids}")
            
            # 检查第一个任务的详情
            if task_ids:
                task_id = task_ids[0]
                print(f"\n检查任务 {task_id} 的详情...")
                task_url = f"{ls_url}/api/tasks/{task_id}"
                task_response = requests.get(task_url, headers=headers, timeout=10)
                task_detail = task_response.json()
                
                print(f"  任务 ID: {task_detail.get('id')}")
                print(f"  Predictions 数量: {len(task_detail.get('predictions', []))}")
                if task_detail.get('predictions'):
                    pred = task_detail['predictions'][0]
                    print(f"  第一个 Prediction:")
                    print(f"    - result 数量: {len(pred.get('result', []))}")
                    print(f"    - model_version: {pred.get('model_version')}")
                else:
                    print("  ⚠️  没有 predictions!")
        else:
            print(f"\n❌ 推送失败")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_label_studio_push()
