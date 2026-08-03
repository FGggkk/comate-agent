<template>
  <div>
    <div class="page-head">
      <div>
        <div class="page-title">公司制度</div>
        <div class="page-sub">上传电子版制度，索引成功后由管理员发布</div>
      </div>
      <button class="btn-gold" @click="openUpload">上传制度</button>
    </div>

    <div class="knowledge-toolbar">
      <div class="tabs" aria-label="制度状态筛选">
        <button v-for="tab in statusTabs" :key="tab.key" :class="['tab-filter', status === tab.key ? 'active' : '']" @click="switchStatus(tab.key)">
          {{ tab.label }}
        </button>
      </div>
      <span class="status-note">仅“已发布”且已生效的资料可被用户问答检索</span>
    </div>

    <div v-if="notice" :class="['notice', notice.type]">{{ notice.text }}</div>

    <div class="card table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>制度</th>
            <th>版本</th>
            <th>生效日期</th>
            <th>分片</th>
            <th>状态</th>
            <th>更新时间</th>
            <th class="actions-head">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td>
              <b>{{ item.title }}</b>
              <div v-if="item.category || item.file_name" class="source-meta">{{ item.category || '未分类' }} · {{ item.file_name }}</div>
              <div v-if="item.error_message" class="error-text">{{ item.error_message }}</div>
            </td>
            <td class="num">{{ item.version }}</td>
            <td class="num dim">{{ formatDate(item.effective_at) }}</td>
            <td class="num">{{ item.chunk_count ?? '—' }}</td>
            <td><span :class="['badge', statusClass(item.status)]">{{ statusLabel(item.status) }}</span></td>
            <td class="num dim">{{ formatDate(item.updated_at, true) }}</td>
            <td class="row-actions">
              <button class="row-btn" @click="showDetail(item)">查看</button>
              <button v-if="item.status === 'draft'" class="row-btn moss" :disabled="actingId === item.id" @click="publish(item)">发布</button>
              <button v-if="item.status === 'published' || item.status === 'draft' || item.status === 'failed'" class="row-btn" :disabled="actingId === item.id" @click="reindex(item)">重建</button>
              <button v-if="item.status === 'published' || item.status === 'draft' || item.status === 'failed'" class="row-btn danger" :disabled="actingId === item.id" @click="archive(item)">下架</button>
            </td>
          </tr>
          <tr v-if="!loading && !items.length">
            <td colspan="7" class="empty-row">暂无制度资料</td>
          </tr>
        </tbody>
      </table>
      <div v-if="loading" class="table-loading">正在加载制度资料…</div>
    </div>

    <div v-if="total > 0" class="pagination">
      <span class="num">共 {{ total }} 条</span>
      <div>
        <button class="btn-ghost" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <span class="num page-no">{{ page }}</span>
        <button class="btn-ghost" :disabled="page * size >= total" @click="goPage(page + 1)">下一页</button>
      </div>
    </div>

    <section class="jobs-section">
      <div class="jobs-head">
        <div>
          <h2>索引任务</h2>
          <p>上传和重建均会生成记录；失败后可重新索引。</p>
        </div>
        <button class="btn-ghost" @click="loadJobs">刷新</button>
      </div>
      <div class="card jobs-list">
        <div v-for="job in jobs" :key="job.id" class="job-row">
          <div><b>{{ job.job_type === 'reindex' ? '重新索引' : '导入索引' }}</b><span class="source-meta">{{ formatDate(job.created_at, true) }}</span></div>
          <div class="num job-count">{{ job.succeeded_chunks }}/{{ job.total_chunks }} 分片</div>
          <span :class="['badge', statusClass(job.status)]">{{ statusLabel(job.status) }}</span>
          <span v-if="job.error_message" class="error-text">{{ job.error_message }}</span>
        </div>
        <div v-if="!jobs.length" class="empty-jobs">暂无索引任务</div>
      </div>
    </section>

    <div v-if="uploadOpen" class="modal-mask" @click.self="uploadOpen = false">
      <div class="modal upload-modal">
        <div class="modal-title"><b>上传制度</b><button class="modal-close" @click="uploadOpen = false">×</button></div>
        <div class="file-field">
          <label>电子版文件 *</label>
          <input ref="fileInput" type="file" accept=".txt,.md,.markdown,text/plain,text/markdown" @change="pickFile" />
          <span class="file-hint">仅支持 UTF-8 编码的 TXT 或 Markdown，最大 2MB</span>
          <span v-if="upload.file" class="file-name">{{ upload.file.name }}</span>
        </div>
        <div class="field">
          <label>制度名称 *</label>
          <input v-model="upload.title" maxlength="255" placeholder="如：员工考勤与休假管理制度" />
        </div>
        <div class="form-row">
          <div class="field"><label>版本号 *</label><input v-model="upload.version" maxlength="64" placeholder="如：V1.0" /></div>
          <div class="field"><label>生效日期 *</label><input v-model="upload.effective_at" type="date" /></div>
        </div>
        <div class="form-row">
          <div class="field"><label>分类</label><input v-model="upload.category" maxlength="64" placeholder="如：人事行政" /></div>
          <div class="field"><label>失效日期</label><input v-model="upload.expires_at" type="date" /></div>
        </div>
        <div class="upload-tip">索引成功后先保存为草稿。确认无误后，再在列表中发布。</div>
        <button class="btn-gold submit-upload" :disabled="uploading || !canUpload" @click="submitUpload">{{ uploading ? '正在索引…' : '上传并索引' }}</button>
      </div>
    </div>

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal detail-modal">
        <div class="modal-title"><div><b>{{ detail.source.title }}</b><span class="detail-version">{{ detail.source.version }}</span></div><button class="modal-close" @click="detail = null">×</button></div>
        <div class="detail-meta">{{ statusLabel(detail.source.status) }} · {{ formatDate(detail.source.effective_at) }} 生效 · 已显示前 {{ detail.chunks.length }} 个分片</div>
        <div class="chunk-list">
          <article v-for="chunk in detail.chunks" :key="chunk.id" class="chunk-item">
            <div class="chunk-head"><span>{{ chunk.section_path || '未标注章节' }}</span><span class="num">#{{ chunk.chunk_index + 1 }} · {{ chunk.token_count }} 字符估算</span></div>
            <p>{{ chunk.content }}</p>
          </article>
          <div v-if="!detail.chunks.length" class="empty-jobs">该资料尚未产生分片</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  apiAdminCompanyKnowledgeArchive,
  apiAdminCompanyKnowledgeJobs,
  apiAdminCompanyKnowledgePublish,
  apiAdminCompanyKnowledgeReindex,
  apiAdminCompanyKnowledgeSource,
  apiAdminCompanyKnowledgeSources,
  apiAdminCompanyKnowledgeUpload,
} from '../api'

