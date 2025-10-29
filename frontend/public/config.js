// 全局配置文件
// 此文件在运行时加载，支持通过环境变量动态配置
window.APP_CONFIG = {
    // API 基础地址 - 可通过环境变量 VUE_APP_API_BASE_URL 配置
    // 默认使用当前主机的 8010 端口
    API_BASE_URL: window.VUE_APP_API_BASE_URL || `http://${window.location.hostname}:8010/api`,
    
    // Label Studio 地址 - 可通过环境变量 VUE_APP_LABEL_STUDIO_URL 配置
    LABEL_STUDIO_URL: window.VUE_APP_LABEL_STUDIO_URL || `http://${window.location.hostname}:8081`,
}
