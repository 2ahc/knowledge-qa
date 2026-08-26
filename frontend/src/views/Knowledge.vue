<template>
  <div class="page">
    <div class="toolbar">
      <h2>知识库管理</h2>
      <el-button type="primary" @click="createVisible = true">
        <el-icon><Plus /></el-icon>&nbsp;新建知识库
      </el-button>
    </div>

    <el-row :gutter="16">
      <el-col v-for="kbItem in kb.kbs" :key="kbItem.id" :span="8">
        <el-card
          class="kb-card"
          :class="{ selected: kbItem.id === selectedKbId }"
          shadow="hover"
          @click="selectKb(kbItem.id)"
        >
          <div class="kb-head">
            <span class="kb-name">📚 {{ kbItem.name }}</span>
            <el-dropdown @command="(cmd: string) => onKbCommand(cmd, kbItem)">
              <el-icon class="kb-more"><MoreFilled /></el-icon>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="members" v-if="canManage(kbItem)">成员管理</el-dropdown-item>
                  <el-dropdown-item command="delete" v-if="canManage(kbItem)">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <div class="kb-desc">{{ kbItem.description || '暂无描述' }}</div>
          <div class="kb-meta">
            <el-tag size="small" :type="visType(kbItem.visibility)">{{ visLabel(kbItem.visibility) }}</el-tag>
            <span>{{ kbItem.doc_count }} 篇文档</span>
            <span>{{ kbItem.chunk_count }} 个切片</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-empty v-if="!kb.kbs.length && !kb.loading" description="还没有知识库，点击右上角新建" />

    <!-- 文档面板 -->
    <el-card v-if="selectedKbId" class="doc-panel">
      <template #header>
        <div class="doc-head">
          <span>📄 文档列表</span>
          <el-upload
            :show-file-list="false"
            :before-upload="onUpload"
            accept=".pdf,.docx,.xlsx,.md,.txt"
            multiple
          >
            <el-button type="primary" plain>
              <el-icon><Upload /></el-icon>&nbsp;上传文档（PDF/Word/Excel/Markdown/TXT）
            </el-button>
          </el-upload>
        </div>
      </template>
      <el-table :data="documents" v-loading="docLoading" empty-text="暂无文档，上传一份试试">
        <el-table-column prop="filename" label="文件名" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="切片数" width="90" />
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ formatSize(row.size_bytes) }}</template>
        </el-table-column>
        <el-table-column label="错误信息" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.error" class="err-text">{{ row.error }}</span>
            <span v-else class="sub-text">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="reindex(row)">重建索引</el-button>
            <el-button size="small" text type="danger" @click="removeDoc(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 成员管理对话框 -->
    <el-dialog v-model="membersVisible" :title="`成员管理：${membersKb?.name || ''}`" width="560px">
      <el-alert
        v-if="membersKb?.visibility !== 'shared'"
        type="info"
        :closable="false"
        show-icon
        title="仅「共享」可见性的知识库会按成员授权；私有库只有创建者可见，公开库所有人可见。"
        style="margin-bottom: 14px"
      />
      <div class="member-add">
        <el-select
          v-model="memberForm.user_id"
          filterable
          remote
          reserve-keyword
          placeholder="搜索用户名/昵称添加成员"
          :remote-method="searchUsers"
          :loading="userSearching"
          style="flex: 1"
        >
          <el-option v-for="u in userOptions" :key="u.id" :label="`${u.display_name}（${u.username}）`" :value="u.id" />
        </el-select>
        <el-radio-group v-model="memberForm.role">
          <el-radio value="viewer">查看</el-radio>
          <el-radio value="editor">编辑</el-radio>
        </el-radio-group>
        <el-button type="primary" :disabled="!memberForm.user_id" :loading="memberSaving" @click="addMember">
          添加
        </el-button>
      </div>
      <el-table :data="members" v-loading="membersLoading" empty-text="暂无成员" style="margin-top: 14px">
        <el-table-column prop="display_name" label="显示名" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.role === 'editor' ? 'warning' : 'info'">
              {{ row.role === 'editor' ? '编辑' : '查看' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button size="small" text type="danger" @click="removeMember(row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 新建知识库对话框 -->
    <el-dialog v-model="createVisible" title="新建知识库" width="460px">
      <el-form label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="newKb.name" placeholder="例如：产品知识库" maxlength="60" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newKb.description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
        <el-form-item label="可见性">
          <el-radio-group v-model="newKb.visibility">
            <el-radio value="private">私有（仅自己）</el-radio>
            <el-radio value="shared">共享（指定成员）</el-radio>
            <el-radio value="public">公开（所有人）</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createKb">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// 知识库管理页：知识库卡片列表 + 选中库的文档面板 + 成员管理/新建对话框。
// 文档索引是异步的，页面用 3 秒轮询刷新处于处理中的文档状态。
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox, type UploadRawFile } from 'element-plus'
import { MoreFilled, Plus, Upload } from '@element-plus/icons-vue'
import { http } from '../api/http'
import { useKbStore } from '../stores/kb'
import { useAuthStore } from '../stores/auth'
import type { DocumentItem, KnowledgeBase } from '../api/types'

const kb = useKbStore()
const auth = useAuthStore()

const selectedKbId = ref<string | null>(null)
const documents = ref<DocumentItem[]>([])
const docLoading = ref(false)
const createVisible = ref(false)
const creating = ref(false)
const newKb = ref({ name: '', description: '', visibility: 'private' })

let pollTimer: number | undefined

// 是否可管理该库（删除/成员管理）：管理员或创建者
function canManage(item: KnowledgeBase) {
  return auth.isAdmin || auth.user?.id === item.owner_id
}

function visLabel(v: string) {
  return { private: '私有', shared: '共享', public: '公开' }[v] || v
}
function visType(v: string): 'info' | 'warning' | 'success' {
  return v === 'public' ? 'success' : v === 'shared' ? 'warning' : 'info'
}
function statusLabel(s: string) {
  return { pending: '排队中', parsing: '解析中', embedding: '向量化中', done: '已完成', failed: '失败' }[s] || s
}
function statusType(s: string): 'info' | 'warning' | 'success' | 'danger' | 'primary' {
  return { pending: 'info', parsing: 'warning', embedding: 'primary', done: 'success', failed: 'danger' }[
    s
  ] as any
}
function formatSize(n: number) {
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1024 / 1024).toFixed(1) + ' MB'
}

