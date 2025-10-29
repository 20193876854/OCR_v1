#!/usr/bin/env python3
"""
详细检查任务的预标注数据
"""
import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.label_studio_utils import LabelStudioClient

def check_task_predictions(task_id):
    """检查任务的预标注详情"""
    ls_client = LabelStudioClient()
    task = ls_client.get_task(task_id)
    
    if not task:
        print(f"任务 #{task_id} 不存在")
        return
    
    print(f"\n{'='*60}")
    print(f"任务 #{task_id} 详细信息")
    print(f"{'='*60}")
    
    # 图片 URL
    image_url = task.get('data', {}).get('image', 'N/A')
    print(f"\n图片 URL: {image_url}")
    
    # Predictions
    predictions = task.get('predictions', [])
    print(f"\nPredictions 数量: {len(predictions)}")
    
    if predictions:
        for idx, pred in enumerate(predictions):
            result = pred.get('result', [])
            print(f"\nPrediction #{idx + 1}:")
            print(f"  result 项数: {len(result)}")
            
            # 统计各种标签类型
            label_counts = {}
            text_count = 0
            rect_count = 0
            
            for item in result:
                item_type = item.get('type')
                if item_type == 'rectanglelabels':
                    rect_count += 1
                    labels = item.get('value', {}).get('rectanglelabels', [])
                    for label in labels:
                        label_counts[label] = label_counts.get(label, 0) + 1
                elif item_type == 'textarea':
                    text_count += 1
            
            print(f"  矩形框数量: {rect_count}")
            print(f"  文本标注数量: {text_count}")
            print(f"\n  标签统计:")
            for label, count in sorted(label_counts.items()):
                print(f"    {label}: {count}")
            
            # 显示前 3 个标注示例
            if result:
                print(f"\n  前 3 个标注示例:")
                for i, item in enumerate(result[:3]):
                    print(f"\n    [{i+1}] 类型: {item.get('type')}")
                    if item.get('type') == 'rectanglelabels':
                        value = item.get('value', {})
                        print(f"        标签: {value.get('rectanglelabels')}")
                        print(f"        位置: x={value.get('x'):.1f}%, y={value.get('y'):.1f}%")
                        print(f"        大小: w={value.get('width'):.1f}%, h={value.get('height'):.1f}%")
                    elif item.get('type') == 'textarea':
                        text = item.get('value', {}).get('text', [])
                        print(f"        文本: {text[0][:50] if text else 'N/A'}...")

if __name__ == '__main__':
    # 检查最新的几个任务
    print("检查最新推送的任务...")
    for task_id in [72, 71, 36]:
        check_task_predictions(task_id)
