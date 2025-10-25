# 🚀 Label Studio 自动上传完整指南

## 📋 系统架构说明

### 图片文件访问方式

我们使用 **Label Studio Local Files** 功能，让 Label Studio 直接访问服务器上的图片文件，而不是上传图片。

#### 架构流程：
```
1. PDF 上传 → Backend
2. MinerU OCR 处理 → 生成图片到 ./data/mineru_output/{unique_id}/pages/
3. 图片和 JSON 数据 → Backend 数据库
4. 自动上传任务 → Label Studio (只传 JSON + 图片路径引用)
5. Label Studio → 通过 local-files 读取图片
```

### 文件路径映射

| 位置 | 主机路径 | Backend容器路径 | Label Studio容器路径 |
|------|---------|----------------|---------------------|
| 数据目录 | `./data` | `/data` | `/data` |
| 图片文件 | `./data/mineru_output/{id}/pages/` | `/data/mineru_output/{id}/pages/` | `/data/mineru_output/{id}/pages/` |

### Label Studio 图片 URL 格式

```
/data/local-files/?d=mineru_output/{unique_id}/pages/page-0001.jpg
```

- `d` 参数：相对于 `LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT` 的路径
- 在我们的配置中，`DOCUMENT_ROOT=/data`
- 所以完整路径是：`/data/mineru_output/{unique_id}/pages/page-0001.jpg`

---

## ⚙️ 配置步骤

### 步骤 1: 验证 Docker 卷映射

确保 `docker-compose.yml` 中的 Label Studio 配置正确：

```yaml
label-studio:
  image: heartexlabs/label-studio:latest
  volumes:
    - label_studio_data:/label-studio/data    # Label Studio 内部数据
    - ./data:/data:ro                          # OCR 输出文件（只读）
  environment:
    - LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
    - LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/data
```

### 步骤 2: 创建 Label Studio 项目

1. 访问：`http://localhost:8081`
2. 创建账号并登录
3. 点击 **"Create Project"**
4. 项目名称：例如 "OCR Document Proofreading"

### 步骤 3: 配置标注界面

在 **Labeling Setup** 或 **Settings → Labeling Interface** 中，粘贴：

```xml
<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="true"/>
  <RectangleLabels name="bbox" toName="image">
    <Label value="Text" background="#3b82f6"/>
    <Label value="Title" background="#10b981"/>
    <Label value="List" background="#f59e0b"/>
    <Label value="Figure" background="#ef4444"/>
    <Label value="Table" background="#8b5cf6"/>
    <Label value="Header" background="#06b6d4"/>
    <Label value="Footer" background="#f97316"/>
    <Label value="Equation" background="#ec4899"/>
  </RectangleLabels>
  <TextArea name="transcription" toName="image" 
            editable="true" 
            perRegion="true" 
            required="false" 
            maxSubmissions="1" 
            rows="5" 
            placeholder="输入或修改此区域的文本内容"/>
</View>
```

### 步骤 4: 配置 Cloud Storage (关键！)

为了让 Label Studio 能够访问本地文件，需要配置 Cloud Storage：

1. 进入项目 **Settings → Cloud Storage**
2. 点击 **"Add Source Storage"**
3. 选择 **"Local Files"**
4. 配置如下：
   - **Storage Title**: OCR Images
   - **Absolute local path**: `/data/mineru_output`
   - **File Filter Regex**: `.*\.jpg$` (可选，只显示 JPG 文件)
   - **Treat every bucket object as a source file**: ✅ 勾选
5. 点击 **"Add Storage"**
6. 点击 **"Sync Storage"** 同步文件

**注意**：如果您通过 API 上传任务（推荐方式），可以跳过 Cloud Storage 配置。

### 步骤 5: 获取项目 ID 和 API Token

#### 获取 Project ID:
- 在项目页面，查看 URL：`http://localhost:8081/projects/1/`
- Project ID = `1`

#### 获取 API Token (可选):
1. 点击右上角用户头像
2. **Account & Settings**
3. **Access Token** → 复制 Token

### 步骤 6: 更新 Backend 配置

编辑 `docker-compose.yml`，在 `backend` 和 `celery` 服务中：

```yaml
environment:
  - LABEL_STUDIO_URL=http://label-studio:8080
  - LABEL_STUDIO_API_KEY=your_token_here  # 可选，如果不需要认证留空
  - LABEL_STUDIO_PROJECT_ID=1             # 替换为您的实际 Project ID
```

### 步骤 7: 重启服务

```powershell
docker-compose restart backend celery
```

---

## 🔄 使用自动上传功能

### 方式一：自动上传（推荐）

OCR 处理完成后，系统会**自动**尝试上传任务到 Label Studio。

查看日志确认：
```powershell
docker-compose logs -f celery | Select-String "Label Studio"
```

### 方式二：手动触发上传

在前端界面：
1. 找到状态为 "processed" 的文档
2. 点击 **"📤 自动上传LS"** 按钮
3. 等待上传完成提示

### 方式三：API 调用

```powershell
# 上传文档 ID=3 的任务到 Label Studio
$response = Invoke-WebRequest -Uri "http://localhost/api/documents/3/upload-to-label-studio/" -Method POST -UseBasicParsing
$response.Content | ConvertFrom-Json
```

---

## 🔍 验证上传成功

