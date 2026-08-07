<template>
  <div>
    <div class="page-head">
      <div>
        <div class="page-title">RAG 知识库</div>
        <div class="page-sub">上传资料并转换为 Markdown，完成切分、向量化和验证后发布</div>
      </div>
      <button class="btn-gold" @click="openUpload">上传资料</button>
    </div>

    <div class="knowledge-toolbar">
      <div class="tabs" aria-label="资料状态筛选">
        <button v-for="tab in statusTabs" :key="tab.key" :class="['tab-filter', status === tab.key ? 'active' : '']" @click="switchStatus(tab.key)">{{ tab.label }}</button>
      </div>
      <span class="status-note">快捷操作可直接使用；完整上传到发布流程也可在“RAG 执行流程”完成</span>
    </div>

    <div v-if="notice" :class="['notice', notice.type]">{{ notice.text }}</div>

    <div class="card table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>资料</th><th>版本</th><th>生效日期</th><th>分片</th><th>状态</th><th>更新时间</th><th class="actions-head">操作</th>
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
              <button v-if="item.status !== 'published' && item.status !== 'indexing'" class="row-btn" @click="openEdit(item)">编辑信息</button>
              <button v-if="item.status !== 'archived'" class="row-btn" @click="openWorkflow(item)">执行流程</button>
              <button v-if="item.status === 'validated' || item.status === 'published'" class="row-btn moss" :disabled="actingId === item.id" @click="publish(item)">{{ item.status === 'published' ? '切换索引' : '发布' }}</button>
              <button v-if="item.status === 'archived'" class="row-btn moss" :disabled="actingId === item.id" @click="restore(item)">上架</button>
              <button v-if="item.status !== 'archived' && item.status !== 'indexing'" class="row-btn danger" :disabled="actingId === item.id" @click="archive(item)">下架</button>
              <button v-if="item.status === 'archived'" class="row-btn danger" :disabled="actingId === item.id" @click="removeArchived(item)">删除</button>
            </td>
          </tr>
          <tr v-if="!loading && !items.length"><td colspan="7" class="empty-row">暂无知识库资料</td></tr>
        </tbody>
      </table>
      <div v-if="loading" class="table-loading">正在加载知识库资料…</div>
    </div>

    <div v-if="total > 0" class="pagination">
      <span class="num">共 {{ total }} 条</span>
      <div><button class="btn-ghost" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button><span class="num page-no">{{ page }}</span><button class="btn-ghost" :disabled="page * size >= total" @click="goPage(page + 1)">下一页</button></div>
    </div>

    <div v-if="uploadOpen" class="modal-mask" @click.self="uploadOpen = false">
      <div class="modal upload-modal">
        <div class="modal-title"><b>上传资料</b><button class="modal-close" @click="uploadOpen = false">×</button></div>
        <div class="file-field"><label>电子版文件 *</label><input type="file" accept=".txt,.md,.markdown,text/plain,text/markdown" @change="pickFile" /><span class="file-hint">仅支持 UTF-8 编码的 TXT 或 Markdown，最大 2MB</span><span v-if="upload.file" class="file-name">{{ upload.file.name }}</span></div>
        <div class="field"><label>资料名称 *</label><input v-model="upload.title" maxlength="255" placeholder="如：员工考勤与休假管理制度" /></div>
        <div class="form-row"><div class="field"><label>版本号 *</label><input v-model="upload.version" maxlength="64" placeholder="如：V1.0" /></div><div class="field"><label>生效日期 *</label><input v-model="upload.effective_at" type="date" /></div></div>
        <div class="form-row"><div class="field"><label>分类</label><input v-model="upload.category" maxlength="64" placeholder="如：人事行政" /></div><div class="field"><label>失效日期</label><input v-model="upload.expires_at" type="date" /></div></div>
        <div class="upload-tip">上传后仅生成 Markdown；请在“RAG 执行流程”确认分片、向量化和检索验证。</div>
        <button class="btn-gold submit-upload" :disabled="uploading || !canUpload" @click="submitUpload">{{ uploading ? '正在转换…' : '上传并转换' }}</button>
      </div>
    </div>

    <div v-if="editOpen" class="modal-mask" @click.self="editOpen = false">
      <div class="modal upload-modal">
        <div class="modal-title"><b>编辑资料信息</b><button class="modal-close" @click="editOpen = false">×</button></div>
        <div class="field"><label>资料名称 *</label><input v-model="edit.title" maxlength="255" /></div>
        <div class="form-row"><div class="field"><label>版本号 *</label><input v-model="edit.version" maxlength="64" /></div><div class="field"><label>生效日期 *</label><input v-model="edit.effective_at" type="date" /></div></div>
        <div class="form-row"><div class="field"><label>分类</label><input v-model="edit.category" maxlength="64" /></div><div class="field"><label>失效日期</label><input v-model="edit.expires_at" type="date" /></div></div>
        <div class="upload-tip">编辑不会改动原文件、Markdown、分片或既有引用；已发布资料请上传新版本。</div>
        <button class="btn-gold submit-upload" :disabled="savingEdit || !canSaveEdit" @click="submitEdit">{{ savingEdit ? '保存中…' : '保存修改' }}</button>
      </div>
    </div>

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal detail-modal">
        <div class="modal-title"><div><b>{{ detail.source.title }}</b><span class="detail-version">{{ detail.source.version }}</span></div><button class="modal-close" @click="detail = null">×</button></div>
        <div class="detail-meta">{{ statusLabel(detail.source.status) }} · {{ formatDate(detail.source.effective_at) }} 生效 · Markdown 正文</div>
        <pre class="markdown-preview">{{ detail.markdown }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  apiAdminCompanyKnowledgeArchive,
  apiAdminCompanyKnowledgeDelete,
  apiAdminCompanyKnowledgePublish,
  apiAdminCompanyKnowledgeSource,
  apiAdminCompanyKnowledgeSources,
  apiAdminCompanyKnowledgeUpdate,
  apiAdminCompanyKnowledgeUpload,
} from '../api'

