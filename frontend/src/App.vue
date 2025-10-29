<template>
  <div id="app" class="min-h-screen bg-gray-100">
    <div class="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8">
      
      <!-- Header -->
      <header class="mb-8">
        <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 class="text-4xl font-bold text-gray-900">OCR 处理流程面板</h1>
            <p class="mt-2 text-lg text-gray-600">上传PDF → 自动OCR → 人工校对 → 生成RAGFlow入库文件</p>
          </div>
          <a 
            :href="labelStudioUrl" 
            target="_blank" 
            class="btn btn-info flex items-center gap-2 whitespace-nowrap"
          >
            <span>🏷️</span>
            <span>打开 Label Studio</span>
          </a>
        </div>
      </header>

      <!-- 文件上传区域 -->
      <div class="bg-white p-6 rounded-lg shadow-md mb-8">
        <h2 class="text-2xl font-semibold mb-4">第一步：上传PDF文档</h2>
        <div 
          @dragover.prevent="dragover = true" 
          @dragleave.prevent="dragover = false" 
          @drop.prevent="handleDrop"
          :class="{'border-blue-500 bg-blue-50': dragover, 'border-gray-300': !dragover}"
          class="border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors"
          @click="$refs.fileInput.click()"
        >
          <input type="file" ref="fileInput" @change="handleFileUpload" class="hidden" accept=".pdf">
          <p v-if="!fileToUpload" class="text-gray-500">将PDF文件拖拽到此处，或点击选择文件</p>
          <p v-else class="text-blue-700 font-medium">📄 {{ fileToUpload.name }}</p>
        </div>
        <div class="mt-4 text-right">
          <button 
            @click="submitFile" 
            :disabled="!fileToUpload || isUploading" 
            class="btn btn-primary" 
            :class="{'opacity-50 cursor-not-allowed': !fileToUpload || isUploading}"
          >
            <span v-if="isUploading">上传中<span class="spinner"></span></span>
            <span v-else>上传并开始处理</span>
          </button>
        </div>
      </div>

      <!-- 文档列表 -->
      <div class="bg-white p-6 rounded-lg shadow-md">
        <h2 class="text-2xl font-semibold mb-4">第二步：文档处理中心</h2>
        
        <div v-if="isLoading" class="text-center py-8">
          <div class="spinner-large mx-auto"></div>
          <p class="mt-4 text-gray-600">加载文档列表中...</p>
        </div>
        
        <div v-else-if="documents.length === 0" class="text-center py-12 text-gray-500">
          <p class="text-xl">📭 暂无文档</p>
          <p class="mt-2">请上传PDF文件开始处理</p>
        </div>
        
        <ul v-else class="space-y-4">
          <li v-for="doc in documents" :key="doc.id" class="p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow">
            <!-- 文档信息区域 -->
            <div class="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
              <div class="flex-grow min-w-0 w-full">
                <div class="flex items-center gap-3 flex-wrap">
                  <span class="status-dot" :class="`status-${doc.status}`" :title="getStatusText(doc.status)"></span>
                  <p class="font-mono text-sm text-gray-700 break-all">{{ getFileName(doc.original_pdf_path) }}</p>
                  
                  <span v-if="doc.raw_ocr_json" class="badge badge-sky">OCR完成</span>
                  <span v-if="doc.corrected_label_studio_json" class="badge badge-teal">校对已保存</span>
                  <span v-if="doc.status === 'ingested'" class="badge badge-violet">RAGFlow已生成</span>
                </div>
                <p class="text-xs text-gray-500 mt-1">
                  上传于: {{ formatDate(doc.created_at) }} | 状态: {{ getStatusText(doc.status) }}
                </p>
                
                <!-- 处理日志显示区域 -->
                <div v-if="doc.processing_log && doc.processing_log.trim()" class="mt-3 p-3 bg-gray-50 rounded border border-gray-200">
                  <details :open="doc.status === 'processing'">
                    <summary class="cursor-pointer text-sm font-medium text-gray-700 mb-2">📋 处理日志</summary>
                    <pre class="text-xs text-gray-600 whitespace-pre-wrap font-mono max-h-60 overflow-y-auto">{{ doc.processing_log }}</pre>
                  </details>
                </div>
              </div>
              
              <!-- 操作按钮区域 -->
              <div class="flex flex-wrap items-center gap-2 w-full lg:w-auto">
                
                <!-- 下载原始OCR JSON -->
                <button 
                  @click="downloadRawOcrJson(doc.id)" 
                  :disabled="!isReadyForDownload(doc.status)" 
                  class="btn btn-secondary text-sm flex-1 sm:flex-none" 
                  :class="{'opacity-50 cursor-not-allowed': !isReadyForDownload(doc.status)}"
                  title="下载原始OCR JSON"
                >
                  📥 下载OCR JSON
                </button>

                <!-- 上传校对JSON -->
                <input 
                  type="file" 
                  :ref="`correctionFileInput_${doc.id}`" 
                  @change="handleCorrectionFileUpload($event, doc.id)" 
                  class="hidden" 
                  accept=".json"
                >
                <button 
                  @click="triggerCorrectionFileUpload(doc.id)" 
                  class="btn btn-info text-sm flex-1 sm:flex-none"
                  title="上传Label Studio导出的校对JSON"
                >
                  📤 上传校对JSON
                </button>
                
                <!-- 推送到 Label Studio -->
                <button 
                  @click="pushToLabelStudio(doc.id, doc.label_studio_synced)" 
                  :disabled="!isReadyForDownload(doc.status)" 
                  class="btn text-sm flex-1 sm:flex-none" 
                  :class="{
                    'btn-secondary': !doc.label_studio_synced,
                    'bg-teal-600 text-white hover:bg-teal-700': doc.label_studio_synced,
                    'opacity-50 cursor-not-allowed': !isReadyForDownload(doc.status)
                  }"
                  :title="doc.label_studio_synced ? '已推送到Label Studio,点击重新推送' : '推送到Label Studio进行标注'"
                >
                  {{ doc.label_studio_synced ? '✅ 已推送LS' : '📤 推送到LS' }}
                </button>
                
                <!-- 生成RAGFlow文件 -->
                <button 
                  @click="downloadRAGFlowPayload(doc.id)" 
                  :disabled="!canGenerateRAG(doc.status)" 
                  class="btn btn-success text-sm flex-1 sm:flex-none" 
                  :class="{'opacity-50 cursor-not-allowed': !canGenerateRAG(doc.status)}"
                  title="生成RAGFlow入库文件"
                >
                  🚀 生成RAGFlow
                </button>

                <!-- 删除 -->
                <button 
                  @click="deleteDocument(doc.id)" 
                  class="btn btn-danger text-sm flex-1 sm:flex-none"
                  title="删除此文档"
                >
                  🗑️ 删除
                </button>
              </div>
            </div>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script>