### 1. 检查后端日志
```powershell
docker-compose logs backend celery | Select-String "upload" -Context 2
```

### 2. 访问 Label Studio
```
http://localhost:8081/projects/1/
```

应该能看到导入的任务，每个任务对应 PDF 的一页。

### 3. 检查图片显示

如果图片无法显示：

#### 问题诊断：
```powershell
# 1. 检查容器内文件是否存在
docker exec ocr_label_studio ls -la /data/mineru_output/

# 2. 检查文件权限
docker exec ocr_label_studio ls -la /data/mineru_output/{unique_id}/pages/

# 3. 测试图片访问
docker exec ocr_label_studio cat /data/mineru_output/{unique_id}/pages/page-0001.jpg > test.jpg
```

#### 常见解决方案：

**问题 1: 图片路径不正确**
- 检查生成的 JSON 中的 image URL
- 确保格式为：`/data/local-files/?d=mineru_output/.../page-0001.jpg`

**问题 2: Label Studio 无法访问文件**
- 确认卷映射：`./data:/data:ro`
- 重启 Label Studio：`docker-compose restart label-studio`

**问题 3: 权限问题**
```powershell
# 给数据目录添加读取权限（Windows）
icacls ".\data" /grant Everyone:R /T

# Linux/Mac
chmod -R 755 ./data
```

---

## 📝 完整工作流程

### 1. 上传 PDF
```
前端 → 上传 PDF 文件
```

### 2. 自动 OCR
```
Backend → MinerU 处理
       → 生成图片到 /data/mineru_output/{id}/pages/
       → 保存 JSON 到数据库
       → 自动调用上传到 Label Studio
```

### 3. 在 Label Studio 中校对
```
访问 http://localhost:8081
→ 打开项目
→ 查看任务
→ 修改文本内容
→ 调整边界框（如需要）
→ 提交标注
```

### 4. 导出校对结果
```
Label Studio → Export
            → 选择 JSON 格式
            → 下载文件
```

### 5. 上传校对结果
```
前端 → 点击"📤 上传校对JSON"
     → 选择导出的 JSON 文件
     → 上传
```

### 6. 生成 RAGFlow 文件
```
前端 → 点击"🚀 生成RAGFlow"
     → 下载入库文件
```

---

## 🐛 故障排查

### 问题：自动上传失败

**检查清单：**
1. ✅ `LABEL_STUDIO_PROJECT_ID` 是否配置？
2. ✅ Label Studio 是否在运行？
3. ✅ 项目 ID 是否正确？
4. ✅ 网络是否连通？

**诊断命令：**
```powershell
# 测试 Backend 到 Label Studio 的连接
docker exec ocr_backend curl http://label-studio:8080/

# 查看详细日志
docker-compose logs celery | Select-String "Label Studio|upload|error" -Context 5
```

### 问题：图片无法在 Label Studio 中显示

**原因分析：**
- Local files 功能未启用
- 路径配置不正确
- 文件权限问题
- 卷映射问题

**解决步骤：**
1. 确认环境变量：
   ```yaml
   - LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
   - LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/data
   ```

2. 重启 Label Studio：
   ```powershell
   docker-compose restart label-studio
   ```

3. 检查图片 URL 格式：
   - ✅ 正确：`/data/local-files/?d=mineru_output/abc123/pages/page-0001.jpg`
   - ❌ 错误：`/data/local-files/?d=data/mineru_output/...`
   - ❌ 错误：`/data/local-files/?d=/data/mineru_output/...`

### 问题：API Token 认证失败

如果 Label Studio 启用了认证：

```yaml
environment:
  - LABEL_STUDIO_API_KEY=your_actual_token_here
```

获取 Token:
1. Label Studio → Account Settings
2. Access Token → Copy

---

## 📊 性能优化建议

### 1. 图片压缩
如果 PDF 页面很多，可以调整图片质量：

编辑 `backend/api/tasks.py`：
```python
pil_images = convert_from_path(
    pdf_path, 
    poppler_path=POPPLER_PATH, 
    thread_count=4, 
    fmt='jpeg',
    jpegopt={'quality': 85, 'optimize': True}  # 添加这一行
)
```

### 2. 批量上传
如果任务数量很多，可以分批上传。

### 3. 异步处理
已实现：使用 Celery 异步处理 OCR 和上传任务。

---

## 🎉 总结

### 优势：
- ✅ **无需上传图片**：图片存储在服务器，Label Studio 直接读取
- ✅ **节省空间**：不重复存储图片
- ✅ **加载速度快**：本地文件访问
- ✅ **自动化流程**：一键上传任务
- ✅ **灵活配置**：支持自动和手动两种模式

### 架构图：
```
┌─────────────┐
│   Frontend  │ ← 用户上传 PDF
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│   Backend   │────→│   Celery     │ ← OCR 处理
└──────┬──────┘     └──────┬───────┘
       │                   │
       │                   ▼
       │            ┌─────────────────┐
       │            │ ./data/mineru_  │ ← 图片存储
       │            │    output/      │
       │            └─────────────────┘
       │                   ↑
       ▼                   │ (挂载)
┌─────────────┐            │
│Label Studio │───────────┘
│  (访问图片) │
└─────────────┘
```

享受您的自动化 OCR 校对流程！🚀
