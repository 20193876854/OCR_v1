#!/usr/bin/env python3
"""
检查 Label Studio 中指定任务的图片 URL
"""
import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.label_studio_utils import LabelStudioClient

def check_task_url(task_id):
    """检查指定任务的图片 URL"""
    ls_client = LabelStudioClient()
    
    task = ls_client.get_task(task_id)
    if task:
        print(f"\n任务 #{task_id} 的详细信息:")
        print(f"  图片 URL: {task.get('data', {}).get('image', 'N/A')}")
        print(f"  predictions 数量: {len(task.get('predictions', []))}")
    else:
        print(f"\n任务 #{task_id} 不存在")

if __name__ == '__main__':
    # 检查几个常见的任务
    for task_id in [1, 5, 10, 29]:
        check_task_url(task_id)
