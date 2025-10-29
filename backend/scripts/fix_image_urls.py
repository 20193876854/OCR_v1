#!/usr/bin/env python3
"""
修复 Label Studio 中的图片 URL
将 host.docker.internal 替换为 localhost
"""
import os
import sys
import django

# 设置 Django 环境
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.label_studio_utils import LabelStudioClient
from api.models import OcrDocument
import json

def fix_image_urls():
    """修复所有任务的图片 URL"""
    ls_client = LabelStudioClient()
    
    # 获取项目中的所有任务
    tasks = ls_client.get_tasks()
    print(f"找到 {len(tasks)} 个任务")
    
    fixed_count = 0
    for task in tasks:
        task_id = task['id']
        data = task.get('data', {})
        
        # 检查并修复图片 URL
        if 'image' in data:
            old_url = data['image']
            if 'host.docker.internal' in old_url:
                # 替换为 localhost
                new_url = old_url.replace('host.docker.internal', 'localhost')
                
                print(f"\n任务 #{task_id}:")
                print(f"  旧 URL: {old_url}")
                print(f"  新 URL: {new_url}")
                
                # 更新任务
                try:
                    ls_client.update_task(task_id, {'data': {'image': new_url}})
                    print(f"  ✓ 已更新")
                    fixed_count += 1
                except Exception as e:
                    print(f"  ✗ 更新失败: {e}")
    
    print(f"\n总共修复了 {fixed_count} 个任务的图片 URL")

if __name__ == '__main__':
    fix_image_urls()
