# OCR-RAG 文档处理流水线

一个端到端的 OCR 文档处理与标注系统，集成 MinerU OCR 引擎、Django API、Celery 异步任务、Vue 前端与 Label Studio 人工校对，并支持导出 RAG（Retrieval-Augmented Generation）所需的数据格式。

## Overview
- **智能 OCR**：使用 MinerU 解析复杂排版，支持段落、列表、表格、标题等多种版块。
- **自动化流水线**：Celery 异步任务负责 PDF 处理、页面渲染与结果推送，后端统一存储与调度。
- **Label Studio 集成**：自动创建任务、预填 OCR 结果、支持实时图片访问和标注关系。
- **RAG 友好**：将校对后的内容转换为 RAGFlow 兼容格式，便于知识库入库。
- **容器化部署**：基于 Docker Compose，提供开发、测试、生产与 GPU 加速多种方案。
- **可观测性**：实时处理日志、详细的 Docker 日志、Celery 任务监控。

## Architecture
| 组件 | 说明 |
|------|------|
| Vue 前端 (`frontend`)| 上传 PDF、查看处理状态、下载/上传 JSON、生成 RAG 数据 |
| Django 后端 (`backend`) | 提供 REST API、管理数据库、暴露静态图片服务 |
| Celery Worker (`celery`) | 执行 MinerU OCR、页面渲染、Label Studio 推送 |
| PostgreSQL (`db`) | 存储文档、处理状态、日志、Label Studio 同步信息 |
| Redis (`redis`) | Celery 任务队列与缓存 |
| Label Studio (`label-studio`) | OCR 结果人工校对与再加工 |
| MinerU | OCR 引擎，通过 Celery worker 内的命令行调用 |

主要数据目录位于 `data/`，包含 OCR 输出、导出文件与 Label Studio 数据卷。

## Repository Layout
```
OCR_v1-dev/
 backend/                # Django 与 Celery 源码、Dockerfile、脚本
 frontend/               # Vue 应用、Nginx、多阶段 Docker 构建
 data/                   # OCR 输出、Label Studio 数据、导出文件
 docker-compose*.yml     # 多套部署方案（标准、开发、GPU、生产）
 start.ps1 / start.sh    # 一键启动脚本（Windows / Linux & macOS）
 prebuild.ps1 / prebuild.sh # 可选：预构建基础镜像脚本
 label_studio_config.xml # Label Studio 标注界面配置
 README.md               # 本文档（整合全部使用说明）
```

## Prerequisites
- Docker Engine 20.10+ / Docker Desktop 4.x+
- Docker Compose 1.28+（或内置 `docker compose`）
- 8 GB+ 内存，20 GB+ 磁盘空间（首次运行需下载模型）
- 可选 GPU：NVIDIA GPU、NVIDIA Driver、NVIDIA Container Toolkit

## Quick Start

### 命令行
```bash
# 首次拉取代码
git clone <repository-url>
cd OCR_v1-dev
cp .env.example .env

# CPU 模式（默认）
docker compose up -d --build

# GPU 模式
docker compose -f docker-compose.gpu.yml up -d --build
```

### 常用操作
```bash
# 查看服务状态
docker compose ps
# 查看日志
docker compose logs -f          # 所有服务
docker compose logs -f backend  # 指定服务
# 重启/停止
docker compose restart
docker compose down             # 保留卷
docker compose down -v          # 删除卷（慎用）
```

## Environment Variables
将 `.env.example` 复制为 `.env` 并根据环境调整。常用配置如下：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FRONTEND_PORT` | `8082` | 前端暴露端口 |
| `VUE_APP_API_BASE_URL` | `http://localhost:8010/api` | 前端访问后端的 API 地址 |
| `VUE_APP_LABEL_STUDIO_URL` | `http://localhost:8081` | 前端跳转 Label Studio 的地址 |
| `LABEL_STUDIO_PORT` | `8081` | Label Studio 暴露端口 |
| `LABEL_STUDIO_URL` | `http://label-studio:8080` | 后端/Worker 在容器网络中访问 Label Studio 的地址 |
| `LABEL_STUDIO_API_KEY` | _(必填)_ | Label Studio Personal Access Token（见下文） |
| `LABEL_STUDIO_PROJECT_ID` | `1` | Label Studio 项目 ID |
| `BACKEND_EXTERNAL_URL` | `http://host.docker.internal:8010` | Label Studio 回访后端静态图片的地址（支持 localhost 方式） |
| `MINERU_MODEL_SOURCE` | `modelscope` | MinerU 模型下载源，可选 `huggingface` |
| `CELERY_CONCURRENCY` | `2` | Celery worker 并发数 |
| `GPU_COUNT` / `GPU_DEVICE_IDS` | `1` / `0` | GPU 模式相关设置 |

> 如果部署在远程主机，`VUE_APP_API_BASE_URL` 需使用宿主机可访问的实际 IP。`BACKEND_EXTERNAL_URL` 已配置为 `host.docker.internal`，在 Windows/Mac Docker Desktop 上会自动解析为宿主机，无需修改。

## Deployment Modes
| 场景 | 配置文件 | 特性 | 访问端口 |
|------|----------|------|----------|
| 本地开发 | `docker-compose.dev.yml` | 代码挂载、Django/Vue 开发服务器、热重载；首次启动约 8-12 分钟 | 前端 `8080`, 后端 `8010`, Label Studio `8081` |
| GPU 加速 | `docker-compose.gpu.yml` | 自动挂载 GPU，需安装 `nvidia-docker` | 同上 |