const router = useRouter()
const statusTabs = [
  { key: 'all', label: '全部' }, { key: 'markdown_ready', label: '待预处理' }, { key: 'preprocessed', label: '待切分' }, { key: 'chunk_ready', label: '待向量化' }, { key: 'indexed', label: '待验证' }, { key: 'validated', label: '待发布' }, { key: 'published', label: '已发布' }, { key: 'indexing', label: '向量化中' }, { key: 'failed', label: '失败' }, { key: 'archived', label: '已下架' },
]
const status = ref('all')
const items = ref([])
const total = ref(0)
const page = ref(1)
const size = 20
const loading = ref(false)
const actingId = ref('')
const notice = ref(null)
const uploadOpen = ref(false)
const uploading = ref(false)
const upload = ref(emptyUpload())
const editOpen = ref(false)
const savingEdit = ref(false)
const edit = ref(emptyEdit())
const detail = ref(null)
const canUpload = computed(() => upload.value.file && upload.value.title.trim() && upload.value.version.trim() && upload.value.effective_at)
const canSaveEdit = computed(() => edit.value.id && edit.value.title.trim() && edit.value.version.trim() && edit.value.effective_at)

function emptyUpload() { return { file: null, title: '', version: '', effective_at: '', expires_at: '', category: '', knowledge_type: 'policy' } }
function emptyEdit() { return { id: '', title: '', version: '', effective_at: '', expires_at: '', category: '' } }
function statusLabel(value) { return ({ markdown_ready: '待预处理', preprocessed: '待切分', chunking: '切分草稿', chunk_ready: '待向量化', indexed: '待检索验证', validated: '待发布', published: '已发布', indexing: '向量化中', failed: '失败', archived: '已下架', running: '进行中', succeeded: '成功' }[value] || value) }
function statusClass(value) { return ({ published: 'badge-moss', succeeded: 'badge-moss', indexed: 'badge-gold', validated: 'badge-gold', markdown_ready: 'badge-gold', preprocessed: 'badge-gold', chunking: 'badge-gold', chunk_ready: 'badge-gold', indexing: 'badge-gold', running: 'badge-gold', failed: 'badge-berry', archived: 'badge-berry' }[value] || '') }
function formatDate(value, withTime = false) { if (!value) return '—'; const date = new Date(value); if (Number.isNaN(date.getTime())) return value.slice(0, withTime ? 16 : 10); return withTime ? date.toLocaleString('zh-CN', { hour12: false }) : date.toLocaleDateString('zh-CN') }
function showNotice(text, type = 'success') { notice.value = { text, type }; window.setTimeout(() => { if (notice.value?.text === text) notice.value = null }, 3500) }
async function load() {
  loading.value = true
  try {
    const res = await apiAdminCompanyKnowledgeSources('policy', status.value, page.value, size)
    if (res.success) { items.value = res.data.items; total.value = res.data.total } else showNotice(res.message || '加载失败', 'error')
  } catch (error) { showNotice(error.message || '加载失败', 'error') } finally { loading.value = false }
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
    if (res.success) { uploadOpen.value = false; showNotice(res.message); await load() } else showNotice(res.message || '导入失败', 'error')
  } catch (error) { showNotice(error.message || '导入失败', 'error') } finally { uploading.value = false }
}
function openEdit(item) { edit.value = { id: item.id, title: item.title, version: item.version, effective_at: item.effective_at?.slice(0, 10) || '', expires_at: item.expires_at?.slice(0, 10) || '', category: item.category || '' }; editOpen.value = true }
async function submitEdit() {
  if (!canSaveEdit.value) return
  savingEdit.value = true
  try {
    const res = await apiAdminCompanyKnowledgeUpdate(edit.value.id, { title: edit.value.title.trim(), version: edit.value.version.trim(), effective_at: edit.value.effective_at, expires_at: edit.value.expires_at || null, category: edit.value.category.trim() })
    if (res.success) { editOpen.value = false; showNotice(res.message || '资料信息已更新'); await load() } else showNotice(res.message || '保存失败', 'error')
  } catch (error) { showNotice(error.message || '保存失败', 'error') } finally { savingEdit.value = false }
}
function openWorkflow(item) { router.push({ path: '/chunking-rules', query: { source: item.id } }) }
async function publish(item) { if (confirm(`发布「${item.title} ${item.version}」？同名已发布版本会自动下架。`)) await runAction(item, apiAdminCompanyKnowledgePublish, '资料已发布') }
async function archive(item) { if (confirm(`下架「${item.title} ${item.version}」？下架后不再参与新问答。`)) await runAction(item, apiAdminCompanyKnowledgeArchive, '资料已下架') }
async function restore(item) { if (confirm(`上架「${item.title} ${item.version}」？恢复后该资料将重新参与新问答。`)) await runAction(item, apiAdminCompanyKnowledgePublish, '资料已重新上架') }
async function removeArchived(item) { if (confirm(`删除已下架资料「${item.title} ${item.version}」？此操作不可恢复。`)) await runAction(item, apiAdminCompanyKnowledgeDelete, '已删除下架资料') }
async function runAction(item, action, successText) {
  actingId.value = item.id
  try { const res = await action(item.id); if (res.success) { showNotice(res.message || successText); await load() } else showNotice(res.message || '操作失败', 'error') } catch (error) { showNotice(error.message || '操作失败', 'error') } finally { actingId.value = '' }
}
async function showDetail(item) { try { const res = await apiAdminCompanyKnowledgeSource(item.id); if (res.success) detail.value = res.data; else showNotice(res.message || '加载详情失败', 'error') } catch (error) { showNotice(error.message || '加载详情失败', 'error') } }

