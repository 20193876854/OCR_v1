"""
调试脚本：检查推送到 Label Studio 的任务数据结构
"""
import os
import sys
import django

# 设置 Django 环境
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.models import OcrDocument
from api.views import _generate_ls_tasks
import json

def check_task_generation():
    """检查任务生成逻辑"""
    print("=" * 80)
    print("Label Studio 任务数据诊断")
    print("=" * 80)
    
    # 获取最近的文档
    docs = OcrDocument.objects.filter(status='processed').order_by('-created_at')[:3]
    
    if not docs:
        print("❌ 没有找到已处理的文档")
        return
    
    for doc in docs:
        print(f"\n文档 ID: {doc.id}")
        print(f"文件名: {doc.original_pdf_path}")
        print(f"状态: {doc.status}")
        print(f"Label Studio 同步: {doc.label_studio_synced}")
        print(f"任务 IDs: {doc.label_studio_task_ids}")
        print("-" * 80)
        
        # 检查原始 OCR JSON
        if not doc.raw_ocr_json:
            print("❌ raw_ocr_json 为空")
            continue
        
        ocr_data = doc.raw_ocr_json
        pdf_info = ocr_data.get('pdf_info', [])
        print(f"✅ PDF 信息: {len(pdf_info)} 页")
        
        if not pdf_info:
            print("❌ pdf_info 为空")
            continue
        
        # 检查第一页的数据结构
        first_page = pdf_info[0]
        print(f"\n第一页数据结构:")
        print(f"  - page_idx: {first_page.get('page_idx')}")
        print(f"  - page_size: {first_page.get('page_size')}")
        print(f"  - para_blocks: {len(first_page.get('para_blocks', []))} 个")
        print(f"  - preproc_blocks: {len(first_page.get('preproc_blocks', []))} 个")
        
        # 检查 blocks 内容
        all_blocks = first_page.get('para_blocks', []) + first_page.get('preproc_blocks', [])
        if all_blocks:
            print(f"\n示例 block:")
            sample_block = all_blocks[0]
            print(f"  - type: {sample_block.get('type')}")
            print(f"  - bbox: {sample_block.get('bbox')}")
            print(f"  - lines: {len(sample_block.get('lines', []))} 行")
            if sample_block.get('lines'):
                sample_line = sample_block['lines'][0]
                print(f"  - 第一行 bbox: {sample_line.get('bbox')}")
                print(f"  - 第一行 spans: {len(sample_line.get('spans', []))} 个")
                if sample_line.get('spans'):
                    sample_span = sample_line['spans'][0]
                    print(f"  - 第一个 span content: {sample_span.get('content', '')[:50]}...")
        
        # 尝试生成任务
        try:
            # 从 mineru_json_path 获取唯一文件夹名
            mineru_path = doc.mineru_json_path
            if mineru_path:
                import re
                match = re.search(r'mineru_output[/\\]([^/\\]+)', mineru_path)
                if match:
                    unique_folder_name = match.group(1)
                else:
                    print("❌ 无法从路径提取文件夹名")
                    continue
            else:
                print("❌ mineru_json_path 为空")
                continue
            
            print(f"\n生成任务数据 (folder: {unique_folder_name})...")
            tasks_data = _generate_ls_tasks(ocr_data, doc, unique_folder_name)
            
            print(f"✅ 生成了 {len(tasks_data)} 个任务")
            
            if tasks_data:
                # 检查第一个任务的结构
                first_task = tasks_data[0]
                print(f"\n第一个任务数据结构:")
                print(f"  - data.image: {first_task['data']['image']}")
                print(f"  - data.page_num: {first_task['data']['page_num']}")
                print(f"  - predictions 数量: {len(first_task['predictions'])}")
                
                if first_task['predictions']:
                    first_pred = first_task['predictions'][0]
                    result_count = len(first_pred.get('result', []))
                    print(f"  - predictions[0].result 数量: {result_count}")
                    
                    if result_count > 0:
                        print(f"\n✅ 预标注数据存在！")
                        # 显示前3个标注
                        for i, item in enumerate(first_pred['result'][:3]):
                            print(f"\n  标注 {i+1}:")
                            print(f"    - from_name: {item.get('from_name')}")
                            print(f"    - type: {item.get('type')}")
                            if item.get('type') == 'rectanglelabels':
                                print(f"    - labels: {item.get('value', {}).get('rectanglelabels')}")
                                print(f"    - bbox: x={item['value']['x']:.1f}, y={item['value']['y']:.1f}, w={item['value']['width']:.1f}, h={item['value']['height']:.1f}")
                            elif item.get('type') == 'textarea':
                                text = item.get('value', {}).get('text', [''])[0]
                                print(f"    - text: {text[:50]}...")
                    else:
                        print(f"\n❌ predictions[0].result 为空！没有生成预标注")
                else:
                    print(f"\n❌ predictions 为空")
                
                # 保存示例任务到文件
                sample_file = f"/tmp/label_studio_task_sample_doc_{doc.id}.json"
                with open(sample_file, 'w', encoding='utf-8') as f:
                    json.dump(first_task, f, indent=2, ensure_ascii=False)
                print(f"\n💾 示例任务已保存到: {sample_file}")
                
        except Exception as e:
            print(f"❌ 生成任务失败: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 80)

if __name__ == '__main__':
    check_task_generation()
