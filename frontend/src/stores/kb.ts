// 知识库状态（Pinia）：知识库列表 + 文档的增删/上传/重建索引。
// 写操作成功后统一调 fetchKbs 刷新，保证前端与后端一致。
import { defineStore } from 'pinia'
import { http } from '../api/http'
import type { DocumentItem, KnowledgeBase } from '../api/types'

export const useKbStore = defineStore('kb', {
  state: () => ({
    kbs: [] as KnowledgeBase[],
    loading: false,
  }),
  actions: {
    async fetchKbs() {
      this.loading = true
      try {
        const { data } = await http.get('/kbs')
        this.kbs = data
      } finally {
        this.loading = false
      }
    },
    async createKb(payload: { name: string; description: string; visibility: string }) {
      await http.post('/kbs', payload)
      await this.fetchKbs()
    },
    async deleteKb(id: string) {
      await http.delete(`/kbs/${id}`)
      await this.fetchKbs()
    },
    async fetchDocuments(kbId: string): Promise<DocumentItem[]> {
      const { data } = await http.get(`/kbs/${kbId}/documents`)
      return data
    },
    // 上传文档：multipart 表单提交；接口立即返回，索引在后台异步进行，
    // 页面通过轮询文档状态展示进度
    async uploadDocument(kbId: string, file: File): Promise<DocumentItem> {
      const form = new FormData()
      form.append('file', file)
      const { data } = await http.post(`/kbs/${kbId}/documents`, form)
      return data
    },
    async deleteDocument(kbId: string, docId: string) {
      await http.delete(`/kbs/${kbId}/documents/${docId}`)
    },
    async reindexDocument(kbId: string, docId: string) {
      await http.post(`/kbs/${kbId}/documents/${docId}/reindex`)
    },
  },
})
