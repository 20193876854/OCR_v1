# GPU 加速配置指南

本项目使用 MinerU 进行 OCR 识别，支持 GPU 加速以显著提升处理速度。

## 前置要求

### 1. 硬件要求
- NVIDIA GPU（支持 CUDA 12.1+）
- 推荐显存：8GB 及以上

### 2. 软件要求
- NVIDIA 驱动（版本 >= 525.60）
- Docker（版本 >= 19.03）
- NVIDIA Container Toolkit（nvidia-docker）

## 安装步骤

### Step 1: 检查 NVIDIA 驱动

```bash
# 检查驱动版本
nvidia-smi

# 确认 CUDA 版本 >= 12.1
# 输出应类似于：
# +-----------------------------------------------------------------------------+
# | NVIDIA-SMI 525.xx.xx    Driver Version: 525.xx.xx    CUDA Version: 12.1   |
# +-----------------------------------------------------------------------------+
```

### Step 2: 安装 NVIDIA Container Toolkit

#### Ubuntu/Debian

```bash
# 配置仓库
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# 安装
sudo apt-get update
sudo apt-get install -y nvidia-docker2

# 重启 Docker 服务
sudo systemctl restart docker
```

#### CentOS/RHEL

```bash
# 配置仓库
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.repo | sudo tee /etc/yum.repos.d/nvidia-docker.repo

# 安装
sudo yum install -y nvidia-docker2

# 重启 Docker 服务
sudo systemctl restart docker
```

### Step 3: 验证 GPU 支持

```bash
# 测试 Docker 能否访问 GPU
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# 如果成功，应该能看到 GPU 信息
```

## 配置项目使用 GPU

### 1. 配置环境变量

编辑项目根目录的 `.env` 文件：

```bash
# 指定使用的 GPU 设备
# 单个GPU: CUDA_VISIBLE_DEVICES=0
# 多个GPU: CUDA_VISIBLE_DEVICES=0,1
CUDA_VISIBLE_DEVICES=0

# NVIDIA Docker 配置（通常保持默认）
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility
```

### 2. 确认 docker-compose.yml 配置

项目的 `docker-compose.yml` 已经配置好 GPU 支持（celery 服务）：

```yaml
celery:
  # ... 其他配置 ...
  environment:
    - CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
    - NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}
    - NVIDIA_DRIVER_CAPABILITIES=${NVIDIA_DRIVER_CAPABILITIES:-compute,utility}
    - TORCH_CUDA_ARCH_LIST=8.9+PTX
  
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all  # 使用所有GPU，或指定数量如 count: 1
            capabilities: [gpu]
```

### 3. 启动服务

```bash
# 构建并启动服务
docker-compose up -d --build

# 查看 Celery 日志，确认 GPU 被识别
docker-compose logs -f celery

# 应该能看到类似输出：
# ✓ GPU可用: 1 个设备, 主设备: NVIDIA GeForce RTX 3090
```

## 验证 GPU 加速

### 1. 查看 GPU 使用情况

在处理 PDF 时，打开新终端监控 GPU：

```bash
# 实时监控 GPU 使用
watch -n 1 nvidia-smi

# 或者在 Docker 容器内查看
docker exec -it ocr_celery_worker nvidia-smi
```

### 2. 性能对比

| 模式 | 处理速度（10页PDF） |
|------|-------------------|
| CPU  | 约 60-90 秒       |
| GPU  | 约 15-30 秒       |

*实际性能取决于 PDF 复杂度和 GPU 型号*

## 故障排查

### 问题 1: "nvidia-smi: command not found"

**原因**: NVIDIA 驱动未安装或未正确安装

**解决**:
```bash
# Ubuntu
sudo apt-get install nvidia-driver-525

# 重启系统
sudo reboot
```

### 问题 2: "could not select device driver with capabilities: [[gpu]]"

**原因**: nvidia-docker2 未安装或 Docker 未重启

**解决**:
```bash
# 重新安装 nvidia-docker2
sudo apt-get install --reinstall nvidia-docker2

# 重启 Docker
sudo systemctl restart docker

# 重启容器
docker-compose down
docker-compose up -d
```

### 问题 3: Celery 日志显示 "GPU不可用，将使用CPU模式"

**可能原因**:
1. 容器内无法访问 GPU
2. PyTorch 未正确安装 CUDA 支持

**解决**:
```bash
# 进入容器检查
docker exec -it ocr_celery_worker bash

# 检查 GPU 是否可见
nvidia-smi

# 检查 PyTorch CUDA 支持
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# 如果返回 False，重新构建镜像
docker-compose build --no-cache celery
docker-compose up -d
```

### 问题 4: CUDA 版本不匹配

**错误信息**: "CUDA driver version is insufficient for CUDA runtime version"

**原因**: Docker 镜像中的 CUDA 版本高于主机驱动支持的版本

**解决**: 
修改 `backend/dockerfile`，使用较低版本的 CUDA 基础镜像：

```dockerfile
# 从 CUDA 12.1 改为 CUDA 11.8
FROM nvcr.io/nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04
```

同时修改 PyTorch 安装命令：
```dockerfile
RUN pip install torch>=2.4.0 torchvision>=0.19.0 --index-url https://download.pytorch.org/whl/cu118
```

## GPU 优化建议

### 1. 批量处理

处理多个文档时，GPU 优势更明显：

```python
# 推荐：批量提交任务
for pdf_file in pdf_files:
    process_pdf_with_mineru.delay(doc_id)
```

### 2. 多 GPU 配置

如果有多个 GPU，可以在 `.env` 中配置：

```bash
# 使用 GPU 0 和 1
CUDA_VISIBLE_DEVICES=0,1
```

在 `docker-compose.yml` 中修改：

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 2  # 使用 2 个 GPU
          capabilities: [gpu]
```

### 3. 显存优化

如果遇到显存不足（OOM）错误，可以：

1. 限制单个 GPU 的使用：
```bash
CUDA_VISIBLE_DEVICES=0  # 只使用一个 GPU
```

2. 在代码中添加显存清理（`backend/api/tasks.py`）：
```python
import torch

def process_pdf_with_mineru(doc_id):
    # ... OCR 处理 ...
    
    # 处理完成后清理显存
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
```

## Windows 系统特殊说明

Windows 用户需要：

1. 安装 NVIDIA 驱动
2. 安装 Docker Desktop（版本 >= 3.0，支持 WSL2）
3. 启用 WSL2 中的 GPU 支持

```powershell
# 在 PowerShell 中测试
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

## 参考资料

- [NVIDIA Container Toolkit 官方文档](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- [Docker GPU 支持文档](https://docs.docker.com/config/containers/resource_constraints/#gpu)
- [MinerU GitHub](https://github.com/opendatalab/MinerU)
- [PyTorch CUDA 安装指南](https://pytorch.org/get-started/locally/)
