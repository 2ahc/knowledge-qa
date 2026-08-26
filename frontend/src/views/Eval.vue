<template>
  <div class="page">
    <h2>问答评测</h2>
    <el-tabs v-model="tab">
      <!-- 数据集 -->
      <el-tab-pane label="📋 评测集" name="datasets">
        <div class="tab-toolbar">
          <el-button type="primary" @click="openCreateDs">
            <el-icon><Plus /></el-icon>&nbsp;新建评测集
          </el-button>
        </div>
        <el-table :data="datasets" v-loading="dsLoading" empty-text="暂无评测集">
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column label="题目数" width="90">
            <template #default="{ row }">{{ row.items.length }}</template>
          </el-table-column>
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="170">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="viewDs(row)">查看</el-button>
              <el-button size="small" text type="danger" @click="removeDs(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 运行 -->
      <el-tab-pane label="🚀 评测运行" name="runs">
        <div class="tab-toolbar">
          <el-button @click="fetchRuns">刷新</el-button>
          <el-button type="primary" :disabled="!datasets.length || !kb.kbs.length" @click="openCreateRun">
            <el-icon><VideoPlay /></el-icon>&nbsp;发起评测
          </el-button>
        </div>
        <el-table :data="runs" v-loading="runLoading" empty-text="暂无评测运行">
          <el-table-column label="数据集" min-width="130">
            <template #default="{ row }">{{ dsName(row.dataset_id) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="命中率" width="90">
            <template #default="{ row }">
              {{ pct(row.metrics?.retrieval_precision) }}
            </template>
          </el-table-column>
          <el-table-column label="关键词" width="90">
            <template #default="{ row }">{{ pct(row.metrics?.avg_keyword_rate) }}</template>
          </el-table-column>
          <el-table-column label="忠实性" width="80">
            <template #default="{ row }">{{ row.metrics?.avg_faithfulness ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="相关性" width="80">
            <template #default="{ row }">{{ row.metrics?.avg_relevance ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="时间" width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="viewRun(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建数据集 -->
    <el-dialog v-model="dsDialogVisible" title="新建评测集" width="640px">
      <el-form label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="dsForm.name" placeholder="例如：产品问答评测 v1" />
        </el-form-item>
        <el-form-item label="评测项（JSONL 格式，每行一个）">
          <el-input
            v-model="dsForm.jsonl"
            type="textarea"
            :rows="8"
            placeholder='{"question": "公司哪年成立？", "expect_keywords": ["2020"], "expect_doc": "公司介绍"}'
          />
          <div class="hint">
            question 必填；expect_keywords 用于关键词命中率；expect_doc 用于检索命中判断（文档名子串）。
            也可以上传 .jsonl 文件：
          </div>
          <el-upload :show-file-list="false" accept=".jsonl,.json,.txt" :before-upload="onDsFile">
            <el-button size="small" plain style="margin-top: 8px">选择文件</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dsDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dsSaving" @click="saveDs">创建</el-button>
      </template>
    </el-dialog>

    <!-- 查看数据集 -->
    <el-dialog v-model="viewDsVisible" :title="`评测集：${viewingDs?.name || ''}`" width="700px">
      <el-table :data="viewingDs?.items || []" max-height="420" size="small">
        <el-table-column prop="question" label="问题" min-width="220" show-overflow-tooltip />
        <el-table-column label="期望关键词" width="180">
          <template #default="{ row }">{{ (row.expect_keywords || []).join('、') || '—' }}</template>
        </el-table-column>
        <el-table-column prop="expect_doc" label="期望文档" width="150" show-overflow-tooltip />
      </el-table>
    </el-dialog>

    <!-- 发起评测 -->
    <el-dialog v-model="runDialogVisible" title="发起评测" width="460px">
      <el-form label-position="top">
        <el-form-item label="评测集" required>
          <el-select v-model="runForm.dataset_id" style="width: 100%">
            <el-option v-for="d in datasets" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="知识库（可多选）" required>
          <el-select v-model="runForm.kb_ids" multiple style="width: 100%">
            <el-option v-for="k in kb.kbs" :key="k.id" :label="k.name" :value="k.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="runDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="runSaving" @click="saveRun">开始</el-button>
      </template>
    </el-dialog>

    <!-- 运行详情 -->
    <el-dialog v-model="viewRunVisible" title="评测详情" width="860px">
      <template v-if="runDetail">
        <el-descriptions :column="4" border size="small" style="margin-bottom: 16px">
          <el-descriptions-item label="题目数">{{ runDetail.metrics?.total }}</el-descriptions-item>
          <el-descriptions-item label="检索命中率">{{ pct(runDetail.metrics?.retrieval_precision) }}</el-descriptions-item>
          <el-descriptions-item label="忠实性均分">{{ runDetail.metrics?.avg_faithfulness ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="相关性均分">{{ runDetail.metrics?.avg_relevance ?? '—' }}</el-descriptions-item>
        </el-descriptions>
        <el-table :data="runDetail.results" max-height="420" size="small">
          <el-table-column prop="question" label="问题" min-width="180" show-overflow-tooltip />
          <el-table-column label="检索命中" width="90">
            <template #default="{ row }">
              <el-tag v-if="!row.expect_doc" size="small" type="info">未设置</el-tag>
              <el-tag v-else :type="row.retrieval_hit ? 'success' : 'danger'" size="small">
                {{ row.retrieval_hit ? '命中' : '未命中' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="关键词" width="100">
            <template #default="{ row }">{{ pct(row.keyword_rate) }}</template>
          </el-table-column>
          <el-table-column label="评分" width="90">
            <template #default="{ row }">
              {{ row.scores ? `${row.scores.faithfulness}/${row.scores.relevance}` : '—' }}
            </template>
          </el-table-column>
          <el-table-column prop="answer" label="回答" min-width="220" show-overflow-tooltip />
        </el-table>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// 问答评测页：评测集（JSONL 题目）+ 评测运行（异步任务，轮询进度）。
// 指标说明：检索命中率=期望文档被召回的比例；关键词=期望关键词出现在回答中的比例；
// 忠实性/相关性=LLM 裁判 1-5 分。
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox, type UploadRawFile } from 'element-plus'
import { Plus, VideoPlay } from '@element-plus/icons-vue'
import { http } from '../api/http'
import { useKbStore } from '../stores/kb'

const kb = useKbStore()
const tab = ref('datasets')

const datasets = ref<any[]>([])
const dsLoading = ref(false)
const dsDialogVisible = ref(false)
const dsSaving = ref(false)
const dsForm = ref({ name: '', jsonl: '' })
const viewDsVisible = ref(false)
const viewingDs = ref<any>(null)

const runs = ref<any[]>([])
const runLoading = ref(false)
const runDialogVisible = ref(false)
const runSaving = ref(false)
const runForm = ref({ dataset_id: '', kb_ids: [] as string[] })
const viewRunVisible = ref(false)
const runDetail = ref<any>(null)

let pollTimer: number | undefined

function formatTime(s: string) {
  const d = new Date(s)
  return `${d.getMonth() + 1}-${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
function pct(v: number | null | undefined) {
  return v === null || v === undefined ? '—' : (v * 100).toFixed(0) + '%'
}
function statusLabel(s: string) {
  return { queued: '排队中', running: '运行中', done: '已完成', failed: '失败' }[s] || s
}
function statusType(s: string): 'info' | 'warning' | 'success' | 'danger' {
  return ({ queued: 'info', running: 'warning', done: 'success', failed: 'danger' } as any)[s]
}
function dsName(id: string) {
  return datasets.value.find((d) => d.id === id)?.name || id.slice(0, 8)
}

async function fetchDatasets() {
  dsLoading.value = true
  try {
    const { data } = await http.get('/eval/datasets')
    datasets.value = data
  } finally {
    dsLoading.value = false
  }
}
async function fetchRuns() {
  runLoading.value = true
  try {
    const { data } = await http.get('/eval/runs')
    runs.value = data
  } finally {
    runLoading.value = false
  }
}

function openCreateDs() {
  dsForm.value = { name: '', jsonl: '' }
  dsDialogVisible.value = true
}
// 选择 .jsonl 文件：本地读取文本填入输入框（不直接上传，便于用户预览修改）
function onDsFile(file: UploadRawFile) {
  const reader = new FileReader()
  reader.onload = () => {
    dsForm.value.jsonl = String(reader.result || '')
  }
  reader.readAsText(file)
  return false
}
// 保存评测集：逐行解析 JSONL，任何一行非法都中止并提示行号
async function saveDs() {
  if (!dsForm.value.name.trim()) {
    ElMessage.warning('请输入名称')
    return
  }
  const items: any[] = []
  for (const [i, line] of dsForm.value.jsonl.split('\n').entries()) {
    const t = line.trim()
    if (!t) continue
    try {
      items.push(JSON.parse(t))
    } catch {
      ElMessage.error(`第 ${i + 1} 行不是合法 JSON`)
      return
    }
  }
  if (!items.length) {
    ElMessage.warning('请至少填写一条评测项')
    return
  }
  dsSaving.value = true
  try {
    await http.post('/eval/datasets', { name: dsForm.value.name, items })
    ElMessage.success('创建成功')
    dsDialogVisible.value = false
    await fetchDatasets()
  } finally {
    dsSaving.value = false
  }
}
function viewDs(ds: any) {
  viewingDs.value = ds
  viewDsVisible.value = true
}
async function removeDs(ds: any) {
  await ElMessageBox.confirm(`删除评测集「${ds.name}」？`, '删除', { type: 'warning' }).catch(() =>
    Promise.reject()
  )
  await http.delete(`/eval/datasets/${ds.id}`)
  await fetchDatasets()
}

function openCreateRun() {
  runForm.value = { dataset_id: datasets.value[0]?.id || '', kb_ids: kb.kbs.length ? [kb.kbs[0].id] : [] }
  runDialogVisible.value = true
}
async function saveRun() {
  if (!runForm.value.dataset_id || !runForm.value.kb_ids.length) {
    ElMessage.warning('请选择数据集和知识库')
    return
  }
  runSaving.value = true
  try {
    await http.post('/eval/runs', runForm.value)
    ElMessage.success('评测任务已提交')
    runDialogVisible.value = false
    tab.value = 'runs'
    await fetchRuns()
  } finally {
    runSaving.value = false
  }
}
async function viewRun(run: any) {
  const { data } = await http.get(`/eval/runs/${run.id}`)
  runDetail.value = data
  viewRunVisible.value = true
}

onMounted(async () => {
  await Promise.all([fetchDatasets(), fetchRuns(), kb.fetchKbs()])
  // 有评测在排队/运行时每 4 秒刷新一次，让进度实时可见
  pollTimer = window.setInterval(async () => {
    if (runs.value.some((r) => ['queued', 'running'].includes(r.status))) await fetchRuns()
  }, 4000)
})
// 离开页面清理轮询
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
h2 {
  margin: 0 0 16px;
  font-size: 18px;
}
.tab-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 12px;
}
.hint {
  font-size: 12px;
  color: var(--sub);
  margin-top: 6px;
  line-height: 1.6;
}
</style>
