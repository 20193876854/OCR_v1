#!/usr/bin/env python3
"""
测试 ingest-to-ragflow 端点
模拟从 Label Studio 导出的校对数据
"""
import requests
import json

def test_ingest():
    """测试上传校对数据"""
    doc_id = 4
    
    # 模拟 Label Studio 导出的数据格式
    corrected_data = [
        {
            "id": 1,
            "data": {
                "image": "http://localhost:8010/api/images/test/page-0001.jpg",
                "page_num": 1
            },
            "annotations": [
                {
                    "result": [
                        {
                            "type": "rectanglelabels",
                            "value": {
                                "x": 10,
                                "y": 10,
                                "width": 80,
                                "height": 5,
                                "rectanglelabels": ["Para"]
                            },
                            "from_name": "bbox",
                            "to_name": "image"
                        },
                        {
                            "type": "textarea",
                            "value": {
                                "text": ["这是第一页的测试文本内容。"]
                            },
                            "from_name": "transcription",
                            "to_name": "image"
                        }
                    ]
                }
            ]
        },
        {
            "id": 2,
            "data": {
                "image": "http://localhost:8010/api/images/test/page-0002.jpg",
                "page_num": 2
            },
            "annotations": [
                {
                    "result": [
                        {
                            "type": "textarea",
                            "value": {
                                "text": ["这是第二页的测试文本内容。"]
                            },
                            "from_name": "transcription",
                            "to_name": "image"
                        }
                    ]
                }
            ]
        }
    ]
    
    # 发送 POST 请求
    url = f"http://localhost:8010/api/documents/{doc_id}/ingest-to-ragflow/"
    
    print(f"测试端点: {url}")
    print(f"发送 {len(corrected_data)} 个任务的数据...\n")
    
    try:
        response = requests.post(
            url,
            json=corrected_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n✓ 成功!")
            print(f"  消息: {data.get('message')}")
            print(f"  生成的块数: {data.get('chunks_count')}")
            
            if 'ragflow_payload' in data:
                payload = data['ragflow_payload']
                print(f"\nRAGFlow Payload:")
                print(f"  doc_id: {payload.get('doc_id')}")
                print(f"  kb_name: {payload.get('kb_name')}")
                print(f"  chunks: {len(payload.get('chunks', []))} 个")
                
                if payload.get('chunks'):
                    print(f"\n  第一个块的内容:")
                    print(f"    {payload['chunks'][0].get('content_ltxt')[:100]}...")
        else:
            print(f"\n✗ 失败")
            print(f"  错误: {response.text}")
            
    except Exception as e:
        print(f"\n✗ 请求失败: {e}")

if __name__ == '__main__':
    test_ingest()
