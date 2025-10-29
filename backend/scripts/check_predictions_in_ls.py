"""
直接检查 Label Studio 中的任务是否包含预标注
"""
import os
import sys
import django

# 设置 Django 环境
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.label_studio_utils import LabelStudioClient
import requests
import json

def check_predictions_in_label_studio():
    """检查 Label Studio 中任务的预标注"""
    print("=" * 80)
    print("检查 Label Studio 中任务的预标注")
    print("=" * 80)
    
    ls_client = LabelStudioClient()
    if not ls_client.is_configured():
        print("❌ Label Studio 未配置")
        return
    
    headers = ls_client._get_headers()
    if not headers:
        print("❌ 无法获取认证头")
        return
    
    # 获取任务列表
    url = f"{ls_client.base_url}/api/projects/{ls_client.project_id}/tasks"
    params = {
        'page_size': 5,
        'ordering': '-id'  # 最新的任务
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        tasks = data.get('tasks', []) if isinstance(data, dict) else data
        
        print(f"\n✅ 找到 {len(tasks)} 个任务\n")
        
        for i, task in enumerate(tasks, 1):
            task_id = task.get('id')
            print(f"任务 {i} (ID: {task_id})")
            print(f"  - 创建时间: {task.get('created_at', 'N/A')[:19]}")
            
            # 检查 data
            data_obj = task.get('data', {})
            print(f"  - 图片: {data_obj.get('image', 'N/A')}")
            print(f"  - 页码: {data_obj.get('page_num', 'N/A')}/{data_obj.get('total_pages', 'N/A')}")
            
            # 检查 predictions (预标注)
            predictions = task.get('predictions', [])
            print(f"  - Predictions 数量: {len(predictions)}")
            
            if predictions:
                for j, pred in enumerate(predictions):
                    result = pred.get('result', [])
                    print(f"    Prediction {j+1}:")
                    print(f"      - result 项数: {len(result)}")
                    print(f"      - model_version: {pred.get('model_version', 'N/A')}")
                    
                    # 统计类型
                    rect_count = sum(1 for r in result if r.get('type') == 'rectanglelabels')
                    text_count = sum(1 for r in result if r.get('type') == 'textarea')
                    print(f"      - 矩形框: {rect_count}, 文本: {text_count}")
                    
                    if result:
                        print(f"      ✅ 包含预标注数据！")
                        # 显示第一个标注
                        first = result[0]
                        if first.get('type') == 'rectanglelabels':
                            labels = first.get('value', {}).get('rectanglelabels', [])
                            print(f"      示例: {labels}")
                    else:
                        print(f"      ❌ result 为空")
            else:
                print(f"    ❌ 没有 predictions")
            
            # 检查 annotations (人工标注)
            annotations = task.get('annotations', [])
            print(f"  - Annotations 数量: {len(annotations)}")
            
            print()
        
        # 总结
        total_predictions = sum(len(task.get('predictions', [])) for task in tasks)
        tasks_with_predictions = sum(1 for task in tasks if task.get('predictions'))
        
        print("=" * 80)
        print(f"总结:")
        print(f"  - 检查任务数: {len(tasks)}")
        print(f"  - 包含预标注的任务: {tasks_with_predictions}")
        print(f"  - 总预标注数: {total_predictions}")
        
        if tasks_with_predictions == 0:
            print("\n❌ 所有任务都没有预标注！")
            print("\n可能原因:")
            print("1. 推送时 predictions 数据丢失")
            print("2. Label Studio API 没有正确处理 predictions")
            print("3. 需要检查推送的 JSON 格式")
        else:
            print(f"\n✅ 成功！{tasks_with_predictions}/{len(tasks)} 个任务包含预标注")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_predictions_in_label_studio()
