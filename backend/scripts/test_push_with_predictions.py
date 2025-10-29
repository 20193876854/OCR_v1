#!/usr/bin/env python3
"""
测试推送文档到 Label Studio（包含预标注）
"""
import os
import sys
import django
import requests

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.models import OcrDocument
from api.label_studio_utils import LabelStudioClient

def test_push(doc_id):
    """测试推送指定文档"""
    try:
        doc = OcrDocument.objects.get(id=doc_id)
        print(f"\n文档 #{doc_id}:")
        print(f"  状态: {doc.status}")
        print(f"  JSON 路径: {doc.mineru_json_path}")
        print(f"  已推送: {doc.label_studio_synced}")
        
        # 调用后端 API 推送
        url = f"http://localhost:8010/api/documents/{doc_id}/push-to-labelstudio/"
        response = requests.post(url, json={"force": True}, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ 推送成功!")
            print(f"  任务数: {data.get('task_count')}")
            print(f"  任务 IDs: {data.get('task_ids')[:5]}...")
            
            # 检查第一个任务的预标注
            ls_client = LabelStudioClient()
            if data.get('task_ids'):
                first_task_id = data['task_ids'][0]
                task = ls_client.get_task(first_task_id)
                if task:
                    predictions = task.get('predictions', [])
                    print(f"\n  任务 #{first_task_id} 预标注检查:")
                    print(f"    predictions 数量: {len(predictions)}")
                    if predictions:
                        result = predictions[0].get('result', [])
                        print(f"    result 项数: {len(result)}")
                        if result:
                            print(f"    第一个标注: {result[0]}")
        else:
            print(f"\n✗ 推送失败: {response.status_code}")
            print(f"  错误: {response.text}")
            
    except OcrDocument.DoesNotExist:
        print(f"\n✗ 文档 #{doc_id} 不存在")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # 找到第一个已处理的文档
    doc = OcrDocument.objects.filter(status='processed').first()
    if doc:
        print(f"测试文档 ID: {doc.id}")
        test_push(doc.id)
    else:
        print("没有找到已处理的文档")
