<template>
  <div class="kb-page">
    <!-- 左栏：知识库列表（当前墨黑加粗 + 左侧竖线） -->
    <aside class="kb-side">
      <div class="group-label">知识库</div>
      <div class="kb-list">
        <div
          v-for="kbItem in kb.kbs"
          :key="kbItem.id"
          class="kb-item"
          :class="{ active: kbItem.id === selectedKbId }"
          @click="selectKb(kbItem.id)"
        >
          <span class="kb-name">{{ kbItem.name }}</span>
          <el-dropdown
            v-if="canManage(kbItem)"
            class="kb-more"
            @command="(cmd: string) => onKbCommand(cmd, kbItem)"
          >
            <el-icon @click.stop><MoreFilled /></el-icon>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="members">成员管理</el-dropdown-item>
                <el-dropdown-item command="delete">删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div v-if="!kb.kbs.length && !kb.loading" class="kb-empty">还没有知识库</div>
      </div>
      <button class="create-btn" @click="createVisible = true">
        <el-icon><Plus /></el-icon>新建知识库
      </button>
    </aside>

    <!-- 右栏：选中库的详情与文档 -->
    <section class="kb-main">
      <div v-if="!selectedKb" class="kb-placeholder">
        <p class="ph-title">从左侧选择一个知识库</p>
        <p class="ph-sub">查看文档、上传资料、管理成员</p>
      </div>

      <template v-else>
        <header class="kb-head">
          <h2 class="kb-title">{{ selectedKb.name }}</h2>
          <div class="kb-sub">
            {{ visLabel(selectedKb.visibility) }} · {{ selectedKb.doc_count }} 篇文档
            · {{ selectedKb.chunk_count }} 个切片
          </div>
          <p v-if="selectedKb.description" class="kb-desc">{{ selectedKb.description }}</p>
        </header>

        <div class="doc-toolbar">
          <span class="doc-label">文档</span>
          <el-upload
            :show-file-list="false"
            :before-upload="onUpload"
            accept=".pdf,.docx,.xlsx,.md,.txt"
            multiple
          >
            <el-button size="small" plain>上传文档</el-button>
          </el-upload>
        </div>

        <div class="doc-list" v-loading="docLoading">
          <div v-if="!documents.length && !docLoading" class="doc-empty">
            暂无文档，上传一份试试
          </div>
          <div v-for="doc in documents" :key="doc.id" class="doc-row">
            <span class="doc-name" :title="doc.filename">{{ doc.filename }}</span>
            <span class="doc-status" :class="'st-' + doc.status">{{ statusLabel(doc.status) }}</span>
            <span class="doc-num">{{ doc.chunk_count }} 切片</span>
            <span class="doc-num">{{ formatSize(doc.size_bytes) }}</span>
            <span class="doc-ops">
              <button class="op-link" @click="reindex(doc)">重建索引</button>
              <button class="op-link" @click="removeDoc(doc)">删除</button>
            </span>
            <div v-if="doc.error" class="doc-err">{{ doc.error }}</div>
          </div>
        </div>
      </template>
    </section>

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
            <span>{{ row.role === 'editor' ? '编辑' : '查看' }}</span>
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
// 知识库管理页：左栏知识库列表 + 右栏选中库详情（文档行列表、成员管理、新建）。
// 文档索引是异步的，页面用 3 秒轮询刷新处于处理中的文档状态。
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox, type UploadRawFile } from 'element-plus'
import { MoreFilled, Plus } from '@element-plus/icons-vue'
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

const selectedKb = computed(() => kb.kbs.find((k) => k.id === selectedKbId.value) || null)

let pollTimer: number | undefined

// 是否可管理该库（删除/成员管理）：管理员或创建者
function canManage(item: KnowledgeBase) {
  return auth.isAdmin || auth.user?.id === item.owner_id
}