import api from './services/api';

export default {
  name: 'App',
  data() {
    return {
      documents: [],
      fileToUpload: null,
      isLoading: true,
      isUploading: false,
      dragover: false,
      pollInterval: null,
      labelStudioUrl: window.APP_CONFIG?.LABEL_STUDIO_URL || 'http://localhost:8081',
    };
  },
  methods: {
    async fetchDocuments() {
      try {
        const response = await api.getDocuments();
        this.documents = response.data;
      } catch (error) {
        console.error('获取文档列表失败:', error);
        this.$nextTick(() => {
          if (this.documents.length === 0) {
            // 首次加载失败时显示错误
            alert('无法连接到后端服务，请检查后端是否正常运行');
          }
        });
      } finally {
        this.isLoading = false;
      }
    },
    
    handleFileUpload(event) {
      this.fileToUpload = event.target.files[0];
      this.dragover = false;
    },
    
    handleDrop(event) {
      const files = event.dataTransfer.files;
      if (files.length > 0 && files[0].type === 'application/pdf') {
        this.fileToUpload = files[0];
      } else {
        alert('请上传PDF文件');
      }
      this.dragover = false;
    },
    
    async submitFile() {
      if (!this.fileToUpload) return;
      this.isUploading = true;
      
      try {
        await api.uploadDocument(this.fileToUpload);
        this.fileToUpload = null;
        this.$refs.fileInput.value = '';
        await this.fetchDocuments();
        alert('文件上传成功！后台正在处理中...');
      } catch (error) {
        console.error('文件上传失败:', error);
        alert('文件上传失败，请检查后端服务。');
      } finally {
        this.isUploading = false;
      }
    },
    
    async deleteDocument(docId) {
      if (!confirm('确定要删除这个文档吗？此操作不可恢复。')) return;
      
      try {
        await api.deleteDocument(docId);
        alert('文档删除成功!');
        await this.fetchDocuments();
      } catch (error) {
        console.error('删除文档失败:', error);
        alert(`删除失败: ${error.message || '请稍后重试'}`);
      }
    },
    
    async pushToLabelStudio(docId, alreadySynced) {
      let force = false;
      
      // 如果已经推送,询问是否重新推送
      if (alreadySynced) {
        if (!confirm('此文档已推送到 Label Studio。\n\n是否要重新推送？\n(这可能会在 Label Studio 中创建重复任务)')) {
          return;
        }
        force = true;
      }
      
      try {
        const response = await api.pushToLabelStudio(docId, force);
        const data = response.data;
        
        if (data.synced && !force) {
          alert(`文档已推送到 Label Studio\n\n任务数: ${data.task_ids?.length || 0}\n推送时间: ${data.sync_time || '未知'}`);
        } else {
          alert(`成功推送到 Label Studio!\n\n任务数: ${data.task_count}\n任务ID: ${data.task_ids?.slice(0, 5).join(', ')}${data.task_ids?.length > 5 ? '...' : ''}`);
          await this.fetchDocuments(); // 刷新列表以更新状态
        }
      } catch (error) {
        console.error('推送到 Label Studio 失败:', error);
        const errorMsg = error.response?.data?.error || error.message || '未知错误';
        alert(`推送失败: ${errorMsg}\n\n请检查:\n1. Label Studio API Key 是否已配置\n2. Label Studio 服务是否正常运行\n3. 项目 ID 是否正确`);
      }
    },
    
    async downloadRawOcrJson(docId) {
      try {
        const response = await api.getLabelStudioTasks(docId);
        this.downloadJSON(response.data, `raw_ocr_${docId}.json`);
      } catch (error) {
        console.error('下载原始OCR文件失败:', error);
        alert('下载失败，请确保文档已完成OCR处理');
      }
    },
    
    triggerCorrectionFileUpload(docId) {
      const input = this.$refs[`correctionFileInput_${docId}`];
      if (input && input[0]) {
        input[0].click();
      }
    },
    
    async handleCorrectionFileUpload(event, docId) {
      const file = event.target.files[0];
      if (!file) return;
      
      try {
        const fileContent = await this.readFileAsJSON(file);
        await api.ingestToRagflow(docId, fileContent);
        alert('校对结果已成功上传！');
        await this.fetchDocuments();
      } catch (error) {
        console.error('上传校对文件失败:', error);
        alert('上传校对文件失败: ' + (error.message || '未知错误'));
      } finally {
        event.target.value = '';
      }
    },
    
    async downloadRAGFlowPayload(docId) {
      try {
        // 这里需要后端提供专门的RAGFlow导出接口
        // 临时使用现有接口
        const response = await api.getLabelStudioTasks(docId);
        this.downloadJSON(response.data, `ragflow_payload_${docId}.json`);
        alert('RAGFlow文件已生成并下载！');
        await this.fetchDocuments();
      } catch (error) {
        console.error('生成RAGFlow文件失败:', error);
        alert('生成RAGFlow文件失败，请确保已完成校对');
      }
    },
    
    // 辅助方法
    downloadJSON(data, filename) {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    },
    
    readFileAsJSON(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            const json = JSON.parse(e.target.result);
            resolve(json);
          } catch (error) {
            reject(new Error('JSON文件格式错误'));
          }
        };
        reader.onerror = () => reject(new Error('文件读取失败'));
        reader.readAsText(file);
      });
    },
    
    isReadyForDownload(status) {
      return ['processed', 'corrected', 'ingested'].includes(status);
    },
    
    canGenerateRAG(status) {
      return ['corrected', 'ingested'].includes(status);
    },
    
    getFileName(path) {
      return path ? path.split(/[\\/]/).pop() : 'N/A';
    },
    
    getStatusText(status) {
      const statusMap = {
        'pending': '等待处理',
        'processing': '处理中',
        'processed': '已完成OCR',
        'failed': '处理失败',
        'corrected': '已校对',
        'ingested': '已入库'
      };
      return statusMap[status] || status;
    },
    
    formatDate(dateString) {
      return new Date(dateString).toLocaleString('zh-CN');
    },
    
    startPolling() {
      this.pollInterval = setInterval(() => {
        this.fetchDocuments();
      }, 5000); // 每5秒刷新一次
    },
    
    stopPolling() {
      if (this.pollInterval) {
        clearInterval(this.pollInterval);
      }
    }
  },
  
  mounted() {
    this.fetchDocuments();
    this.startPolling();
  },
  
  beforeUnmount() {
    this.stopPolling();
  }
};
</script>

