#!/bin/sh
# 前端环境变量注入脚本
# 在容器启动时动态生成配置文件

set -e

CONFIG_FILE="/usr/share/nginx/html/config.js"

echo "生成前端配置文件..."

# 生成配置文件，使用环境变量或默认值
cat > "$CONFIG_FILE" << EOF
// 此文件由 docker-entrypoint.sh 自动生成
// 请勿手动修改，修改 docker-compose.yml 中的环境变量即可
window.APP_CONFIG = {
    API_BASE_URL: '${VUE_APP_API_BASE_URL:-http://localhost:8010/api}',
    LABEL_STUDIO_URL: '${VUE_APP_LABEL_STUDIO_URL:-http://localhost:8081}',
};

console.log('应用配置已加载:', window.APP_CONFIG);
EOF

echo "配置文件已生成: $CONFIG_FILE"
cat "$CONFIG_FILE"

# 执行传入的命令（启动 nginx）
exec "$@"