onMounted(load)
</script>

<style scoped>
.page-head, .knowledge-toolbar, .modal-title, .pagination { display:flex; justify-content:space-between; align-items:flex-end; gap:12px; }
.knowledge-toolbar { margin:18px 0 12px; align-items:center; flex-wrap:wrap; }
.tabs { display:flex; gap:6px; flex-wrap:wrap; }
.tab-filter, .row-btn { border:1px solid var(--line); background:transparent; color:var(--ink-soft); border-radius:6px; font-size:13px; }
.tab-filter { padding:6px 14px; }
.tab-filter:hover, .row-btn:hover { border-color:var(--gold); color:var(--ink); }
.tab-filter.active { background:var(--gold-soft); border-color:var(--gold); color:#8A6A1C; font-weight:600; }
.status-note, .source-meta, .detail-meta, .upload-tip { color:var(--ink-soft); font-size:12px; }
.table-wrap { padding:0; overflow:auto; position:relative; min-height:180px; }
.actions-head { min-width:270px; }
.row-actions { white-space:nowrap; }
.row-btn { padding:4px 8px; margin-right:4px; font-size:12px; }
.row-btn.moss:hover { border-color:var(--moss); color:var(--moss); }
.row-btn.danger:hover { border-color:var(--berry); color:var(--berry); }
.row-btn:disabled { opacity:.5; cursor:not-allowed; }
.source-meta { margin-top:3px; overflow-wrap:anywhere; }
.dim { color:var(--ink-soft); font-size:12px; white-space:nowrap; }
.error-text { color:var(--berry); font-size:12px; margin-top:3px; overflow-wrap:anywhere; }
.empty-row, .table-loading { padding:36px 12px; text-align:center; color:var(--ink-soft); font-size:13px; }
.table-loading { position:absolute; inset:0; background:rgba(255,255,255,.72); display:flex; align-items:center; justify-content:center; }
.pagination { margin-top:14px; align-items:center; color:var(--ink-soft); font-size:12px; }
.pagination > div { display:flex; gap:8px; align-items:center; }
.page-no { min-width:20px; text-align:center; color:var(--ink); }
.notice { margin-bottom:12px; padding:9px 12px; border-radius:6px; font-size:13px; }
.notice.success { background:#E4EEE6; color:var(--moss); }
.notice.error { background:#F6E4E2; color:var(--berry); }
.modal-mask { position:fixed; inset:0; z-index:30; background:rgba(30,53,44,.42); display:flex; align-items:center; justify-content:center; padding:20px; }
.modal { width:min(520px, 100%); max-height:calc(100vh - 40px); overflow:auto; border-radius:8px; background:var(--card); box-shadow:0 20px 48px rgba(30,53,44,.24); padding:20px; }
.modal-title { align-items:center; margin-bottom:18px; font-size:16px; }
.modal-close { border:0; background:transparent; color:var(--ink-soft); font-size:26px; line-height:1; padding:2px 6px; }
.modal-close:hover { color:var(--berry); }
.file-field { margin-bottom:16px; }
.file-field label, .field label { display:block; font-size:13px; color:var(--ink-soft); margin-bottom:6px; }
.file-field input, .field input { display:block; box-sizing:border-box; width:100%; padding:9px; border:1px solid var(--line); border-radius:6px; background:var(--card); color:var(--ink); font:inherit; }
.file-field input { border-style:dashed; background:var(--bg); }
.file-hint, .file-name { display:block; margin-top:6px; font-size:12px; color:var(--ink-soft); }
.file-name { color:var(--moss); overflow-wrap:anywhere; }
.field { margin-bottom:14px; }
.form-row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.upload-tip { border-left:3px solid var(--gold); padding-left:9px; margin:0 0 16px; }
.submit-upload { width:100%; }
.detail-modal { width:min(760px, 100%); }
.detail-version { margin-left:8px; color:var(--ink-soft); font-weight:400; font-size:13px; }
.markdown-preview { margin-top:16px; max-height:56vh; overflow:auto; border:1px solid var(--line); border-radius:6px; padding:12px; background:var(--bg); color:var(--ink); white-space:pre-wrap; overflow-wrap:anywhere; font:12px/1.65 ui-monospace, SFMono-Regular, Consolas, monospace; }
@media (max-width:760px) { .status-note { width:100%; } .form-row { grid-template-columns:1fr; gap:0; } }
</style>
