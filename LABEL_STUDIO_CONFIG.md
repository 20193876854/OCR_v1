# Label Studio 自动上传配置指南

## 📋 配置步骤

### 1. 启动 Label Studio 并创建项目

首先启动所有服务：
```bash
docker-compose up -d
```

访问 Label Studio：`http://localhost:8081`

### 2. 创建新项目

1. 在 Label Studio 中创建一个新项目
2. 选择项目类型：**Computer Vision** → **Image Classification** 或自定义模板
3. 记录下项目的 ID（在项目URL中，例如：`http://localhost:8081/projects/1/` 中的 `1`）

### 3. 配置项目标签

使用以下 XML 配置作为标注界面：

```xml
<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true"/>
  <RectangleLabels name="bbox" toName="image">
    <Label value="Text" background="blue"/>
    <Label value="Title" background="green"/>
    <Label value="List" background="yellow"/>
    <Label value="Figure" background="red"/>
    <Label value="Table" background="purple"/>
    <Label value="Header" background="cyan"/>
    <Label value="Footer" background="orange"/>
    <Label value="Equation" background="pink"/>
  </RectangleLabels>
  <TextArea name="transcription" toName="image" 
            editable="true" perRegion="true" 
            required="false" maxSubmissions="1" 
            rows="5" placeholder="输入或修改此区域的文本内容"/>
</View>
```

### 4. 获取 API Token（可选）

如果您的 Label Studio 启用了身份验证：

1. 点击右上角的用户头像
2. 选择 **Account & Settings**
3. 找到 **Access Token** 部分
4. 复制您的 API Token

### 5. 更新 docker-compose.yml

编辑 `docker-compose.yml`，在 `backend` 和 `celery` 服务中设置环境变量：

```yaml
environment:
  - LABEL_STUDIO_URL=http://label-studio:8081
  - LABEL_STUDIO_API_KEY=your_api_token_here  # 如果不需要认证，留空
  - LABEL_STUDIO_PROJECT_ID=1  # 替换为您的项目ID
```

### 6. 重启服务

```bash
docker-compose down
docker-compose up -d backend celery
```

## 🚀 使用方法

### 自动上传流程

1. **上传PDF** → 系统自动进行 OCR 处理
2. **OCR完成** → 系统会**自动**尝试上传到 Label Studio（如果配置了 PROJECT_ID）
3. **在 Label Studio 中校对** → 访问 `http://localhost:8081`，打开您的项目开始标注
4. **导出校对结果** → 在 Label Studio 中导出为 JSON 格式
5. **上传校对结果** → 在前端界面点击"上传校对JSON"
6. **生成 RAGFlow 文件** → 点击"生成RAGFlow"按钮下载入库文件

### 手动上传流程（备选）

如果自动上传失败或未配置，您可以：

1. **点击"📤 自动上传LS"按钮** → 手动触发上传到 Label Studio
2. **或下载OCR JSON** → 手动在 Label Studio 中导入
3. 其余流程相同

## 🔍 故障排查

### 问题：自动上传失败

**检查项：**
1. 确认 `LABEL_STUDIO_PROJECT_ID` 已设置
2. 查看后端日志：`docker-compose logs backend celery`
3. 确认 Label Studio 可访问：`docker-compose exec backend curl http://label-studio:8081`

### 问题：Label Studio 无法显示图片

**原因：** Label Studio 需要能够访问图片文件

**解决方案：**
在 `docker-compose.yml` 中为 Label Studio 添加数据卷映射：

```yaml
label-studio:
  image: heartexlabs/label-studio:latest
  volumes:
    - label_studio_data:/label-studio/data
    - ./data:/data:ro  # 添加这一行，允许访问OCR输出的图片
  environment:
    - LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
    - LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/data
```

## 📝 工作流程图

```
PDF上传
   ↓
MinerU OCR处理
   ↓
自动上传到Label Studio (NEW!)
   ↓
人工在Label Studio中校对
   ↓
导出校对JSON
   ↓
上传校对JSON到系统
   ↓
生成RAGFlow入库文件
```

## 🎯 优势

- ✅ **全自动化**：OCR完成后自动推送到Label Studio
- ✅ **保留手动选项**：仍可手动下载/上传JSON
- ✅ **响应式界面**：前端适配移动端和小屏幕
- ✅ **状态追踪**：清晰的视觉反馈和状态指示
