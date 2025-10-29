#!/usr/bin/env python
"""测试 Label Studio 配置"""
import os
import django

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.conf import settings
from api.label_studio_utils import LabelStudioClient

print("=" * 60)
print("Label Studio 配置检查")
print("=" * 60)

print(f"\n1. 配置值:")
print(f"   LABEL_STUDIO_URL: {settings.LABEL_STUDIO_URL}")
print(f"   LABEL_STUDIO_API_KEY: {'已设置 (长度: ' + str(len(settings.LABEL_STUDIO_API_KEY)) + ')' if settings.LABEL_STUDIO_API_KEY else '未设置'}")
print(f"   LABEL_STUDIO_PROJECT_ID: {settings.LABEL_STUDIO_PROJECT_ID}")

print(f"\n2. 客户端初始化:")
ls_client = LabelStudioClient()
print(f"   is_configured(): {ls_client.is_configured()}")

if ls_client.is_configured():
    print(f"\n3. 连接测试:")
    success, message = ls_client.test_connection()
    print(f"   成功: {success}")
    print(f"   消息: {message}")
else:
    print(f"\n3. 连接测试: 跳过（配置不完整）")

print("\n" + "=" * 60)
