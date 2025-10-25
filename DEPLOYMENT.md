# 前端部署配置说明

## 配置方法

本项目通过 **Nginx 反向代理** 统一管理前后端和 Label Studio 的访问，**无需修改内部代码**即可部署到不同的服务器。

## 架构说明

```
用户访问
  ↓
Nginx (端口 80)
  ├─→ / (前端应用)
  ├─→ /api/ (后端API)
  └─→ /label-studio/ (Label Studio)
```

## 配置步骤

### 1. 前端配置

前端已经使用相对路径 `/api`，通过 Nginx 反向代理访问后端。

**开发环境** (`.env.local` 或 `.env.development`):
```bash
# 开发时可以直接指定后端地址
VUE_APP_API_BASE_URL=http://localhost:8010/api
```

**生产环境** (`.env.production`):
```bash
# 生产环境使用相对路径，通过 Nginx 访问
VUE_APP_API_BASE_URL=/api
```

### 2. Nginx 配置

Nginx 配置文件位于 `nginx/nginx.conf`，已经配置好以下路由：

- `http://your-server/` → 前端应用
- `http://your-server/api/` → 后端 API
- `http://your-server/label-studio/` → Label Studio

### 3. 部署到不同服务器

#### 方法一：使用域名（推荐）

1. 配置 DNS 将域名指向服务器 IP
2. 修改 `nginx/nginx.conf` 中的 `server_name`:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;  # 修改为你的域名
       ...
   }
   ```
3. 重启服务: `docker-compose restart nginx`

#### 方法二：使用 IP + 端口

默认配置已支持通过 IP 访问：
- 前端: `http://your-ip/`
- 后端 API: `http://your-ip/api/`
- Label Studio: `http://your-ip/label-studio/`

如需修改端口，编辑 `docker-compose.yml`:
```yaml
nginx:
  ports:
    - "8080:80"  # 将 80 改为其他端口
```

### 4. HTTPS 配置（可选）

对于生产环境，建议启用 HTTPS：

1. 安装 certbot 获取 SSL 证书
2. 修改 `nginx/nginx.conf` 添加 SSL 配置：
   ```nginx
   server {
       listen 443 ssl;
       server_name your-domain.com;
       
       ssl_certificate /etc/nginx/ssl/cert.pem;
       ssl_certificate_key /etc/nginx/ssl/key.pem;
       
       # ... 其他配置
   }
   
   # HTTP 重定向到 HTTPS
   server {
       listen 80;
       server_name your-domain.com;
       return 301 https://$server_name$request_uri;
   }
   ```

## 服务访问地址

### 通过 Nginx 访问（推荐）
- 前端界面: `http://your-server/`
- Label Studio: `http://your-server/label-studio/`
- 后端 API: `http://your-server/api/`

### 直接访问（调试用）

如需直接访问各服务进行调试，可以在 `docker-compose.yml` 中取消注释相应的端口映射：

```yaml
backend:
  ports:
    - "8010:8010"  # 取消注释以直接访问后端

label-studio:
  ports:
    - "8081:8081"  # 取消注释以直接访问 Label Studio
```

## 常见问题

### Q: 如何修改服务器 IP 或域名？
A: 无需修改代码，只需：
1. 确保 `.env.production` 中使用相对路径 `/api`
2. 如使用域名，修改 `nginx/nginx.conf` 中的 `server_name`
3. 重启服务

### Q: Label Studio 无法加载图片？
A: 检查以下配置：
1. Nginx 的 `/data/` 路径配置正确
2. Label Studio 任务中的图片路径使用 `/data/local-files/?d=...` 格式
3. `docker-compose.yml` 中 backend 和 label-studio 都挂载了 `./data:/data`

### Q: API 请求跨域错误？
A: 通过 Nginx 反向代理访问，前后端同域，不会出现跨域问题。如果直接访问后端，需要在后端配置 CORS。

## 网络架构图

```
┌─────────────────────────────────────────────┐
│            外部访问 (端口 80)                 │
│         http://your-server/                 │
└───────────────────┬─────────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   Nginx 反向代理        │
        │  (ocr_nginx 容器)       │
        └───────────┬─────────────┘
                    │
        ┌───────────┼────────────┐
        │           │            │
        ▼           ▼            ▼
   ┌────────┐  ┌────────┐  ┌──────────┐
   │Frontend│  │Backend │  │  Label   │
   │  :80   │  │ :8010  │  │ Studio   │
   └────────┘  └────────┘  └──────────┘
                    │            :8081
                    ▼
              ┌──────────┐
              │PostgreSQL│
              │  :5432   │
              └──────────┘
                    ▲
                    │
              ┌──────────┐
              │  Redis   │
              │  :6379   │
              └──────────┘
```