const statusTabs = [
  { key: 'all', label: '全部' },
  { key: 'draft', label: '待发布' },
  { key: 'published', label: '已发布' },
  { key: 'indexing', label: '索引中' },
  { key: 'failed', label: '失败' },
  { key: 'archived', label: '已下架' },
]
const status = ref('all')
const items = ref([])
const jobs = ref([])
const total = ref(0)
const page = ref(1)
const size = 20
const loading = ref(false)
const actingId = ref('')
const notice = ref(null)
const uploadOpen = ref(false)
const uploading = ref(false)
const detail = ref(null)
const upload = ref(emptyUpload())

const canUpload = computed(() => upload.value.file && upload.value.title.trim() && upload.value.version.trim() && upload.value.effective_at)

function emptyUpload() {
  return { file: null, title: '', version: '', effective_at: '', expires_at: '', category: '', knowledge_type: 'policy' }
}
function statusLabel(value) {
  return ({ draft: '待发布', published: '已发布', indexing: '索引中', failed: '失败', archived: '已下架', running: '进行中', succeeded: '成功' }[value] || value)
}
function statusClass(value) {
  return ({ published: 'badge-moss', succeeded: 'badge-moss', draft: 'badge-gold', indexing: 'badge-gold', running: 'badge-gold', failed: 'badge-berry', archived: 'badge-berry' }[value] || '')
}
function formatDate(value, withTime = false) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, withTime ? 16 : 10)
  return withTime ? date.toLocaleString('zh-CN', { hour12: false }) : date.toLocaleDateString('zh-CN')
}
function showNotice(text, type = 'success') {
  notice.value = { text, type }
  window.setTimeout(() => { if (notice.value?.text === text) notice.value = null }, 3500)
}
async function load() {
  loading.value = true
  try {
    const res = await apiAdminCompanyKnowledgeSources('policy', status.value, page.value, size)
    if (res.success) {
      items.value = res.data.items
      total.value = res.data.total
    } else showNotice(res.message || '加载失败', 'error')
  } catch (error) { showNotice(error.message || '加载失败', 'error') } finally { loading.value = false }
}
async function loadJobs() {
  try {
    const res = await apiAdminCompanyKnowledgeJobs()
    if (res.success) jobs.value = res.data.items
  } catch {}
}
function switchStatus(next) { status.value = next; page.value = 1; load() }
function goPage(next) { page.value = next; load() }
function openUpload() { upload.value = emptyUpload(); uploadOpen.value = true }
function pickFile(event) { upload.value.file = event.target.files?.[0] || null }
async function submitUpload() {
  if (!canUpload.value) return
  uploading.value = true
  try {
    const res = await apiAdminCompanyKnowledgeUpload(upload.value)
    if (res.success) {
      uploadOpen.value = false
      showNotice(res.message)
      await Promise.all([load(), loadJobs()])
    } else showNotice(res.message || '导入失败', 'error')
  } catch (error) { showNotice(error.message || '导入失败', 'error') } finally { uploading.value = false }
}
async function publish(item) {
  if (!confirm(`发布「${item.title} ${item.version}」？同名已发布版本会自动下架。`)) return
  await runAction(item, apiAdminCompanyKnowledgePublish, '制度已发布')
}
async function archive(item) {
  if (!confirm(`下架「${item.title} ${item.version}」？下架后不再参与新问答。`)) return
  await runAction(item, apiAdminCompanyKnowledgeArchive, '制度已下架')
}
async function reindex(item) {
  if (!confirm(`重新索引「${item.title} ${item.version}」？`)) return
  await runAction(item, apiAdminCompanyKnowledgeReindex, '资料已重新索引')
}
async function runAction(item, action, successText) {
  actingId.value = item.id
  try {
    const res = await action(item.id)
    if (res.success) {
      showNotice(res.message || successText)
      await Promise.all([load(), loadJobs()])
    } else showNotice(res.message || '操作失败', 'error')
  } catch (error) { showNotice(error.message || '操作失败', 'error') } finally { actingId.value = '' }
}
async function showDetail(item) {
  try {
    const res = await apiAdminCompanyKnowledgeSource(item.id)
    if (res.success) detail.value = res.data
    else showNotice(res.message || '加载详情失败', 'error')
  } catch (error) { showNotice(error.message || '加载详情失败', 'error') }
}

