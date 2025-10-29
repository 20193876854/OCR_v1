#!/usr/bin/env python3
"""
更新 Label Studio 项目配置
"""
import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.label_studio_utils import LabelStudioClient

def update_project_config():
    """更新项目配置"""
    ls_client = LabelStudioClient()
    
    # 读取新的 XML 配置
    xml_config = '''<View>
  <Style>
    .lsf-main-content.lsf-requesting .lsf-htx-img { opacity: 0.5; }
    [data-label^="Figure"] { border: 2px solid #9370DB !important; }
    [data-label^="Table"] { border: 2px solid #FF6347 !important; }
    [data-label^="Formula"] { border: 2px solid #32CD32 !important; }
  </Style>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="true"/>
  <Header value="Recognized Content"/>
  
  <RectangleLabels name="bbox" toName="image">
    <Label value="Para" background="#00FF00" />
    <Label value="Title" background="#FFA500" />
    <Label value="List" background="#87CEEB" />
    <Label value="Table" background="#FF6347" />
    <Label value="Figure" background="#9370DB" />
    <Label value="Footer" background="#C0C0C0" />
    <Label value="Header" background="#C0C0C0" />
    <Label value="Formula" background="#32CD32" />
    <Label value="Unknown" background="#F08080" />
  </RectangleLabels>
  
  <TextArea name="transcription" toName="image" editable="true" perRegion="true" required="false" rows="1" placeholder="Recognized text" displayMode="region-list"/>
</View>'''
    
    # 更新项目配置
    headers = ls_client._get_headers()
    url = f"{ls_client.base_url}/api/projects/{ls_client.project_id}"
    
    import requests
    response = requests.patch(
        url,
        json={"label_config": xml_config},
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        print("✓ Label Studio 项目配置已更新")
        print(f"  项目 ID: {ls_client.project_id}")
        print(f"  配置包含标签: Para, Title, List, Table, Figure, Footer, Header, Formula, Unknown")
    else:
        print(f"✗ 更新失败: {response.status_code}")
        print(f"  响应: {response.text}")

if __name__ == '__main__':
    update_project_config()