async function selectKb(id: string) {
  selectedKbId.value = id
  await refreshDocs()
}

async function refreshDocs() {
  if (!selectedKbId.value) return
  docLoading.value = true
  try {
    documents.value = await kb.fetchDocuments(selectedKbId.value)
  } finally {
    docLoading.value = false
  }
}

async function createKb() {
  if (!newKb.value.name.trim()) {
    ElMessage.warning('请输入知识库名称')
    return
  }
  creating.value = true
  try {
    await kb.createKb(newKb.value)
    ElMessage.success('创建成功')
    createVisible.value = false
    newKb.value = { name: '', description: '', visibility: 'private' }
  } finally {
    creating.value = false
  }
}

async function onKbCommand(cmd: string, item: KnowledgeBase) {
  if (cmd === 'members') {
    await openMembers(item)
  } else if (cmd === 'delete') {
    await ElMessageBox.confirm(`删除知识库「${item.name}」？其所有文档与向量将一并删除。`, '危险操作', {
      type: 'warning',
    }).catch(() => Promise.reject())
    await kb.deleteKb(item.id)
    if (selectedKbId.value === item.id) {
      selectedKbId.value = null
      documents.value = []
    }
    ElMessage.success('已删除')
  }
}

// 上传文档：before-upload 钩子返回 false 表示手动接管上传（走自己的 axios）
async function onUpload(file: UploadRawFile) {
  if (!selectedKbId.value) return false
  try {
    await kb.uploadDocument(selectedKbId.value, file)
    ElMessage.success(`已上传「${file.name}」，开始索引`)
    await refreshDocs()
    await kb.fetchKbs()
  } catch {
    /* 错误提示由 axios 拦截器统一处理 */
  }
  return false
}

