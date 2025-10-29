#!/usr/bin/env python3
"""
Label Studio 预标注检查脚本
用于验证 OCR 任务是否正确推送并包含预标注
"""
import os
import requests
import json
from pprint import pprint

# 配置
LABEL_STUDIO_URL = os.getenv('LABEL_STUDIO_URL', 'http://localhost:8081')
LABEL_STUDIO_API_KEY = os.getenv('LABEL_STUDIO_API_KEY', '')
PROJECT_ID = os.getenv('LABEL_STUDIO_PROJECT_ID', '1')

def check_label_studio_config():
    """检查 Label Studio 配置"""
    print("=" * 60)
    print("检查 Label Studio 配置")
    print("=" * 60)
    
    if not LABEL_STUDIO_API_KEY:
        print("❌ LABEL_STUDIO_API_KEY 未设置")
        return False
    
    print(f"✅ LABEL_STUDIO_URL: {LABEL_STUDIO_URL}")
    print(f"✅ LABEL_STUDIO_API_KEY: {LABEL_STUDIO_API_KEY[:10]}...")
    print(f"✅ PROJECT_ID: {PROJECT_ID}")
    return True

def get_tasks():
    """获取项目中的任务列表"""
    print("\n" + "=" * 60)
    print("获取任务列表")
    print("=" * 60)
    
    headers = {
        'Authorization': f'Token {LABEL_STUDIO_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    url = f"{LABEL_STUDIO_URL}/api/projects/{PROJECT_ID}/tasks"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        tasks = response.json()
        
        print(f"✅ 找到 {len(tasks)} 个任务")
        return tasks
    except Exception as e:
        print(f"❌ 获取任务失败: {e}")
        return []

def check_task_predictions(task):
    """检查单个任务的预标注"""
    task_id = task.get('id')
    print(f"\n任务 ID: {task_id}")
    print("-" * 60)
    
    # 检查 data
    data = task.get('data', {})
    print(f"图片 URL: {data.get('image', 'N/A')}")
    print(f"文档 ID: {data.get('doc_id', 'N/A')}")
    print(f"页码: {data.get('page_num', 'N/A')} / {data.get('total_pages', 'N/A')}")
    
    # 检查 predictions
    predictions = task.get('predictions', [])
    if not predictions:
        print("⚠️  没有预标注 (predictions)")
        return False
    
    print(f"✅ 找到 {len(predictions)} 个预标注")
    
    for idx, pred in enumerate(predictions):
        result = pred.get('result', [])
        print(f"  预标注 {idx + 1}: 包含 {len(result)} 个标注项")
        
        # 统计标注类型
        rect_count = sum(1 for r in result if r.get('type') == 'rectanglelabels')
        text_count = sum(1 for r in result if r.get('type') == 'textarea')
        
        print(f"    - 矩形框: {rect_count}")
        print(f"    - 文本内容: {text_count}")
        
        # 显示前3个标注的详情
        for r in result[:3]:
            if r.get('type') == 'rectanglelabels':
                labels = r.get('value', {}).get('rectanglelabels', [])
                print(f"    示例: {r.get('from_name')} -> {labels}")
    
    return len(predictions) > 0

def main():
    """主函数"""
    if not check_label_studio_config():
        return
    
    tasks = get_tasks()
    if not tasks:
        print("\n⚠️  没有找到任何任务，请先运行 OCR 处理")
        return
    
    # 检查最近的3个任务
    print("\n" + "=" * 60)
    print("检查最近的任务")
    print("=" * 60)
    
    tasks_to_check = tasks[:3]
    has_predictions = 0
    
    for task in tasks_to_check:
        if check_task_predictions(task):
            has_predictions += 1
    
    print("\n" + "=" * 60)
    print("检查结果汇总")
    print("=" * 60)
    print(f"总任务数: {len(tasks)}")
    print(f"检查任务数: {len(tasks_to_check)}")
    print(f"包含预标注: {has_predictions}")
    
    if has_predictions == 0:
        print("\n❌ 所有任务都没有预标注！")
        print("\n可能的原因：")
        print("1. 标签名称不匹配（后端 vs Label Studio 配置）")
        print("2. 推送时出错（检查 Celery 日志）")
        print("3. BACKEND_EXTERNAL_URL 配置错误（图片无法访问）")
        print("\n建议操作：")
        print("1. 检查 docker compose logs celery")
        print("2. 验证 BACKEND_EXTERNAL_URL 可访问")
        print("3. 更新 Label Studio 配置为 label_studio_config_updated.xml")
        print("4. 重新推送任务：POST /api/documents/<id>/push-to-label-studio?force=true")
    else:
        print(f"\n✅ 成功！{has_predictions}/{len(tasks_to_check)} 个任务包含预标注")

if __name__ == '__main__':
    main()
