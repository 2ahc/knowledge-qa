<template>
  <div class="page">
    <h2>管理后台</h2>

    <el-tabs v-model="tab">
      <!-- 用量统计 -->
      <el-tab-pane label="用量统计" name="stats">
        <el-row :gutter="16">
          <el-col :span="6" v-for="card in statCards" :key="card.label">
            <el-card class="stat-card">
              <div class="stat-value">{{ card.value }}</div>
              <div class="stat-label">{{ card.label }}</div>
            </el-card>
          </el-col>
        </el-row>
        <el-row :gutter="16" style="margin-top: 16px">
          <el-col :span="14">
            <el-card>
              <template #header>近 14 天提问量</template>
              <el-table :data="stats?.daily_questions || []" empty-text="暂无数据" size="small">
                <el-table-column prop="date" label="日期" />
                <el-table-column prop="questions" label="提问数" />
                <el-table-column label="趋势">
                  <template #default="{ row }">
                    <div class="bar" :style="{ width: barWidth(row.questions) }"></div>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
          <el-col :span="10">
            <el-card>
              <template #header>切片数最多的文档</template>
              <el-table :data="stats?.top_documents || []" empty-text="暂无数据" size="small">
                <el-table-column prop="filename" label="文档" show-overflow-tooltip />
                <el-table-column prop="chunk_count" label="切片" width="70" />
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 用户管理 -->
      <el-tab-pane label="用户管理" name="users">
        <div class="tab-toolbar">
          <el-button type="primary" @click="openCreateUser">
            <el-icon><Plus /></el-icon>&nbsp;新建用户
          </el-button>
        </div>
        <el-table :data="users" v-loading="userLoading">
          <el-table-column prop="username" label="用户名" width="160" />
          <el-table-column prop="display_name" label="显示名" width="160" />
          <el-table-column label="角色" width="130">
            <template #default="{ row }">
              <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
                {{ row.role === 'admin' ? '管理员' : '普通用户' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'warning'" size="small">
                {{ row.is_active ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="240">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openEditUser(row)">编辑</el-button>
              <el-button
                size="small"
                text
                :type="row.is_active ? 'warning' : 'success'"
                :disabled="row.id === auth.user?.id"
                @click="toggleActive(row)"
              >
                {{ row.is_active ? '停用' : '启用' }}
              </el-button>
              <el-button
                size="small"
                text
                :type="row.role === 'admin' ? 'info' : 'danger'"
                :disabled="row.id === auth.user?.id"
                @click="toggleRole(row)"
              >
                {{ row.role === 'admin' ? '降为普通' : '设为管理' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 任务监控 -->
      <el-tab-pane label="任务监控" name="tasks">
        <div class="tab-toolbar">
          <el-button @click="fetchTasks">刷新</el-button>
        </div>
        <el-table :data="tasks" v-loading="taskLoading" empty-text="暂无任务">
          <el-table-column label="类型" width="150">
            <template #default="{ row }">{{ kindLabel(row.kind) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="taskStatusType(row.status)" size="small">{{ taskStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="attempts" label="尝试" width="70" />
          <el-table-column label="载荷" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ JSON.stringify(row.payload) }}</template>
          </el-table-column>
          <el-table-column label="错误" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.error" class="err-text">{{ row.error }}</span>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 用户对话框 -->
    <el-dialog v-model="userDialogVisible" :title="editingUser ? '编辑用户' : '新建用户'" width="440px">
      <el-form label-position="top">
        <el-form-item label="用户名" v-if="!editingUser" required>
          <el-input v-model="userForm.username" placeholder="登录名" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="userForm.display_name" placeholder="昵称（可选）" />
        </el-form-item>
        <el-form-item :label="editingUser ? '新密码（留空不修改）' : '密码'" :required="!editingUser">
          <el-input v-model="userForm.password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="userForm.role">
            <el-radio value="user">普通用户</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingUser" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// 管理后台（仅管理员）：用量统计 / 用户管理 / 任务监控 三个标签页。
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { http } from '../api/http'
import { useAuthStore } from '../stores/auth'
import type { User } from '../api/types'

const auth = useAuthStore()
const tab = ref('stats')

// ---- 用量统计 ----
const stats = ref<any>(null)
// 顶部四张统计卡片
const statCards = computed(() => [
  { label: '用户数', value: stats.value?.user_count ?? '—' },
  { label: '知识库 / 文档', value: `${stats.value?.kb_count ?? '—'} / ${stats.value?.doc_count ?? '—'}` },
  { label: '总提问数', value: stats.value?.question_count ?? '—' },
  { label: '平均响应延迟', value: `${stats.value?.avg_latency_ms ?? '—'} ms` },
])
// 趋势条形图宽度：按 14 天里的最大提问量等比缩放
function barWidth(n: number) {
  const max = Math.max(1, ...(stats.value?.daily_questions || []).map((d: any) => d.questions))
  return Math.round((n / max) * 100) + '%'
}

// ---- 用户管理（创建/编辑/启停/角色切换）----
const users = ref<User[]>([])
const userLoading = ref(false)
const userDialogVisible = ref(false)
const editingUser = ref<User | null>(null)
const savingUser = ref(false)
const userForm = ref({ username: '', display_name: '', password: '', role: 'user' })

async function fetchUsers() {
  userLoading.value = true
  try {
    const { data } = await http.get('/users')
    users.value = data
  } finally {
    userLoading.value = false
  }
}
function openCreateUser() {
  editingUser.value = null
  userForm.value = { username: '', display_name: '', password: '', role: 'user' }
  userDialogVisible.value = true
}
function openEditUser(u: User) {
  editingUser.value = u
  userForm.value = { username: u.username, display_name: u.display_name, password: '', role: u.role }
  userDialogVisible.value = true
}
async function saveUser() {
  savingUser.value = true
  try {
    if (editingUser.value) {
      // 编辑：密码留空则不修改
      const body: any = { display_name: userForm.value.display_name, role: userForm.value.role }
      if (userForm.value.password) body.password = userForm.value.password
      await http.patch(`/users/${editingUser.value.id}`, body)
      ElMessage.success('已更新')
    } else {
      await http.post('/users', userForm.value)
      ElMessage.success('已创建')
    }
    userDialogVisible.value = false
    await fetchUsers()
  } finally {
    savingUser.value = false
  }
}
async function toggleActive(u: User) {
  await http.patch(`/users/${u.id}`, { is_active: !u.is_active })
  await fetchUsers()
}
async function toggleRole(u: User) {
  await http.patch(`/users/${u.id}`, { role: u.role === 'admin' ? 'user' : 'admin' })
  await fetchUsers()
}

// ---- 任务监控（查看异步队列：索引/重建/评测的执行情况与失败原因）----
const tasks = ref<any[]>([])
const taskLoading = ref(false)
async function fetchTasks() {
  taskLoading.value = true
  try {
    const { data } = await http.get('/admin/tasks')
    tasks.value = data
  } finally {
    taskLoading.value = false
  }
}
function kindLabel(k: string) {
  return {
    'document.index': '文档索引',
    'document.reindex': '重建索引',
    'eval.run': '评测运行',
  }[k] || k
}
function taskStatusLabel(s: string) {
  return { queued: '排队中', running: '运行中', done: '已完成', failed: '失败' }[s] || s
}
function taskStatusType(s: string): 'info' | 'warning' | 'success' | 'danger' {
  return ({ queued: 'info', running: 'warning', done: 'success', failed: 'danger' } as any)[s]
}

function formatTime(s: string) {
  const d = new Date(s)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(async () => {
  const { data } = await http.get('/admin/stats')
  stats.value = data
  fetchUsers()
  fetchTasks()
})
</script>

<style scoped>
h2 {
  margin: 0 0 20px;
  font-family: var(--font-serif);
  font-size: 20px;
  color: var(--ink);
  letter-spacing: 0.04em;
}
.stat-card {
  text-align: center;
}
.stat-value {
  font-size: 26px;
  font-weight: 800;
  color: var(--brand);
}
.stat-label {
  color: var(--sub);
  font-size: 13px;
  margin-top: 6px;
}
.bar {
  height: 10px;
  background: var(--brand);
  border-radius: 5px;
  min-width: 2px;
}
.tab-toolbar {
  margin-bottom: 12px;
  display: flex;
  justify-content: flex-end;
}
.err-text {
  color: var(--ink-2);
  font-size: 12px;
}
</style>