<style scoped>
/* 自定义样式 */

/* 状态点 */
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.status-pending { background-color: #f59e0b; }
.status-processing { 
  background-color: #3b82f6;
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
.status-processed { background-color: #10b981; }
.status-failed { background-color: #ef4444; }
.status-corrected { background-color: #14b8a6; }
.status-ingested { background-color: #8b5cf6; }

/* 按钮样式 */
.btn {
  padding: 8px 16px;
  border-radius: 6px;
  color: white;
  font-weight: 500;
  transition: all 0.2s;
  cursor: pointer;
  border: none;
  font-size: 0.875rem;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-primary { background-color: #3b82f6; }
.btn-primary:hover { background-color: #2563eb; }
.btn-secondary { background-color: #6b7280; }
.btn-secondary:hover { background-color: #4b5563; }
.btn-danger { background-color: #ef4444; }
.btn-danger:hover { background-color: #dc2626; }
.btn-success { background-color: #22c55e; }
.btn-success:hover { background-color: #16a34a; }
.btn-info { background-color: #0ea5e9; }
.btn-info:hover { background-color: #0284c7; }

/* 徽章样式 */
.badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.25rem 0.5rem;
  border-radius: 9999px;
}

.badge-sky { 
  color: #0284c7;
  background-color: #e0f2fe;
}

.badge-teal {
  color: #0d9488;
  background-color: #ccfbf1;
}

.badge-violet {
  color: #7c3aed;
  background-color: #ede9fe;
}

/* 加载动画 */
.spinner {
  border: 2px solid #f3f3f3;
  border-top: 2px solid #3b82f6;
  border-radius: 50%;
  width: 16px;
  height: 16px;
  animation: spin 1s linear infinite;
  display: inline-block;
  margin-left: 8px;
}

.spinner-large {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #3b82f6;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 响应式调整 */
@media (max-width: 640px) {
  .btn {
    padding: 6px 12px;
    font-size: 0.75rem;
  }
}
</style>