## Processing Workflow
1. **上传 PDF**：前端创建 `OcrDocument` 记录并触发 Celery 任务。
2. **MinerU OCR**：Worker 下载/缓存模型，执行 OCR，生成 `_middle.json`。
3. **页面渲染**：`pdf2image` 将每页转换为 JPG 存放在 `data/mineru_output/<task>/pages/`。
4. **实时日志**：`processing_log` 字段持续更新，前端可展开查看。
5. **推送 Label Studio**：通过 `_generate_ls_tasks` 生成预标注并批量导入，包含文本框与文本内容。
6. **人工校对**：在 Label Studio 中使用 `label_studio_config.xml` 的界面进行标注、修正与关系定义。
7. **回传校对结果**：前端上传 Label Studio 导出 JSON（`corrected_label_studio_json`）。
8. **RAG 导出**：生成 RAGFlow 兼容 payload，自动更新文档状态为 `ingested`。

## Label Studio Integration
### 获取 API Token
1. 登录 `http://localhost:8081`。
2. 点击头像 -> **Account & Settings** -> **Access Token** -> `Create New Token`。
3. 将 Token 写入 `.env` 的 `LABEL_STUDIO_API_KEY`，并重启 `backend` 与 `celery`。
4. 若使用 JWT 个人令牌，系统会自动刷新 access token；

### 常见问题：看不到 OCR 识别结果

如果在 Label Studio 中看不到预标注的 OCR 结果（文本框和内容），这是最常见的问题。

**快速诊断**：
1. 标签名称不匹配（后端 vs Label Studio 配置）
2. API 推送失败（Token 错误或网络问题）

**快速修复**：

# 1. 是否完成了Label Studio 的 label surface 配置？
# 2. .env文件的Label studio 的 access token 是否完成了替换？
# 3. 重启服务
docker compose restart backend celery label-studio


```

### 环境变量要点
```env
LABEL_STUDIO_URL=http://label-studio:8080       # 容器网络地址
LABEL_STUDIO_API_KEY=<your-token>
LABEL_STUDIO_PROJECT_ID=1
BACKEND_EXTERNAL_URL=http://<host-or-ip>:8010   # Label Studio 访问后端图片的地址
```

### 标注界面配置
- 在项目设置中选择 **Labeling Interface** -> **Code**。
- 使用更新后的配置文件 `label_studio_config.xml`（已修复标签映射）。

### 自动推送与监控
- Celery 完成 OCR 后自动调用 Label Studio API：成功与失败都会写入 `processing_log`。
- 数据库字段 `label_studio_synced`、`label_studio_task_ids`、`label_studio_sync_time` 可用于追踪同步状态。
- 如需强制重推，调用 `/api/documents/<id>/push-to-label-studio` 并传 `force=true`。

### 图片访问
- 后端提供 `GET /api/images/<task>/<filename>`。
- `BACKEND_EXTERNAL_URL` 必须为 Label Studio 可访问的外部地址。
- 若跨主机部署，请使用宿主机内网 IP。

## Model Management
- MinerU 采用首次运行下载策略；模型缓存保存在 `mineru_models` 卷。
- **检查缓存**：
  ```bash
  docker volume ls | grep mineru_models
  docker exec ocr_celery_worker ls -lh /root/.cache/
  ```
- **手动预热**：
  ```bash
  docker exec -it ocr_celery_worker bash
  python scripts/download_models.py
  ```
- `backend/dockerfile` 采用分层构建，模型层只在依赖变化时重建，可结合 `prebuild` 脚本制作离线镜像。

## Logs & Monitoring
- `docker compose logs -f`：查看所有容器日志。
- `docker compose logs -f backend|celery|frontend|label-studio`：按服务查看。
- `celery -A backend inspect active / stats`：监控 Celery worker。
- 前端文档列表支持展开实时 `processing_log`，显示 OCR 命令、页码进度、异常与推送状态。

## Troubleshooting
| 场景 | 建议 |
|------|------|
| 前端无法连到后端 | 校验 `.env` 中 `VUE_APP_API_BASE_URL` 是否使用正确主机 IP；检查防火墙；重启 `frontend` 容器 |
| Label Studio 没有新任务 | 确认 `LABEL_STUDIO_API_KEY`、`LABEL_STUDIO_PROJECT_ID`；查看 `celery` 日志的 API 返回码；确保 `BACKEND_EXTERNAL_URL` 可访问 |
| MinerU 未生成 JSON | 检查 `processing_log` 是否有错误；确认 PDF 未损坏、磁盘充足；如超时请降低并发或拆分文档 |
| 模型下载失败 | 切换 `MINERU_MODEL_SOURCE=huggingface`；检查代理/网络；重新构建 `docker compose build --no-cache backend` |
| GPU 不可用 | 验证 `docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi`；确保安装 `nvidia-docker`; 启用配置文件中的 GPU 段落 |
| Label Studio 图片加载失败 | 使用可访问的 `BACKEND_EXTERNAL_URL`；确认 `GET /api/images/...` 返回 200 |

## Maintenance
```bash
# 更新代码
git pull origin main
docker compose down
docker compose up -d --build

# 备份数据库
docker exec ocr_postgres_db pg_dump -U test ocr_pipeline_db > backup.sql

# 备份数据目录
tar -czf data_backup_$(date +%Y%m%d).tar.gz data/

# 清理资源（谨慎）
docker system prune -a
```

---
> 首次执行 OCR 会下载约 1-2 GB 模型文件，请耐心等待。模型会缓存在 Docker 卷或镜像中，后续启动会显著加快。
> 在先前的尝试中，尝试使用反向代理会发生label studio的异常跳转（比如设置setting时正好遇到token刷新就被送到了login界面，令人头大），因此反向代理的实现可能比预想中的要复杂，谨慎尝试。