onMounted(() => { load(); loadJobs() })
</script>

<style scoped>
.page-head, .knowledge-toolbar, .jobs-head, .modal-title, .pagination { display:flex; justify-content:space-between; align-items:flex-end; gap:12px; }
.knowledge-toolbar { margin:18px 0 12px; align-items:center; flex-wrap:wrap; }
.tabs { display:flex; gap:6px; flex-wrap:wrap; }
.tab-filter, .row-btn { border:1px solid var(--line); background:transparent; color:var(--ink-soft); border-radius:6px; font-size:13px; }
.tab-filter { padding:6px 14px; }
.tab-filter:hover, .row-btn:hover { border-color:var(--gold); color:var(--ink); }
.tab-filter.active { background:var(--gold-soft); border-color:var(--gold); color:#8A6A1C; font-weight:600; }
.status-note, .source-meta, .detail-meta, .upload-tip { color:var(--ink-soft); font-size:12px; }
.table-wrap { padding:0; overflow:auto; position:relative; min-height:180px; }
.actions-head { min-width:182px; }
.row-actions { white-space:nowrap; }
.row-btn { padding:4px 8px; margin-right:4px; font-size:12px; }
.row-btn.moss:hover { border-color:var(--moss); color:var(--moss); }
.row-btn.danger:hover { border-color:var(--berry); color:var(--berry); }
.row-btn:disabled { opacity:.5; cursor:not-allowed; }
.source-meta { margin-top:3px; overflow-wrap:anywhere; }
.dim { color:var(--ink-soft); font-size:12px; white-space:nowrap; }
.error-text { color:var(--berry); font-size:12px; margin-top:3px; overflow-wrap:anywhere; }
.empty-row, .table-loading, .empty-jobs { padding:36px 12px; text-align:center; color:var(--ink-soft); font-size:13px; }
.table-loading { position:absolute; inset:0; background:rgba(255,255,255,.72); display:flex; align-items:center; justify-content:center; }
.pagination { margin-top:14px; align-items:center; color:var(--ink-soft); font-size:12px; }
.pagination > div { display:flex; gap:8px; align-items:center; }
.page-no { min-width:20px; text-align:center; color:var(--ink); }
.jobs-section { margin-top:30px; }
.jobs-head { align-items:center; margin-bottom:10px; }
.jobs-head h2 { font-size:15px; }
.jobs-head p { font-size:12px; color:var(--ink-soft); margin-top:2px; }
.jobs-list { padding:0; }
.job-row { min-height:54px; display:grid; grid-template-columns:minmax(160px,1fr) 120px 76px minmax(0,1fr); gap:12px; align-items:center; padding:10px 14px; border-bottom:1px solid var(--line); }
.job-row:last-child { border-bottom:none; }
.job-row b { display:block; font-size:13px; }
.job-count { font-size:12px; color:var(--ink-soft); }
.notice { margin-bottom:12px; padding:9px 12px; border-radius:6px; font-size:13px; }
.notice.success { background:#E4EEE6; color:var(--moss); }
.notice.error { background:#F6E4E2; color:var(--berry); }
.modal-mask { position:fixed; inset:0; z-index:30; background:rgba(30,53,44,.42); display:flex; align-items:center; justify-content:center; padding:20px; }
.modal { width:min(520px, 100%); max-height:calc(100vh - 40px); overflow:auto; border-radius:8px; background:var(--card); box-shadow:0 20px 48px rgba(30,53,44,.24); padding:20px; }
.modal-title { align-items:center; margin-bottom:18px; font-size:16px; }
.modal-close { border:0; background:transparent; color:var(--ink-soft); font-size:26px; line-height:1; padding:2px 6px; }
.modal-close:hover { color:var(--berry); }
.file-field { margin-bottom:16px; }
.file-field label { display:block; font-size:13px; color:var(--ink-soft); margin-bottom:6px; }
.file-field input { display:block; width:100%; padding:9px; border:1px dashed var(--line); border-radius:6px; background:var(--bg); font-size:13px; }
.file-hint, .file-name { display:block; margin-top:6px; font-size:12px; color:var(--ink-soft); }
.file-name { color:var(--moss); overflow-wrap:anywhere; }
.form-row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.upload-tip { border-left:3px solid var(--gold); padding-left:9px; margin:0 0 16px; }
.submit-upload { width:100%; }
.detail-modal { width:min(760px, 100%); }
.detail-version { margin-left:8px; color:var(--ink-soft); font-weight:400; font-size:13px; }
.chunk-list { margin-top:16px; display:grid; gap:10px; }
.chunk-item { border:1px solid var(--line); border-radius:6px; padding:12px; }
.chunk-head { display:flex; justify-content:space-between; gap:10px; color:var(--moss); font-size:12px; }
.chunk-head span:last-child { color:var(--ink-soft); white-space:nowrap; }
.chunk-item p { margin-top:8px; white-space:pre-wrap; font-size:13px; overflow-wrap:anywhere; }
@media (max-width: 760px) {
  .job-row { grid-template-columns:1fr 76px; }
  .job-row .error-text { grid-column:1 / -1; }
  .status-note { width:100%; }
  .form-row { grid-template-columns:1fr; gap:0; }
}
</style>
