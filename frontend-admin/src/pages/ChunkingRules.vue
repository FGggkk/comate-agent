<template>
  <div>
    <div class="page-head">
      <div>
        <div class="page-title">RAG 执行流程</div>
        <div class="page-sub">上传资料、确认分片、向量化、检索验证并发布</div>
      </div>
      <div class="page-actions">
        <button class="btn-ghost" @click="goKnowledge">查看知识库</button>
        <button class="btn-gold" @click="openUpload">上传资料</button>
      </div>
    </div>

    <div class="card source-picker">
      <label for="source-select">选择资料</label>
      <select id="source-select" v-model="sourceId" @change="changeSource">
        <option value="">请选择已转换的资料</option>
        <option v-for="item in sources" :key="item.id" :value="item.id">{{ item.title }} · {{ item.version }} · {{ statusLabel(item.status) }}</option>
      </select>
      <div v-if="detail" class="source-actions">
        <button v-if="detail.source.status !== 'published' && detail.source.status !== 'indexing'" class="row-btn" @click="openEdit">编辑</button>
        <button v-if="detail.source.status !== 'archived' && detail.source.status !== 'indexing'" class="row-btn danger" :disabled="sourceActing" @click="archiveSource">下架</button>
        <button v-if="detail.source.status === 'archived'" class="row-btn danger" :disabled="sourceActing" @click="removeSource">删除</button>
      </div>
    </div>

    <p v-if="notice" :class="['notice', notice.type]">{{ notice.text }}</p>

    <template v-if="detail">
      <section class="source-head">
        <div>
          <h2>{{ detail.source.title }}</h2>
          <p>{{ detail.source.version }} · {{ statusLabel(detail.source.status) }} · {{ detail.source.file_name }}</p>
        </div>
        <select v-if="detail.chunk_sets.length" v-model="activeChunkSetId" class="set-select" @change="loadDetail">
          <option v-for="item in detail.chunk_sets" :key="item.id" :value="item.id">{{ modeLabel(item.mode) }} · {{ statusLabel(chunkSetDisplayStatus(item)) }} · {{ formatDate(item.created_at) }}</option>
        </select>
      </section>

      <details class="markdown-source">
        <summary>查看 Markdown 正文</summary>
        <pre>{{ detail.markdown }}</pre>
      </details>

      <section v-if="detail.source.status !== 'archived'" class="card controls">
        <div class="control-title">生成分片草稿</div>
        <div class="mode-options" role="radiogroup" aria-label="切分方式">
          <label v-for="item in modes" :key="item.key" :class="['mode-option', mode === item.key ? 'selected' : '']">
            <input v-model="mode" type="radio" :value="item.key" />
            <span><b>{{ item.label }}</b><small>{{ item.desc }}</small></span>
          </label>
        </div>
        <div v-if="mode !== 'manual'" class="rule-fields">
          <label>目标长度<input v-model.number="rule.max_chars" type="number" min="120" max="3000" /> <span>字符</span></label>
          <label>重叠长度<input v-model.number="rule.overlap_chars" type="number" min="0" :max="Math.max(0, rule.max_chars - 1)" /> <span>字符</span></label>
        </div>
        <button class="btn-gold" :disabled="creating" @click="createDraft">{{ creating ? '正在生成…' : '生成分片草稿' }}</button>
      </section>

      <section v-if="selectedSet" class="chunk-workspace">
        <div class="workspace-head">
          <div>
            <h2>分片草稿</h2>
            <p>{{ modeLabel(selectedSet.mode) }} · {{ statusLabel(selectedSetDisplayStatus) }} · {{ editable ? '可以编辑' : '已锁定' }}</p>
          </div>
          <div v-if="editable" class="workspace-actions">
            <button class="btn-ghost" @click="addChunk">新增分片</button>
            <button class="btn-ghost" :disabled="saving" @click="saveDraft">{{ saving ? '保存中…' : '保存草稿' }}</button>
            <button class="btn-gold" :disabled="saving" @click="confirmDraft">确认分片</button>
          </div>
          <button v-else-if="selectedSetDisplayStatus === 'confirmed' && detail.source.status !== 'archived'" class="btn-gold" :disabled="indexing" @click="indexDraft">{{ indexing ? '向量化中…' : '向量化' }}</button>
          <div v-else-if="selectedSetDisplayStatus === 'indexed'" class="workflow-action">
            <span class="indexed-note">已向量化</span>
            <button class="btn-gold" @click="openValidation">检索验证</button>
          </div>
          <div v-else-if="selectedSetDisplayStatus === 'validated'" class="workflow-action">
            <span class="indexed-note">检索验证已确认</span>
            <button class="btn-gold" :disabled="sourceActing" @click="publishSource">{{ sourceActing ? '发布中…' : '发布' }}</button>
          </div>
          <span v-else-if="selectedSetDisplayStatus === 'published'" class="indexed-note">已发布</span>
        </div>

        <section v-if="(selectedSetDisplayStatus === 'indexed' || selectedSetDisplayStatus === 'validated') && validationOpen" ref="validationPanel" class="retrieval-validation">
          <div class="validation-head">
            <div>
              <h2>检索验证</h2>
              <p>仅检索当前分片版本，核对典型问题的相似度与预期章节命中情况。</p>
            </div>
            <span class="validation-status">{{ selectedSetDisplayStatus === 'validated' ? '已确认' : '待确认' }}</span>
          </div>
          <div class="validation-mode" role="radiogroup" aria-label="检索验证方式">
            <label :class="['validation-mode-option', validationMode === 'auto' ? 'selected' : '']">
              <input v-model="validationMode" type="radio" value="auto" @change="changeValidationMode" />
              <span><b>自动生成</b><small>从当前 Markdown 随机抽取主题生成问题</small></span>
            </label>
            <label :class="['validation-mode-option', validationMode === 'manual' ? 'selected' : '']">
              <input v-model="validationMode" type="radio" value="manual" @change="changeValidationMode" />
              <span><b>手动输入</b><small>自行输入需要验证的典型问题</small></span>
            </label>
          </div>
          <div v-if="validationMode === 'auto'" class="auto-question">
            <div><b>自动问题</b><p>{{ autoQuestion || '未能从 Markdown 生成问题，请改用手动输入。' }}</p></div>
            <button class="btn-ghost" @click="regenerateAutoQuestion">换一个问题</button>
          </div>
          <label v-else class="manual-question">典型问题<textarea v-model="manualQuestion" rows="3" maxlength="2000" placeholder="如：员工年假如何申请？" @input="clearValidationResult" /></label>
          <div class="validation-fields">
            <label>预期分片（手动验证可选）
              <select v-model="expectedChunkId" :disabled="validationMode === 'auto'" @change="clearValidationResult">
                <option value="">仅查看相似度</option>
                <option v-for="(chunk, index) in verificationChunks" :key="chunk.id" :value="chunk.id">第 {{ index + 1 }} 段 · {{ chunk.section_path || '未标注章节' }}</option>
              </select>
            </label>
            <label>返回条数
              <select v-model.number="verificationTopK" @change="clearValidationResult">
                <option :value="3">3</option>
                <option :value="6">6</option>
                <option :value="10">10</option>
              </select>
            </label>
          </div>
          <div class="validation-actions">
            <button class="btn-gold" :disabled="verifying || !activeVerificationQuestion" @click="previewRetrieval">{{ verifying ? '检索中…' : '测试检索' }}</button>
            <button v-if="selectedSetDisplayStatus === 'indexed'" class="btn-ghost" :disabled="validating || !canConfirmValidation" @click="confirmValidation">{{ validating ? '确认中…' : '确认检索验证' }}</button>
            <button v-if="selectedSetDisplayStatus === 'validated'" class="btn-gold" :disabled="sourceActing" @click="publishSource">{{ sourceActing ? '发布中…' : '发布' }}</button>
          </div>
          <p v-if="retrievalResult" :class="['validation-summary', expectedChunkId && !retrievalResult.expected_hit ? 'is-miss' : '']">
            返回 {{ retrievalResult.items.length }} 条结果，{{ retrievalResult.above_threshold_count }} 条达到最低相似度 {{ formatSimilarity(retrievalResult.minimum_similarity) }}。
            <template v-if="expectedChunkId">{{ retrievalResult.expected_hit ? '预期分片已命中。' : '预期分片未命中，请调整切分或提问。' }}</template>
            <template v-else>选择预期分片后可验证 Top-K 命中。</template>
          </p>
          <div v-if="retrievalResult?.items.length" class="retrieval-results">
            <article v-for="(item, index) in retrievalResult.items" :key="item.chunk_id" :class="['retrieval-result', item.meets_minimum_similarity ? 'is-qualified' : 'is-low']">
              <div class="retrieval-result-head">
                <b>Top {{ index + 1 }} · {{ item.section_path || '未标注章节' }}</b>
                <span>{{ formatSimilarity(item.similarity) }}</span>
              </div>
              <p>{{ item.meets_minimum_similarity ? '达到最低相似度' : '低于最低相似度' }}<em v-if="expectedChunkId === item.chunk_id">预期分片</em></p>
              <details><summary>查看分片正文</summary><pre>{{ item.content }}</pre></details>
            </article>
          </div>
        </section>

        <div class="chunk-list">
          <article v-for="(chunk, index) in draftChunks" :key="`${selectedSet.id}-${index}`" class="chunk-editor">
            <div class="chunk-editor-head">
              <b>分片 {{ index + 1 }}</b>
              <button v-if="editable && draftChunks.length > 1" class="icon-delete" title="删除分片" aria-label="删除分片" @click="removeChunk(index)">×</button>
            </div>
            <label>章节路径<input v-model="chunk.section_path" :disabled="!editable" placeholder="如：人事制度 / 年假" /></label>
            <label>分片正文<textarea v-model="chunk.content" :disabled="!editable" rows="7" /></label>
            <div class="chunk-count">{{ chunk.content.length }} 字符</div>
          </article>
        </div>
      </section>
    </template>

    <div v-else class="empty-state">上传资料或从列表选择一份资料后开始执行流程。</div>

    <section class="jobs-section">
      <div class="jobs-head">
        <div>
          <h2>处理任务</h2>
          <p>转换、切分和向量化都会留下记录。</p>
        </div>
        <button class="btn-ghost" @click="loadJobs">刷新</button>
      </div>
      <div class="card jobs-list">
        <div v-for="job in jobs" :key="job.id" class="job-row">
          <div><b>{{ jobLabel(job.job_type) }}</b><span class="source-meta">{{ formatDate(job.created_at) }}</span></div>
          <div class="num job-count">{{ job.succeeded_chunks }}/{{ job.total_chunks }} 分片</div>
          <span :class="['badge', statusClass(job.status)]">{{ statusLabel(job.status) }}</span>
          <span v-if="job.error_message" class="error-text">{{ job.error_message }}</span>
          <button v-if="canDeleteJob(job)" class="row-btn danger job-delete" :disabled="deletingJobId === job.id" @click="removeJob(job)">{{ deletingJobId === job.id ? '删除中…' : '删除' }}</button>
        </div>
        <div v-if="!jobs.length" class="empty-jobs">暂无处理任务</div>
      </div>
    </section>

    <div v-if="uploadOpen" class="modal-mask" @click.self="uploadOpen = false">
      <div class="modal upload-modal">
        <div class="modal-title"><b>上传资料</b><button class="modal-close" @click="uploadOpen = false">×</button></div>
        <div class="file-field">
          <label>电子版文件 *</label>
          <input type="file" accept=".txt,.md,.markdown,text/plain,text/markdown" @change="pickFile" />
          <span class="file-hint">仅支持 UTF-8 编码的 TXT 或 Markdown，最大 2MB</span>
          <span v-if="upload.file" class="file-name">{{ upload.file.name }}</span>
        </div>
        <div class="field"><label>资料名称 *</label><input v-model="upload.title" maxlength="255" placeholder="如：员工考勤与休假管理制度" /></div>
        <div class="form-row">
          <div class="field"><label>版本号 *</label><input v-model="upload.version" maxlength="64" placeholder="如：V1.0" /></div>
          <div class="field"><label>生效日期 *</label><input v-model="upload.effective_at" type="date" /></div>
        </div>
        <div class="form-row">
          <div class="field"><label>分类</label><input v-model="upload.category" maxlength="64" placeholder="如：人事行政" /></div>
          <div class="field"><label>失效日期</label><input v-model="upload.expires_at" type="date" /></div>
        </div>
        <div class="upload-tip">上传后生成 Markdown，并直接在本页完成后续流程。</div>
        <button class="btn-gold submit-upload" :disabled="uploading || !canUpload" @click="submitUpload">{{ uploading ? '正在转换…' : '上传并转换' }}</button>
      </div>
    </div>

    <div v-if="editOpen" class="modal-mask" @click.self="editOpen = false">
      <div class="modal upload-modal">
        <div class="modal-title"><b>编辑资料信息</b><button class="modal-close" @click="editOpen = false">×</button></div>
        <div class="field"><label>资料名称 *</label><input v-model="edit.title" maxlength="255" /></div>
        <div class="form-row">
          <div class="field"><label>版本号 *</label><input v-model="edit.version" maxlength="64" /></div>
          <div class="field"><label>生效日期 *</label><input v-model="edit.effective_at" type="date" /></div>
        </div>
        <div class="form-row">
          <div class="field"><label>分类</label><input v-model="edit.category" maxlength="64" /></div>
          <div class="field"><label>失效日期</label><input v-model="edit.expires_at" type="date" /></div>
        </div>
        <div class="upload-tip">编辑不会改动原文件、Markdown、分片或既有引用；已发布资料请上传新版本。</div>
        <button class="btn-gold submit-upload" :disabled="savingEdit || !canSaveEdit" @click="submitEdit">{{ savingEdit ? '保存中…' : '保存修改' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  apiAdminCompanyKnowledgeArchive,
  apiAdminCompanyKnowledgeConfirmChunkSet,
  apiAdminCompanyKnowledgeCreateChunkSet,
  apiAdminCompanyKnowledgeDelete,
  apiAdminCompanyKnowledgeDeleteJob,
  apiAdminCompanyKnowledgeIndexChunkSet,
  apiAdminCompanyKnowledgeJobs,
  apiAdminCompanyKnowledgePreviewChunkSet,
  apiAdminCompanyKnowledgePublish,
  apiAdminCompanyKnowledgeSource,
  apiAdminCompanyKnowledgeSources,
  apiAdminCompanyKnowledgeUpdate,
  apiAdminCompanyKnowledgeUpdateChunkSet,
  apiAdminCompanyKnowledgeUpload,
  apiAdminCompanyKnowledgeValidateChunkSet,
} from '../api'

const route = useRoute()
const router = useRouter()
const sources = ref([])
const sourceId = ref('')
const detail = ref(null)
const activeChunkSetId = ref('')
const draftChunks = ref([])
const mode = ref('auto_then_manual')
const rule = ref({ max_chars: 650, overlap_chars: 100 })
const creating = ref(false)
const saving = ref(false)
const indexing = ref(false)
const verifying = ref(false)
const validating = ref(false)
const sourceActing = ref(false)
const notice = ref(null)
const validationMode = ref('auto')
const autoQuestion = ref('')
const manualQuestion = ref('')
const verificationTopK = ref(6)
const expectedChunkId = ref('')
const retrievalResult = ref(null)
const previewedQuestion = ref('')
const validationOpen = ref(false)
const validationPanel = ref(null)
const uploadOpen = ref(false)
const uploading = ref(false)
const upload = ref(emptyUpload())
const editOpen = ref(false)
const savingEdit = ref(false)
const edit = ref(emptyEdit())
const jobs = ref([])
const deletingJobId = ref('')
const modes = [
  { key: 'auto', label: '自动切分', desc: '按 Markdown 标题和长度生成草稿' },
  { key: 'manual', label: '手动切分', desc: '从完整 Markdown 开始自行拆分' },
  { key: 'auto_then_manual', label: '自动后调优', desc: '先自动生成，再人工修改边界' },
]

const selectedSet = computed(() => detail.value?.chunk_sets.find((item) => item.id === activeChunkSetId.value) || null)
const selectedSetDisplayStatus = computed(() => chunkSetDisplayStatus(selectedSet.value))
const editable = computed(() => selectedSetDisplayStatus.value === 'draft' && detail.value?.source.status !== 'archived')
const verificationChunks = computed(() => detail.value?.chunks || [])
const activeVerificationQuestion = computed(() => (validationMode.value === 'auto' ? autoQuestion.value : manualQuestion.value).trim())
const canConfirmValidation = computed(() => {
  if (!activeVerificationQuestion.value || previewedQuestion.value !== activeVerificationQuestion.value || !retrievalResult.value?.items?.length) return false
  return !expectedChunkId.value || retrievalResult.value.expected_hit === true
})
const canUpload = computed(() => upload.value.file && upload.value.title.trim() && upload.value.version.trim() && upload.value.effective_at)
const canSaveEdit = computed(() => edit.value.id && edit.value.title.trim() && edit.value.version.trim() && edit.value.effective_at)

function emptyUpload() { return { file: null, title: '', version: '', effective_at: '', expires_at: '', category: '', knowledge_type: 'policy' } }
function emptyEdit() { return { id: '', title: '', version: '', effective_at: '', expires_at: '', category: '' } }
function statusLabel(value) {
  return ({ markdown_ready: '待切分', chunking: '切分草稿', chunk_ready: '待向量化', indexed: '待检索验证', validated: '待发布', indexing: '向量化中', published: '已发布', archived: '已下架', draft: '草稿', confirmed: '已确认', superseded: '已替换', failed: '失败', running: '进行中', succeeded: '成功' }[value] || value)
}
function statusClass(value) {
  return ({ published: 'badge-moss', succeeded: 'badge-moss', indexed: 'badge-gold', validated: 'badge-gold', markdown_ready: 'badge-gold', chunking: 'badge-gold', chunk_ready: 'badge-gold', indexing: 'badge-gold', running: 'badge-gold', failed: 'badge-berry', archived: 'badge-berry' }[value] || '')
}
function modeLabel(value) { return ({ auto: '自动切分', manual: '手动切分', auto_then_manual: '自动后调优', legacy: '历史分片' }[value] || value) }
function chunkSetDisplayStatus(chunkSet) {
  if (chunkSet && detail.value?.source.status === 'published' && detail.value.source.active_chunk_set_id === chunkSet.id) return 'published'
  return chunkSet?.status || ''
}
function jobLabel(value) { return ({ convert: '转换 Markdown', auto_chunk: '自动切分', manual_chunk: '手动切分', index: '显式向量化', reindex: '重新索引' }[value] || value) }
function formatDate(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—' }
function formatSimilarity(value) { return Number(value || 0).toFixed(4) }
function showNotice(text, type = 'success') { notice.value = { text, type } }
function goKnowledge() { router.push('/company-knowledge') }
function replaceSourceQuery(id) { router.replace({ query: id ? { source: id } : {} }) }
function clearValidationResult() {
  retrievalResult.value = null
  previewedQuestion.value = ''
}
function cleanMarkdownText(value) {
  return value.replace(/[`*_>#\[\]()]/g, ' ').replace(/\s+/g, ' ').trim()
}
function markdownQuestionCandidates(markdown) {
  const headings = []
  const candidates = []
  for (const line of (markdown || '').split(/\r?\n/)) {
    const heading = line.match(/^(#{1,6})\s+(.+)$/)
    if (heading) {
      const level = heading[1].length
      headings.splice(level - 1)
      headings[level - 1] = cleanMarkdownText(heading[2])
      continue
    }
    const content = cleanMarkdownText(line)
    if (content.length >= 12) candidates.push({ topic: headings.filter(Boolean).join(' / '), content })
  }
  return candidates
}
function regenerateAutoQuestion() {
  clearValidationResult()
  const candidates = markdownQuestionCandidates(detail.value?.markdown)
  const selected = candidates[Math.floor(Math.random() * candidates.length)]
  const fallbackChunk = verificationChunks.value[Math.floor(Math.random() * verificationChunks.value.length)]
  const topic = selected?.topic || fallbackChunk?.section_path || cleanMarkdownText(selected?.content || fallbackChunk?.content || '')
  if (!topic) { autoQuestion.value = ''; expectedChunkId.value = ''; return }
  const templates = [
    `请说明“${topic}”的具体规定。`,
    `关于“${topic}”，资料中有哪些要求？`,
    `“${topic}”需要如何执行？`,
  ]
  autoQuestion.value = templates[Math.floor(Math.random() * templates.length)]
  expectedChunkId.value = ''
}
function changeValidationMode() {
  clearValidationResult()
  if (validationMode.value === 'auto') regenerateAutoQuestion()
}

async function loadSources() {
  const res = await apiAdminCompanyKnowledgeSources('policy', 'all', 1, 100)
  if (res.success) sources.value = res.data.items
}
async function loadJobs() {
  const res = await apiAdminCompanyKnowledgeJobs()
  if (res.success) jobs.value = res.data.items
}
async function loadDetail() {
  if (!sourceId.value) { detail.value = null; return }
  const res = await apiAdminCompanyKnowledgeSource(sourceId.value, activeChunkSetId.value)
  if (!res.success) { showNotice(res.message || '加载资料失败', 'error'); return }
  detail.value = res.data
  activeChunkSetId.value = res.data.selected_chunk_set_id || ''
  draftChunks.value = res.data.chunks.map((item) => ({ section_path: item.section_path || '', content: item.content || '' }))
  autoQuestion.value = ''
  manualQuestion.value = ''
  expectedChunkId.value = ''
  clearValidationResult()
  validationOpen.value = ['indexed', 'validated'].includes(selectedSetDisplayStatus.value)
  if (validationOpen.value && validationMode.value === 'auto') regenerateAutoQuestion()
}
async function refreshSourceContext() {
  await loadSources()
  if (sourceId.value && sources.value.some((item) => item.id === sourceId.value)) await loadDetail()
}
function changeSource() {
  activeChunkSetId.value = ''
  replaceSourceQuery(sourceId.value)
  loadDetail()
}

function openUpload() { upload.value = emptyUpload(); uploadOpen.value = true }
function pickFile(event) { upload.value.file = event.target.files?.[0] || null }
async function submitUpload() {
  if (!canUpload.value) return
  uploading.value = true
  try {
    const res = await apiAdminCompanyKnowledgeUpload(upload.value)
    if (!res.success) { showNotice(res.message || '导入失败', 'error'); return }
    uploadOpen.value = false
    sourceId.value = res.data.source.id
    activeChunkSetId.value = ''
    replaceSourceQuery(sourceId.value)
    await Promise.all([loadSources(), loadJobs()])
    await loadDetail()
    showNotice('资料已转换为 Markdown，可以继续切分。')
  } catch (error) { showNotice(error.message || '导入失败', 'error') } finally { uploading.value = false }
}
function openEdit() {
  const source = detail.value?.source
  if (!source) return
  edit.value = {
    id: source.id,
    title: source.title,
    version: source.version,
    effective_at: source.effective_at?.slice(0, 10) || '',
    expires_at: source.expires_at?.slice(0, 10) || '',
    category: source.category || '',
  }
  editOpen.value = true
}
async function submitEdit() {
  if (!canSaveEdit.value) return
  savingEdit.value = true
  try {
    const res = await apiAdminCompanyKnowledgeUpdate(edit.value.id, {
      title: edit.value.title.trim(),
      version: edit.value.version.trim(),
      effective_at: edit.value.effective_at,
      expires_at: edit.value.expires_at || null,
      category: edit.value.category.trim(),
    })
    if (!res.success) { showNotice(res.message || '保存失败', 'error'); return }
    editOpen.value = false
    await refreshSourceContext()
    showNotice('资料信息已更新。')
  } catch (error) { showNotice(error.message || '保存失败', 'error') } finally { savingEdit.value = false }
}
async function archiveSource() {
  const source = detail.value?.source
  if (!source || !confirm(`下架「${source.title} ${source.version}」？下架后不再参与新问答。`)) return
  sourceActing.value = true
  try {
    const res = await apiAdminCompanyKnowledgeArchive(source.id)
    if (!res.success) { showNotice(res.message || '下架失败', 'error'); return }
    await refreshSourceContext()
    showNotice('资料已下架。')
  } catch (error) { showNotice(error.message || '下架失败', 'error') } finally { sourceActing.value = false }
}
async function removeSource() {
  const source = detail.value?.source
  if (!source || !confirm(`删除已下架资料「${source.title} ${source.version}」？此操作不可恢复。`)) return
  sourceActing.value = true
  try {
    const res = await apiAdminCompanyKnowledgeDelete(source.id)
    if (!res.success) { showNotice(res.message || '删除失败', 'error'); return }
    sourceId.value = ''
    activeChunkSetId.value = ''
    detail.value = null
    replaceSourceQuery('')
    await loadSources()
    showNotice('已删除下架资料。')
  } catch (error) { showNotice(error.message || '删除失败', 'error') } finally { sourceActing.value = false }
}

async function createDraft() {
  if (!sourceId.value) return
  creating.value = true
  try {
    const res = await apiAdminCompanyKnowledgeCreateChunkSet(sourceId.value, { mode: mode.value, rule: mode.value === 'manual' ? {} : rule.value })
    if (!res.success) { showNotice(res.message || '生成失败', 'error'); return }
    activeChunkSetId.value = res.data.chunk_set.id
    await Promise.all([loadDetail(), loadSources(), loadJobs()])
    showNotice('已生成分片草稿，可以继续编辑。')
  } catch (error) { showNotice(error.message || '生成失败', 'error') } finally { creating.value = false }
}
function addChunk() { draftChunks.value.push({ section_path: '', content: '' }) }
function removeChunk(index) { draftChunks.value.splice(index, 1) }
async function saveDraft() {
  if (!selectedSet.value) return false
  saving.value = true
  try {
    const res = await apiAdminCompanyKnowledgeUpdateChunkSet(sourceId.value, selectedSet.value.id, draftChunks.value)
    if (!res.success) { showNotice(res.message || '保存失败', 'error'); return false }
    await loadDetail()
    showNotice('分片草稿已保存。')
    return true
  } catch (error) { showNotice(error.message || '保存失败', 'error'); return false } finally { saving.value = false }
}
async function confirmDraft() {
  if (!await saveDraft() || !confirm('确认后分片将锁定，之后才能执行向量化。')) return
  const res = await apiAdminCompanyKnowledgeConfirmChunkSet(sourceId.value, selectedSet.value.id)
  if (res.success) { await Promise.all([loadDetail(), loadSources()]); showNotice('分片已确认，可以向量化。') }
  else showNotice(res.message || '确认失败', 'error')
}
async function indexDraft() {
  if (!selectedSet.value || !confirm('开始调用 Embedding 模型向量化这些已确认分片？')) return
  indexing.value = true
  try {
    const res = await apiAdminCompanyKnowledgeIndexChunkSet(sourceId.value, selectedSet.value.id)
    if (!res.success) { showNotice(res.message || '向量化失败', 'error'); return }
    await Promise.all([loadDetail(), loadSources(), loadJobs()])
    validationOpen.value = true
    await nextTick()
    validationPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    showNotice('向量化完成，请在下方完成检索验证。')
  } catch (error) { showNotice(error.message || '向量化失败', 'error') } finally { indexing.value = false }
}
async function openValidation() {
  validationOpen.value = true
  if (validationMode.value === 'auto' && !autoQuestion.value) regenerateAutoQuestion()
  await nextTick()
  validationPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
async function previewRetrieval() {
  const question = activeVerificationQuestion.value
  if (!selectedSet.value || !question) return
  verifying.value = true
  try {
    const res = await apiAdminCompanyKnowledgePreviewChunkSet(sourceId.value, selectedSet.value.id, {
      question, top_k: verificationTopK.value, expected_chunk_ids: expectedChunkId.value ? [expectedChunkId.value] : [],
    })
    if (res.success) {
      retrievalResult.value = res.data
      previewedQuestion.value = question
      showNotice(res.data.expected_hit === false ? '预期分片未命中，请检查切分或提问。' : '检索验证结果已更新。', res.data.expected_hit === false ? 'error' : 'success')
    } else showNotice(res.message || '检索验证失败', 'error')
  } catch (error) { showNotice(error.message || '检索验证失败', 'error') } finally { verifying.value = false }
}
async function confirmValidation() {
  if (!selectedSet.value || !canConfirmValidation.value || !confirm('确认当前分片已完成检索验证并允许发布？')) return
  const question = activeVerificationQuestion.value
  validating.value = true
  try {
    const res = await apiAdminCompanyKnowledgeValidateChunkSet(sourceId.value, selectedSet.value.id, {
      question, top_k: verificationTopK.value, expected_chunk_ids: expectedChunkId.value ? [expectedChunkId.value] : [],
    })
    if (res.success) { await Promise.all([loadDetail(), loadSources()]); validationOpen.value = true; showNotice('检索验证已确认，可以直接发布。') }
    else showNotice(res.message || '确认失败', 'error')
  } catch (error) { showNotice(error.message || '确认失败', 'error') } finally { validating.value = false }
}
async function publishSource() {
  const source = detail.value?.source
  if (!source || !confirm(`发布「${source.title} ${source.version}」？同名已发布版本会自动下架。`)) return
  sourceActing.value = true
  try {
    const res = await apiAdminCompanyKnowledgePublish(source.id)
    if (!res.success) { showNotice(res.message || '发布失败', 'error'); return }
    await refreshSourceContext()
    showNotice('资料已发布。')
  } catch (error) { showNotice(error.message || '发布失败', 'error') } finally { sourceActing.value = false }
}
function canDeleteJob(job) { return !['queued', 'running'].includes(job.status) }
async function removeJob(job) {
  if (!confirm(`删除「${jobLabel(job.job_type)}」处理任务记录？此操作不可恢复。`)) return
  deletingJobId.value = job.id
  try {
    const res = await apiAdminCompanyKnowledgeDeleteJob(job.id)
    if (res.success) { await loadJobs(); showNotice('处理任务记录已删除。') }
    else showNotice(res.message || '删除失败', 'error')
  } catch (error) { showNotice(error.message || '删除失败', 'error') } finally { deletingJobId.value = '' }
}

watch(() => route.query.source, (value) => {
  if (typeof value === 'string' && value !== sourceId.value) {
    sourceId.value = value
    activeChunkSetId.value = ''
    loadDetail()
  }
})

onMounted(async () => {
  await Promise.all([loadSources(), loadJobs()])
  if (typeof route.query.source === 'string') sourceId.value = route.query.source
  if (sourceId.value) await loadDetail()
})
</script>

<style scoped>
.page-head, .source-head, .workspace-head, .jobs-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }
.page-actions, .source-actions, .workspace-actions, .workflow-action { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.source-picker { display:flex; align-items:center; gap:12px; margin:18px 0; flex-wrap:wrap; }
.source-picker label, .source-picker select { font-size:13px; }
.source-picker select, .set-select, .rule-fields input, .chunk-editor input, .chunk-editor textarea, .validation-fields textarea, .validation-fields select { border:1px solid var(--line); border-radius:6px; background:var(--card); color:var(--ink); font:inherit; }
.source-picker select { min-width:280px; max-width:100%; padding:8px 10px; }
.row-btn { border:1px solid var(--line); border-radius:6px; background:transparent; color:var(--ink-soft); padding:4px 8px; font-size:12px; }
.row-btn:hover { border-color:var(--gold); color:var(--ink); }
.row-btn.danger:hover { border-color:var(--berry); color:var(--berry); }
.row-btn:disabled { opacity:.5; cursor:not-allowed; }
.notice { margin:12px 0; padding:9px 12px; border-radius:6px; font-size:13px; }
.notice.success { background:#E4EEE6; color:var(--moss); }
.notice.error { background:#F6E4E2; color:var(--berry); }
.source-head { margin:22px 0 12px; }
.source-head h2, .workspace-head h2 { font-size:16px; }
.source-head p, .workspace-head p, .jobs-head p { margin-top:4px; color:var(--ink-soft); font-size:12px; }
.set-select { max-width:280px; padding:7px 9px; font-size:12px; }
.markdown-source { margin-bottom:14px; border:1px solid var(--line); border-radius:6px; background:var(--card); }
.markdown-source summary { cursor:pointer; padding:10px 12px; color:var(--ink-soft); font-size:13px; }
.markdown-source pre { max-height:300px; overflow:auto; margin:0; padding:0 12px 12px; white-space:pre-wrap; overflow-wrap:anywhere; font:12px/1.65 ui-monospace, SFMono-Regular, Consolas, monospace; }
.controls { margin-bottom:18px; }
.control-title { font-size:14px; font-weight:700; margin-bottom:10px; }
.mode-options { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; }
.mode-option { display:flex; gap:8px; min-height:64px; padding:9px; border:1px solid var(--line); border-radius:6px; cursor:pointer; }
.mode-option.selected { border-color:var(--gold); background:var(--gold-soft); }
.mode-option input { margin-top:2px; accent-color:var(--gold); }
.mode-option b, .mode-option small { display:block; }
.mode-option b { font-size:13px; }
.mode-option small { margin-top:4px; color:var(--ink-soft); font-size:11px; line-height:1.35; }
.rule-fields { display:flex; gap:16px; margin:12px 0; flex-wrap:wrap; }
.rule-fields label { display:flex; align-items:center; gap:6px; color:var(--ink-soft); font-size:12px; }
.rule-fields input { width:82px; padding:6px 8px; }
.chunk-workspace { margin-top:24px; }
.workspace-head { align-items:center; margin-bottom:12px; }
.indexed-note { color:var(--moss); font-size:13px; }
.retrieval-validation { margin:0 0 18px; padding:16px; border:1px solid var(--gold); border-radius:6px; background:var(--card); scroll-margin-top:18px; }
.validation-head, .validation-actions, .retrieval-result-head { display:flex; justify-content:space-between; align-items:center; gap:12px; }
.validation-head h2 { font-size:15px; }
.validation-head p { margin-top:4px; color:var(--ink-soft); font-size:12px; }
.validation-status { color:var(--moss); font-size:12px; white-space:nowrap; }
.validation-mode { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; margin-top:12px; }
.validation-mode-option { display:flex; gap:8px; min-height:54px; padding:9px; border:1px solid var(--line); border-radius:6px; cursor:pointer; }
.validation-mode-option.selected { border-color:var(--gold); background:var(--gold-soft); }
.validation-mode-option input { margin-top:2px; accent-color:var(--gold); }
.validation-mode-option b, .validation-mode-option small { display:block; }
.validation-mode-option b { font-size:13px; }
.validation-mode-option small { margin-top:3px; color:var(--ink-soft); font-size:11px; line-height:1.35; }
.auto-question { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-top:10px; padding:10px; border:1px solid var(--line); border-radius:6px; background:var(--bg); }
.auto-question b { font-size:12px; color:var(--ink-soft); }
.auto-question p { margin-top:4px; font-size:13px; line-height:1.5; }
.auto-question .btn-ghost { flex:none; }
.manual-question { display:block; margin-top:10px; color:var(--ink-soft); font-size:12px; }
.manual-question textarea { display:block; box-sizing:border-box; width:100%; margin-top:5px; padding:8px 9px; border:1px solid var(--line); border-radius:6px; background:var(--card); color:var(--ink); font:inherit; resize:vertical; line-height:1.5; }
.validation-fields { display:grid; grid-template-columns:180px 100px; justify-content:end; gap:10px; margin-top:12px; }
.validation-fields label { color:var(--ink-soft); font-size:12px; }
.validation-fields textarea, .validation-fields select { display:block; box-sizing:border-box; width:100%; margin-top:5px; padding:8px 9px; }
.validation-fields textarea { resize:vertical; line-height:1.5; }
.validation-actions { justify-content:flex-start; margin-top:10px; }
.validation-summary { margin:12px 0; padding:9px 10px; border-left:3px solid var(--moss); background:var(--bg); color:var(--ink-soft); font-size:12px; line-height:1.55; }
.validation-summary.is-miss { border-color:var(--berry); color:var(--berry); }
.retrieval-results, .chunk-list { display:grid; gap:8px; }
.retrieval-result { padding:10px; border:1px solid var(--line); border-radius:6px; background:var(--card); }
.retrieval-result.is-qualified { border-left:3px solid var(--moss); }
.retrieval-result.is-low { border-left:3px solid var(--gold); }
.retrieval-result-head b { font-size:13px; }
.retrieval-result-head span { color:var(--moss); font:600 13px ui-monospace, SFMono-Regular, Consolas, monospace; }
.retrieval-result p { margin-top:4px; color:var(--ink-soft); font-size:11px; }
.retrieval-result em { margin-left:7px; color:var(--moss); font-style:normal; }
.retrieval-result details { margin-top:8px; }
.retrieval-result summary { cursor:pointer; color:var(--ink-soft); font-size:12px; }
.retrieval-result pre { max-height:220px; overflow:auto; margin:7px 0 0; padding:8px; background:var(--bg); color:var(--ink); white-space:pre-wrap; overflow-wrap:anywhere; font:11px/1.55 ui-monospace, SFMono-Regular, Consolas, monospace; }
.chunk-list { gap:12px; }
.chunk-editor { position:relative; padding:13px; border:1px solid var(--line); border-radius:6px; background:var(--card); }
.chunk-editor-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; font-size:13px; }
.icon-delete { width:26px; height:26px; border:1px solid var(--line); border-radius:50%; background:transparent; color:var(--berry); font-size:18px; line-height:1; }
.chunk-editor label { display:block; margin-top:9px; color:var(--ink-soft); font-size:12px; }
.chunk-editor input, .chunk-editor textarea { display:block; box-sizing:border-box; width:100%; margin-top:5px; padding:8px 9px; }
.chunk-editor textarea { resize:vertical; line-height:1.55; }
.chunk-editor input:disabled, .chunk-editor textarea:disabled { background:var(--bg); color:var(--ink-soft); }
.chunk-count { margin-top:7px; color:var(--ink-soft); font-size:11px; text-align:right; }
.jobs-section { margin-top:30px; }
.jobs-head { align-items:center; margin-bottom:10px; }
.jobs-head h2 { font-size:15px; }
.jobs-list { padding:0; }
.job-row { min-height:54px; display:grid; grid-template-columns:minmax(160px,1fr) 120px 76px minmax(0,1fr) 56px; gap:12px; align-items:center; padding:10px 14px; border-bottom:1px solid var(--line); }
.job-row:last-child { border-bottom:none; }
.job-row b { display:block; font-size:13px; }
.source-meta, .job-count { color:var(--ink-soft); font-size:12px; }
.source-meta { display:block; margin-top:3px; }
.error-text { color:var(--berry); font-size:12px; overflow-wrap:anywhere; }
.job-delete { justify-self:end; }
.empty-jobs, .empty-state { padding:36px 12px; color:var(--ink-soft); text-align:center; font-size:13px; }
.empty-state { margin-top:48px; }
.modal-mask { position:fixed; inset:0; z-index:30; background:rgba(30,53,44,.42); display:flex; align-items:center; justify-content:center; padding:20px; }
.modal { width:min(520px, 100%); max-height:calc(100vh - 40px); overflow:auto; border-radius:8px; background:var(--card); box-shadow:0 20px 48px rgba(30,53,44,.24); padding:20px; }
.modal-title { display:flex; justify-content:space-between; align-items:center; margin-bottom:18px; font-size:16px; }
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
.upload-tip { border-left:3px solid var(--gold); padding-left:9px; margin:0 0 16px; color:var(--ink-soft); font-size:12px; }
.submit-upload { width:100%; }
@media (max-width:760px) {
  .page-head, .source-head, .workspace-head, .jobs-head { align-items:stretch; flex-direction:column; }
  .source-picker { align-items:stretch; flex-direction:column; }
  .source-picker select, .set-select { max-width:none; width:100%; }
  .mode-options, .validation-mode, .validation-fields, .form-row { grid-template-columns:1fr; }
  .validation-fields { justify-content:stretch; }
  .auto-question { align-items:stretch; flex-direction:column; }
  .form-row { gap:0; }
  .job-row { grid-template-columns:1fr 76px; }
  .job-row .error-text { grid-column:1 / -1; }
}
</style>
