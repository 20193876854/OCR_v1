# 使用轻量级 Nginx 直接提供静态文件服务
FROM nginx:alpine

# 复制 index.html 到 Nginx 默认目录
COPY index.html /usr/share/nginx/html/

# 暴露端口
EXPOSE 80

# 使用自定义 Nginx 配置（如果需要）
# 如果不需要特殊配置，可以注释掉下面这行
# COPY nginx.conf /etc/nginx/conf.d/default.conf

# Nginx 会自动启动
