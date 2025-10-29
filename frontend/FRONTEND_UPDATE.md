# 前端界面美化更新说明

## 🎨 更新内容

### 视觉改进

1. **现代化设计**
   - 使用 Tailwind CSS 实现响应式设计
   - 采用 Inter 字体，提升视觉体验
   - 卡片式布局，清晰的信息层级

2. **状态可视化**
   - 彩色状态点指示文档处理状态
   - 状态徽章（Badge）显示关键信息
   - 处理中状态带动画效果

3. **交互优化**
   - 拖拽上传支持
   - 按钮悬停效果
   - 加载状态反馈
   - 操作确认提示

### 功能增强

1. **文件上传**
   - ✅ 支持点击选择文件
   - ✅ 支持拖拽上传
   - ✅ 文件类型验证（只接受PDF）
   - ✅ 上传进度显示

2. **文档管理**
   - ✅ 实时状态更新（每5秒轮询）
   - ✅ 文档操作按钮分组
   - ✅ 操作权限控制（根据状态禁用按钮）
   - ✅ 删除确认对话框

3. **数据交互**
   - ✅ OCR JSON 下载
   - ✅ 校对文件上传
   - ✅ RAGFlow 文件生成
   - ✅ Label Studio 快捷入口

### 响应式设计

- 📱 移动端优化
- 💻 平板适配
- 🖥️ 桌面端完美显示

## 🚀 使用指南

### 开发环境

```bash
# 进入前端目录
cd frontend

# 安装依赖（如果需要）
npm install

# 启动开发服务器
npm run serve

# 访问
http://localhost:8080
```

### 生产部署

```bash
# 构建生产版本
npm run build

# 使用 Docker
docker-compose up -d frontend
```

## 📋 工作流程

### 1. 上传PDF文档

- 拖拽PDF文件到上传区域
- 或点击上传区域选择文件
- 点击"上传并开始处理"

### 2. 等待OCR处理

- 文档状态：`pending` → `processing` → `processed`
- 状态点颜色变化指示进度
- 自动刷新列表显示最新状态

### 3. 下载OCR结果

- 点击"📥 下载OCR JSON"
- 获取Label Studio格式的JSON文件

### 4. 人工校对

- 点击"🏷️ 打开 Label Studio"
- 在Label Studio中导入JSON文件
- 进行人工校对和修正
- 导出校对后的JSON

### 5. 上传校对结果

- 点击"📤 上传校对JSON"
- 选择Label Studio导出的文件
- 系统更新文档状态为`corrected`

### 6. 生成RAGFlow文件

- 点击"🚀 生成RAGFlow"
- 下载用于RAGFlow入库的JSON文件
- 文档状态更新为`ingested`

## 🎯 状态说明

| 状态 | 颜色 | 说明 |
|------|------|------|
| `pending` | 🟠 橙色 | 等待处理 |
| `processing` | 🔵 蓝色（动画） | 处理中 |
| `processed` | 🟢 绿色 | OCR完成 |
| `failed` | 🔴 红色 | 处理失败 |
| `corrected` | 🟦 青色 | 已校对 |
| `ingested` | 🟣 紫色 | 已入库 |

## 🔧 配置说明

### API地址配置

前端会自动从以下位置读取配置：

1. `public/config.js` 文件
2. 环境变量（通过 docker-entrypoint.sh 注入）
3. 默认值：`http://localhost:8010/api`

### Label Studio地址

- 默认：`http://localhost:8081`
- 可通过 `.env` 文件配置：`VUE_APP_LABEL_STUDIO_URL`

## 📦 技术栈

- **Vue.js 3** - 渐进式JavaScript框架
- **Tailwind CSS** - 实用优先的CSS框架
- **Axios** - HTTP客户端
- **Inter Font** - 现代字体

## 🔄 API接口

### 当前支持的接口

```javascript
GET  /api/documents/              // 获取文档列表
POST /api/documents/upload/       // 上传PDF
GET  /api/documents/:id/to-label-studio/  // 获取OCR JSON
POST /api/documents/:id/ingest-to-ragflow/  // 提交校对数据
```

### 需要后端添加的接口

```javascript
DELETE /api/documents/:id/        // 删除文档
GET    /api/documents/:id/        // 获取单个文档
GET    /api/documents/:id/to-ragflow/  // 导出RAGFlow文件
```

## 🐛 已知问题

1. **删除功能** - 需要后端添加DELETE接口支持
2. **RAGFlow导出** - 当前使用临时方案，建议添加专用接口
3. **错误处理** - 部分错误信息需要更友好的展示

## 🎨 自定义主题

如需自定义颜色主题，修改以下CSS变量：

```css
/* 在 App.vue 的 <style> 中 */
.status-pending { background-color: #f59e0b; }
.status-processing { background-color: #3b82f6; }
.status-processed { background-color: #10b981; }
/* ... 其他状态颜色 */
```

## 📸 界面截图

### 上传区域
- 拖拽式上传界面
- 清晰的操作提示

### 文档列表
- 卡片式布局
- 状态可视化
- 操作按钮分组

### 响应式设计
- 移动端自适应
- 按钮自动换行
- 触摸友好

## 🚀 性能优化

1. **自动轮询** - 每5秒刷新一次文档列表
2. **条件渲染** - 根据状态显示/隐藏按钮
3. **懒加载** - 按需加载组件
4. **CDN加速** - Tailwind CSS使用CDN

## 📱 浏览器兼容性

- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

## 🔗 相关文档

- [Vue.js 官方文档](https://vuejs.org/)
- [Tailwind CSS 文档](https://tailwindcss.com/)
- [Axios 文档](https://axios-http.com/)

---

**更新日期**: 2025年10月27日  
**版本**: v2.0

**美化完成！** 🎉
