import axios from 'axios';

// 从全局配置中读取 API 地址
// 支持运行时动态配置，无需修改代码
const apiClient = axios.create({
    baseURL: window.APP_CONFIG?.API_BASE_URL || 'http://localhost:8010/api',
    headers: {
        'Content-Type': 'application/json'
    },
    timeout: 30000 // 30秒超时
});

// 添加响应拦截器处理错误
apiClient.interceptors.response.use(
    response => response,
    error => {
        console.error('API Error:', error);
        if (error.response) {
            // 服务器返回错误状态码
            const message = error.response.data?.error || error.response.data?.detail || '请求失败';
            error.message = message;
        } else if (error.request) {
            // 请求已发出但没有收到响应
            error.message = '无法连接到服务器，请检查网络连接';
        }
        return Promise.reject(error);
    }
);

export default {
    // 获取所有文档列表
    getDocuments() {
        return apiClient.get('/documents/');
    },
    
    // 上传PDF文档
    uploadDocument(file) {
        const formData = new FormData();
        formData.append('file', file);
        return apiClient.post('/documents/upload/', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });
    },
    
    // 获取Label Studio任务JSON（原始OCR结果）
    getLabelStudioTasks(docId) {
        return apiClient.get(`/documents/${docId}/to-label-studio/`);
    },
    
    // 提交校对后的数据到RAGFlow
    ingestToRagflow(docId, correctedData) {
        return apiClient.post(`/documents/${docId}/ingest-to-ragflow/`, correctedData);
    },
    
    // 删除文档（需要后端支持）
    deleteDocument(docId) {
        return apiClient.delete(`/documents/${docId}/`);
    },
    
    // 获取单个文档详情
    getDocument(docId) {
        return apiClient.get(`/documents/${docId}/`);
    },
    
    // 导出RAGFlow格式文件（需要后端添加此接口）
    exportToRAGFlow(docId) {
        return apiClient.get(`/documents/${docId}/to-ragflow/`, {
            responseType: 'blob'
        });
    },
    
    // 推送到 Label Studio
    pushToLabelStudio(docId, force = false) {
        return apiClient.post(`/documents/${docId}/push-to-labelstudio/`, { force });
    }
};
