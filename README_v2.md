# OCR-RAG 文档处理流水线 v2.0

基于 [MinerU](https://github.com/opendatalab/MinerU) 的智能文档 OCR 处理系统，集成了自动化识别、人工校对和 RAG 格式导出的完整流水线。

## 🎯 核心特性

### ✨ v2.0 新增功能

- **🚀 优化的 Docker 镜像构建**：模型文件打包到镜像中，利用缓存机制加快构建速度
- **🤖 自动化工作流**：OCR 识别完成后可自动导入 Label Studio，无需手动操作
- **🌐 灵活的部署配置**：通过环境变量和反向代理配置，无需修改代码即可部署到任何服务器
- **⚡ GPU 加速支持**：完整的 CUDA 支持，处理速度提升 3-4 倍

### 📋 基础功能

* **📄 PDF 上传**：通过 Web 界面批量上传 PDF 文档
* **🔍 自动化 OCR**：使用 MinerU 引擎，支持复杂版面分析
* **💾 数据持久化**：PostgreSQL 存储所有文档和处理结果
* **✏️ 人工校对**：Label Studio 集成，支持可视化标注和文本修正
* **📦 RAG 格式导出**：一键转换为 RAGFlow 兼容格式
* **🐳 完整容器化**：所有服务统一管理，一键启动

## 🏗️ 系统架构

```
用户访问 (端口 80)
    ↓
Nginx 反向代理 (统一入口)
    ├─→ / (前端 Vue.js)
    ├─→ /api/ (后端 Django)
    └─→ /label-studio/ (Label Studio)
         ↓
    Celery Worker (GPU 加速)
         ↓
    PostgreSQL + Redis
```

## 🚀 快速开始

### 前置要求

- Docker >= 19.03
- Docker Compose >= 1.27
- （可选）NVIDIA GPU + nvidia-docker（启用 GPU 加速）

### 基础安装

**1. 克隆项目**
```bash
git clone https://github.com/your-repo/OCR_v1.git
cd OCR_v1
```

**2. 配置环境变量**
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
nano .env
```

关键配置项：
```bash
# Label Studio 配置
LABEL_STUDIO_API_TOKEN=your_token_here  # 必须配置！
LABEL_STUDIO_PROJECT_ID=1
AUTO_IMPORT_TO_LABEL_STUDIO=true  # 启用自动导入

# GPU 配置（可选）
CUDA_VISIBLE_DEVICES=0
```

**3. 获取 Label Studio API Token**
```bash
# 启动服务
docker-compose up -d label-studio

# 访问 http://localhost/label-studio/
# 1. 注册/登录账号
# 2. 进入 Account & Settings
# 3. 复制 Access Token
# 4. 将 Token 填入 .env 文件
```

**4. 启动所有服务**
```bash
# 构建并启动
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f celery  # 查看 OCR 处理日志
```

**5. 访问服务**
- 前端界面：http://localhost/
- Label Studio：http://localhost/label-studio/
- 后端 API：http://localhost/api/

## ⚡ GPU 加速配置

GPU 加速可将处理速度提升 3-4 倍。详细配置请参考 [GPU_SETUP.md](GPU_SETUP.md)

**快速启用**：
```bash
# 1. 安装 nvidia-docker
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# 2. 验证 GPU 支持
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# 3. 配置环境变量
echo "CUDA_VISIBLE_DEVICES=0" >> .env

# 4. 重启服务
docker-compose up -d --build

# 5. 验证 GPU 使用
docker-compose logs celery | grep "GPU可用"
# 应该看到：✓ GPU可用: 1 个设备, 主设备: NVIDIA ...
```

## 📖 使用指南

### 工作流程

```
上传PDF → OCR处理 → 自动/手动导入Label Studio → 人工校对 → 导出结果 → RAG格式
```

### 详细步骤

#### 1️⃣ 上传 PDF 文档
- 访问前端界面：http://localhost/
- 点击"上传文档"按钮
- 选择一个或多个 PDF 文件
- 文档状态显示为 `pending`

#### 2️⃣ OCR 自动处理
- 系统自动触发 Celery 异步任务
- 文档状态变更为 `processing`
- 处理时间（10页PDF）：
  - GPU 模式：约 15-30 秒
  - CPU 模式：约 60-90 秒
- 完成后状态变为 `processed`

#### 3️⃣ Label Studio 校对

**方式一：自动导入（推荐）✨**
```bash
# 确保 .env 中配置了
AUTO_IMPORT_TO_LABEL_STUDIO=true
LABEL_STUDIO_API_TOKEN=your_token
LABEL_STUDIO_PROJECT_ID=1
```
- OCR 完成后自动导入 Label Studio
- 直接访问 Label Studio 进行标注
- 无需手动下载/上传 JSON

**方式二：手动导入**
- 在前端下载"原始 OCR JSON"
- 在 Label Studio 中创建项目
- 导入 JSON 文件
- 进行可视化标注和文本修正

#### 4️⃣ 提交校对结果
- 在 Label Studio 完成校对后导出 JSON
- 在前端点击"上传校对后 JSON"
- 文档状态变为 `corrected`

#### 5️⃣ 生成 RAG 格式
- 点击"生成 RAG 文件"按钮
- 下载 RAGFlow 兼容的 JSON 文件
- 文档状态变为 `ingested`

## ⚙️ 配置说明

### 环境变量配置

完整配置项请参考 [.env.example](.env.example)

#### Label Studio 集成
```bash
# Label Studio 服务地址（Docker 内部）
LABEL_STUDIO_URL=http://label-studio:8081

# API Token（必需）
LABEL_STUDIO_API_TOKEN=your_api_token_here

# 项目 ID
LABEL_STUDIO_PROJECT_ID=1

# 自动导入开关
AUTO_IMPORT_TO_LABEL_STUDIO=true
```

#### GPU 配置
```bash
# 指定使用的 GPU（0,1 表示使用前两个GPU）
CUDA_VISIBLE_DEVICES=0

# NVIDIA Docker 配置
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_DRIVER_CAPABILITIES=compute,utility
```

#### 数据库配置
```bash
POSTGRES_NAME=ocr_pipeline_db
POSTGRES_USER=test
POSTGRES_PASSWORD=test1234
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

### 部署配置

详细部署指南请参考 [DEPLOYMENT.md](DEPLOYMENT.md)

#### 使用域名部署

修改 `nginx/nginx.conf`：
```nginx
server {
    listen 80;
    server_name your-domain.com;  # 修改为你的域名
    # ... 其他配置
}
```

#### 修改端口

修改 `docker-compose.yml`：
```yaml
nginx:
  ports:
    - "8080:80"  # 将 80 改为 8080
```

## 🔧 开发指南

### 项目结构

```
OCR_v1/
├── backend/              # Django 后端
│   ├── api/             # API 应用
│   │   ├── models.py    # 数据模型
│   │   ├── views.py     # API 视图
│   │   ├── tasks.py     # Celery 任务
│   │   └── serializers.py
│   ├── dockerfile       # 后端 Dockerfile（含 GPU 支持）
│   ├── requirements.txt # Python 依赖
│   └── download_models.py  # 模型预下载脚本
├── frontend/            # Vue.js 前端
│   ├── src/
│   └── public/
├── nginx/               # Nginx 反向代理
│   ├── Dockerfile
│   └── nginx.conf       # 路由配置
├── data/                # 数据存储目录
│   ├── pdfs_to_process/ # 上传的 PDF
│   ├── mineru_output/   # OCR 输出
│   └── label_studio.sqlite3
├── docker-compose.yml   # Docker 编排配置
├── .env.example         # 环境变量模板
└── README.md           # 本文件
```

### 本地开发

```bash
# 后端开发
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver

# 前端开发
cd frontend
npm install
npm run serve

# Celery 任务开发
celery -A backend worker -l info
```

### API 文档

主要 API 端点：

- `POST /api/upload/` - 上传 PDF
- `GET /api/documents/` - 获取文档列表
- `GET /api/documents/{id}/` - 获取文档详情
- `POST /api/documents/{id}/generate-ls-json/` - 生成 Label Studio JSON
- `POST /api/documents/batch-import-ls/` - 批量导入到 Label Studio
- `POST /api/documents/{id}/submit-correction/` - 提交校对结果
- `GET /api/documents/{id}/generate-ragflow/` - 生成 RAG 格式

## 🐛 故障排查

### 常见问题

#### 1. 服务无法启动

```bash
# 查看所有服务状态
docker-compose ps

# 查看详细日志
docker-compose logs <service-name>

# 重新构建
docker-compose down
docker-compose up -d --build
```

#### 2. OCR 处理失败

```bash
# 查看 Celery 日志
docker-compose logs -f celery

# 检查数据目录权限
ls -la data/

# 重启 Celery
docker-compose restart celery
```

#### 3. Label Studio 无法加载图片

检查以下配置：
- Nginx `/data/` 路径配置正确
- 图片路径使用 `/data/local-files/?d=...` 格式
- `docker-compose.yml` 中挂载了 `./data:/data`

#### 4. GPU 不可用

```bash
# 检查 nvidia-smi
nvidia-smi

# 检查容器内 GPU
docker exec -it ocr_celery_worker nvidia-smi

# 检查 PyTorch CUDA
docker exec -it ocr_celery_worker python -c "import torch; print(torch.cuda.is_available())"

# 重新构建镜像
docker-compose build --no-cache celery
```

### 性能优化

#### 调整 Celery 并发数

修改 `docker-compose.yml`：
```yaml
celery:
  command: celery -A backend worker -l info --concurrency=4
```

#### 优化 Docker 构建速度

```bash
# 使用 BuildKit 加速构建
export DOCKER_BUILDKIT=1
docker-compose build

# 清理未使用的镜像
docker system prune -a
```

## 📚 相关文档

- [GPU_SETUP.md](GPU_SETUP.md) - GPU 加速详细配置指南
- [DEPLOYMENT.md](DEPLOYMENT.md) - 生产环境部署指南
- [.env.example](.env.example) - 完整环境变量配置
- [MinerU GitHub](https://github.com/opendatalab/MinerU) - OCR 引擎文档

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

- [MinerU](https://github.com/opendatalab/MinerU) - 优秀的 OCR 引擎
- [Label Studio](https://labelstud.io/) - 数据标注工具
- [Django](https://www.djangoproject.com/) - Web 框架
- [Vue.js](https://vuejs.org/) - 前端框架

---

**更新日志**

- **v2.0** (2025-10-25)
  - ✨ 新增自动导入 Label Studio 功能
  - 🚀 优化 Docker 镜像构建和模型缓存
  - ⚡ 完善 GPU 加速支持
  - 🌐 改进部署配置，支持环境变量
  
- **v1.0** (2024-09)
  - 🎉 初始版本发布
  - 📄 支持 PDF OCR 识别
  - ✏️ 集成 Label Studio 人工校对
  - 📦 支持 RAG 格式导出