function visLabel(v: string) {
  return { private: '私有', shared: '共享', public: '公开' }[v] || v
}
// 状态用纯文字三档墨色表达，不用彩色标签
function statusLabel(s: string) {
  return { pending: '排队中', parsing: '解析中', embedding: '向量化中', done: '已完成', failed: '失败' }[s] || s
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
    // 用户点"取消"会 reject：try/catch 安静返回，避免未处理的 rejection
    try {
      await ElMessageBox.confirm(`删除知识库「${item.name}」？其所有文档与向量将一并删除。`, '危险操作', {
        type: 'warning',
      })
    } catch {
      return
    }
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
  try {
    await ElMessageBox.confirm(`删除文档「${doc.filename}」？`, '删除文档', { type: 'warning' })
  } catch {
    return // 用户取消
  }
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
  // 默认选中第一个知识库，右栏不留空
  if (kb.kbs.length && !selectedKbId.value) {
    await selectKb(kb.kbs[0].id)
  }
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
.kb-page {
  display: flex;
  height: 100%;
}
/* 左栏 */
.kb-side {
  width: 260px;
  flex: none;
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  padding: 22px 14px;
}
.group-label {
  font-size: 12px;
  color: var(--ink-3);
  letter-spacing: 0.2em;
  padding: 0 12px 10px;
}
.kb-list {
  flex: 1;
  overflow-y: auto;
}
.kb-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 12px 9px 14px;
  border-left: 2px solid transparent;
  cursor: pointer;
  transition: border-color 0.2s;
}
/* 当前库：墨黑加粗 + 左侧墨黑竖线 */
.kb-item.active {
  border-left-color: var(--ink);
}
.kb-item.active .kb-name {
  color: var(--ink);
  font-weight: 600;
}
.kb-name {
  font-size: 13px;
  color: var(--ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kb-more {
  color: var(--ink-3);
  display: none;
}
.kb-item:hover .kb-more {
  display: inline-flex;
}
.kb-more:hover {
  color: var(--ink);
}
.kb-empty {
  color: var(--ink-3);
  font-size: 12px;
  padding: 10px 14px;
}
/* 新建：墨黑小按钮 */
.create-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 14px;
  padding: 9px 0;
  background: var(--ink);
  color: #fdfcfa;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  letter-spacing: 0.08em;
  cursor: pointer;
  transition: opacity 0.2s;
}
.create-btn:hover {
  opacity: 0.82;
}
/* 右栏 */
.kb-main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 36px 48px;
}
.kb-placeholder {
  margin-top: 16vh;
  text-align: center;
}
.ph-title {
  font-family: var(--font-serif);
  font-size: 18px;
  color: var(--ink-2);
  letter-spacing: 0.1em;
  margin: 0 0 10px;
}
.ph-sub {
  font-size: 13px;
  color: var(--ink-3);
  margin: 0;
}
.kb-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: 0.04em;
}
.kb-sub {
  margin-top: 8px;
  font-size: 13px;
  color: var(--ink-3);
  font-variant-numeric: tabular-nums;
}
.kb-desc {
  margin: 14px 0 0;
  font-size: 13px;
  color: var(--ink-2);
  line-height: 1.8;
  max-width: 640px;
}
.doc-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 40px 0 6px;
}
.doc-label {
  font-size: 13px;
  color: var(--ink-3);
  letter-spacing: 0.2em;
}
/* 文档行：极细线分隔，不用卡片与表格框 */
.doc-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 84px 90px 80px 130px;
  align-items: center;
  gap: 12px;
  padding: 13px 4px;
  border-bottom: 1px solid var(--line);
}
.doc-row:hover .op-link {
  opacity: 1;
}
.doc-name {
  font-size: 13px;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 状态：纯文字三档墨色 */
.doc-status {
  font-size: 12px;
  color: var(--ink-2);
}
.doc-status.st-done {
  color: var(--ink);
}
.doc-status.st-pending,
.doc-status.st-parsing,
.doc-status.st-embedding {
  color: var(--ink-3);
}
.doc-num {
  font-size: 12px;
  color: var(--ink-3);
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.doc-ops {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
.op-link {
  background: none;
  border: none;
  padding: 0;
  font-size: 12px;
  color: var(--ink-2);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s, color 0.2s;
}
.op-link:hover {
  color: var(--ink);
}
.doc-err {
  grid-column: 1 / -1;
  font-size: 12px;
  color: var(--ink-3);
}
.doc-empty {
  padding: 40px 0;
  text-align: center;
  color: var(--ink-3);
  font-size: 13px;
}
.member-add {
  display: flex;
  gap: 10px;
  align-items: center;
}
</style>