async function reindex(doc: DocumentItem) {
  if (!selectedKbId.value) return
  await kb.reindexDocument(selectedKbId.value, doc.id)
  ElMessage.success('已提交重建任务')
  await refreshDocs()
}

async function removeDoc(doc: DocumentItem) {
  if (!selectedKbId.value) return
  await ElMessageBox.confirm(`删除文档「${doc.filename}」？`, '删除文档', { type: 'warning' }).catch(() =>
    Promise.reject()
  )
  await kb.deleteDocument(selectedKbId.value, doc.id)
  await refreshDocs()
  await kb.fetchKbs()
}

// ---- 成员管理（仅共享库按成员授权，见对话框内的说明）----
const membersVisible = ref(false)
const membersKb = ref<KnowledgeBase | null>(null)
const members = ref<any[]>([])
const membersLoading = ref(false)
const memberSaving = ref(false)
const memberForm = ref({ user_id: '', role: 'viewer' })
const userOptions = ref<any[]>([])
const userSearching = ref(false)

async function openMembers(item: KnowledgeBase) {
  membersKb.value = item
  membersVisible.value = true
  memberForm.value = { user_id: '', role: 'viewer' }
  await refreshMembers()
  searchUsers('')
}
async function refreshMembers() {
  if (!membersKb.value) return
  membersLoading.value = true
  try {
    const { data } = await http.get(`/kbs/${membersKb.value.id}/members`)
    members.value = data
  } finally {
    membersLoading.value = false
  }
}
// 远程搜索用户（供添加成员选人；排除自己）
async function searchUsers(q: string) {
  userSearching.value = true
  try {
    const { data } = await http.get('/users/search', { params: { q } })
    userOptions.value = data.filter((u: any) => u.id !== auth.user?.id)
  } finally {
    userSearching.value = false
  }
}
async function addMember() {
  if (!membersKb.value || !memberForm.value.user_id) return
  memberSaving.value = true
  try {
    await http.post(`/kbs/${membersKb.value.id}/members`, memberForm.value)
    ElMessage.success('已添加成员')
    memberForm.value.user_id = ''
    await refreshMembers()
  } finally {
    memberSaving.value = false
  }
}
async function removeMember(row: any) {
  if (!membersKb.value) return
  await http.delete(`/kbs/${membersKb.value.id}/members/${row.user_id}`)
  ElMessage.success('已移除')
  await refreshMembers()
}

onMounted(async () => {
  await kb.fetchKbs()
  // 轮询文档状态：只要有文档还在排队/解析/向量化，每 3 秒刷新一次，
  // 让索引进度实时可见；全部完成后轮询自动变为空操作
  pollTimer = window.setInterval(async () => {
    if (!selectedKbId.value) return
    const busy = documents.value.some((d) => ['pending', 'parsing', 'embedding'].includes(d.status))
    if (busy) {
      documents.value = await kb.fetchDocuments(selectedKbId.value)
      await kb.fetchKbs()
    }
  }, 3000)
})

// 离开页面时清理轮询定时器
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.toolbar h2 {
  margin: 0;
  font-size: 18px;
}
.kb-card {
  cursor: pointer;
  margin-bottom: 16px;
  transition: border-color 0.15s;
}
.kb-card.selected {
  border-color: var(--brand);
}
.kb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.kb-name {
  font-weight: 700;
}
.kb-more {
  color: var(--sub);
  cursor: pointer;
}
.kb-desc {
  color: var(--sub);
  font-size: 12px;
  margin: 8px 0;
  height: 32px;
  overflow: hidden;
}
.kb-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--sub);
}
.member-add {
  display: flex;
  gap: 10px;
  align-items: center;
}
.doc-panel {
  margin-top: 8px;
}
.doc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 700;
}
.err-text {
  color: #e5484d;
  font-size: 12px;
}
.sub-text {
  color: var(--sub);
}
</style>
