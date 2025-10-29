# 🔑 获取 Label Studio API Token

## 方法一：通过 Web 界面获取（推荐）

### 步骤：
1. 访问 Label Studio：`http://localhost:8081`
2. 登录（如果是首次访问，会要求创建账号）
3. 点击右上角的用户头像/用户名
4. 选择 **"Account & Settings"**
5. 在左侧菜单找到 **"Account"** 或直接查看页面
6. 找到 **"Access Token"** 部分
7. 点击 **"Create New Token"** 或复制已有的 Token
8. 复制 Token（类似：`a1b2c3d4e5f6...`）

### 配置 Token：
编辑 `docker-compose.yml`，在 backend 和 celery 服务中添加：

```yaml
environment:
  - LABEL_STUDIO_API_KEY=你复制的token
  - LABEL_STUDIO_PROJECT_ID=1  # 你的项目ID
```

然后重启服务：
```powershell
docker-compose restart backend celery
```

---

## 方法二：通过 API 获取 Token

如果已经知道用户名和密码：

```powershell
# 登录获取 Token
$body = @{
    username = "your_email@example.com"
    password = "your_password"
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://localhost:8081/api/current-user/token" `
    -Method POST `
    -Body $body `
    -ContentType "application/json"

Write-Host "Your API Token: $($response.token)"
```

---

## 方法三：重置 Label Studio（如果忘记密码）

```powershell
# 停止并删除 Label Studio 数据（警告：会删除所有项目和标注！）
docker-compose stop label-studio
docker volume rm ocr_v1_label_studio_data

# 重新启动
docker-compose up -d label-studio
```

然后重新创建账号和项目。

---

## 快速测试配置

配置好 Token 后，测试上传：

```powershell
# 测试上传文档 ID=3 到 Label Studio
Invoke-WebRequest `
    -Uri "http://localhost/api/documents/3/upload-to-label-studio/" `
    -Method POST `
    -UseBasicParsing | ConvertFrom-Json
```

期望输出：
```json
{
  "message": "成功上传 10 个任务到 Label Studio",
  "task_count": 10
}
```

---

## 故障排查

### 错误: "Authentication credentials were not provided"

**原因**：没有配置 API Token

**解决**：
1. 获取 Token（方法一或方法二）
2. 配置到 docker-compose.yml
3. 重启服务

### 错误: "Invalid token"

**原因**：Token 过期或不正确

**解决**：
1. 重新生成 Token
2. 更新配置
3. 重启服务

### 无法访问 Label Studio

**检查**：
```powershell
docker-compose ps label-studio
docker-compose logs label-studio
```
