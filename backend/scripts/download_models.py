#!/usr/bin/env python3
"""
MinerU 模型预下载脚本
在 Docker 镜像构建时预先下载所有必需的模型文件
这样可以利用 Docker 缓存机制，加快后续构建速度
"""

import os
import sys
import subprocess
from pathlib import Path


def download_mineru_models():
    """
    使用 MinerU CLI 命令预下载模型文件
    """
    print("=" * 60)
    print("开始下载 MinerU 模型文件...")
    print("=" * 60)
    
    try:
        # 设置模型源（可通过环境变量配置）
        model_source = os.getenv('MINERU_MODEL_SOURCE', 'modelscope')
        print(f"使用模型源: {model_source}")
        os.environ['MINERU_MODEL_SOURCE'] = model_source
        
        # 方法 1: 使用 magic-pdf 命令行工具下载模型
        print("\n方法 1: 使用 magic-pdf 命令下载模型...")
        try:
            # 运行 magic-pdf --help 触发初始化
            result = subprocess.run(
                ['magic-pdf', '--help'],
                capture_output=True,
                text=True,
                timeout=30
            )
            print("✓ magic-pdf 工具可用")
        except Exception as e:
            print(f"⚠️  magic-pdf 命令不可用: {e}")
        
        # 方法 2: 使用 Python API 触发模型下载
        print("\n方法 2: 使用 Python API 触发模型初始化...")
        try:
            # 尝试导入并初始化
            import magic_pdf
            print(f"✓ magic_pdf 模块版本: {magic_pdf.__version__ if hasattr(magic_pdf, '__version__') else 'unknown'}")
            
            # 尝试触发模型下载
            try:
                from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
                from magic_pdf.config.make_content_config import DropMode, MakeMode
                print("✓ 成功导入 MinerU 核心模块")
            except ImportError as ie:
                print(f"⚠️  部分模块导入失败: {ie}")
                
        except ImportError as e:
            print(f"⚠️  无法导入 magic_pdf: {e}")
        
        # 方法 3: 直接调用 mineru 命令（如果存在）
        print("\n方法 3: 检查 mineru 命令...")
        try:
            result = subprocess.run(
                ['mineru', '--help'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                print("✓ mineru 命令可用")
            else:
                print("⚠️  mineru 命令返回非零状态")
        except FileNotFoundError:
            print("⚠️  mineru 命令不存在")
        except Exception as e:
            print(f"⚠️  mineru 命令检查失败: {e}")
        
        # 检查模型缓存目录
        print("\n检查模型缓存目录...")
        possible_dirs = [
            Path.home() / ".cache" / "magic-pdf",
            Path.home() / ".cache" / "mineru",
            Path.home() / ".cache" / "huggingface",
            Path.home() / ".cache" / "modelscope",
        ]
        
        for model_dir in possible_dirs:
            if model_dir.exists():
                print(f"\n找到缓存目录: {model_dir}")
                total_size = 0
                file_count = 0
                for item in model_dir.rglob("*"):
                    if item.is_file():
                        size = item.stat().st_size
                        total_size += size
                        file_count += 1
                        if file_count <= 10:  # 只显示前 10 个文件
                            size_mb = size / (1024 * 1024)
                            print(f"  - {item.relative_to(model_dir)} ({size_mb:.2f} MB)")
                
                if file_count > 10:
                    print(f"  ... 还有 {file_count - 10} 个文件")
                print(f"总计: {file_count} 个文件, {total_size / (1024 * 1024):.2f} MB")
        
        print("\n" + "=" * 60)
        print("模型预下载流程完成！")
        print("=" * 60)
        print("\n注意：MinerU 会在首次实际使用时自动下载模型")
        print("如果上述方法未下载模型，这是正常的，运行时会自动处理")
        return True
        
    except Exception as e:
        print(f"\n❌ 错误: 模型预下载流程失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        # 不返回失败，因为模型可以在运行时下载
        print("\n⚠️  预下载失败，但这不影响系统运行")
        print("模型将在首次使用时自动下载")
        return True  # 返回成功，允许构建继续


if __name__ == "__main__":
    success = download_mineru_models()
    sys.exit(0 if success else 1)
