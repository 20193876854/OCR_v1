# ============================================================
# 多阶段构建：前端优化版
# ============================================================

# ============================================================
# 阶段 1: 依赖安装
# ============================================================
FROM node:18-alpine AS dependencies

WORKDIR /app

# 只复制 package 文件，利用 Docker 缓存
COPY package*.json ./

# 安装依赖（使用国内镜像加速）
RUN npm config set registry https://registry.npmmirror.com && \
    npm ci --only=production && \
    npm cache clean --force

# ============================================================
# 阶段 2: 构建阶段
# ============================================================
FROM node:18-alpine AS builder

WORKDIR /app

# 复制依赖
COPY --from=dependencies /app/node_modules ./node_modules

# 复制 package 文件
COPY package*.json ./

# 安装开发依赖
RUN npm config set registry https://registry.npmmirror.com && \
    npm install

# 复制源代码
COPY . .

# 构建生产版本
RUN npm run build

# ============================================================
# 阶段 3: 生产运行时
# ============================================================
FROM nginx:alpine AS runtime

# 从构建阶段复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制环境变量注入脚本
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# 复制 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 安装 curl 用于健康检查
RUN apk add --no-cache curl

# 暴露端口
EXPOSE 8082

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8082/ || exit 1

# 使用脚本作为入口点
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]

# ============================================================
# 构建优化说明：
# 1. 分离依赖安装和代码复制，最大化缓存利用
# 2. 生产依赖和开发依赖分开安装
# 3. 最终镜像只包含构建产物和 nginx
# 4. 添加健康检查
# ============================================================

