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
