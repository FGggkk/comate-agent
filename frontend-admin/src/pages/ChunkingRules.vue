<template>
  <div>
    <div class="page-head">
      <div>
        <div class="page-title">RAG 执行流程</div>
        <div class="page-sub">上传资料、确认分片、向量化、人工问答验证并发布</div>
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
        <button v-if="detail.source.status === 'archived'" class="row-btn moss" :disabled="sourceActing" @click="restoreSource">上架</button>
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
            <button class="btn-gold" @click="openValidation">问答验证</button>
          </div>
          <div v-else-if="selectedSetDisplayStatus === 'validated'" class="workflow-action">
            <span class="indexed-note">问答验证已确认</span>
            <button class="btn-gold" :disabled="sourceActing" @click="publishSource">{{ sourceActing ? '发布中…' : '发布' }}</button>
          </div>
          <span v-else-if="selectedSetDisplayStatus === 'published'" class="indexed-note">已发布</span>
        </div>

        <section v-if="(selectedSetDisplayStatus === 'indexed' || selectedSetDisplayStatus === 'validated') && validationOpen" ref="validationPanel" class="retrieval-validation">
          <div class="validation-head">
            <div>
              <h2>问答验证</h2>
              <p>选择预期切分段并手动提问，生成 RAG 回答后与全部切片进行匹配和质量评估。</p>
            </div>
            <span class="validation-status">{{ selectedSetDisplayStatus === 'validated' ? '已确认' : '待确认' }}</span>
          </div>
          <label v-if="validationRuns.length" class="validation-run-picker">验证记录
            <select v-model="selectedValidationRunId">
              <option value="">请选择验证记录</option>
              <option v-for="run in validationRuns" :key="run.id" :value="run.id">{{ formatDate(run.created_at) }} · {{ validationModeLabel(run.mode) }} · {{ statusLabel(run.status) }}</option>
            </select>
          </label>
          <label class="manual-question">预期切分段
            <select :value="expectedChunkId" :disabled="runningValidation" @change="selectExpectedChunk">
              <option value="">请选择本问题应命中的切分段</option>
              <option v-for="(chunk, index) in verificationChunks" :key="chunk.id" :value="String(chunk.id)">第 {{ index + 1 }} 段 · {{ chunk.section_path || '未标注章节' }}</option>
            </select>
          </label>
          <label class="manual-question">验证问题<textarea v-model="manualQuestion" :disabled="runningValidation" rows="3" maxlength="2000" placeholder="如：员工年假如何申请？" @input="clearValidationInput" /></label>
          <div class="validation-actions">
            <button class="btn-gold" :disabled="runningValidation" @click="runAnswerValidation">{{ runningValidation ? '验证运行中…' : '执行问答验证' }}</button>
            <span v-if="!runningValidation && activeValidationRun?.status === 'succeeded'" class="validation-complete">执行完成</span>
            <span v-else-if="!runningValidation && activeValidationRun?.status === 'failed'" class="validation-failed">执行失败</span>
            <button v-if="selectedSetDisplayStatus === 'indexed'" class="btn-ghost" :disabled="confirmingValidation || !canConfirmValidation" @click="confirmValidation">{{ confirmingValidation ? '确认中…' : '确认问答验证' }}</button>
            <button v-if="selectedSetDisplayStatus === 'validated'" class="btn-gold" :disabled="sourceActing" @click="publishSource">{{ sourceActing ? '发布中…' : '发布' }}</button>
          </div>
          <p v-if="runningValidation" class="validation-summary">验证请求已提交，正在检索、生成回答并评估结果；完成后会自动展示结果。</p>
          <template v-if="activeValidationRun">
            <p v-if="activeValidationRun.status === 'failed'" class="validation-summary is-miss">本次运行失败：{{ activeValidationRun.error_message || '请稍后重试。' }}</p>
            <template v-else>
              <div class="validation-question-result"><span>验证问题</span><b>{{ activeValidationRun.question }}</b></div>
              <section class="answer-evaluation">
                <div class="answer-evaluation-head"><h3>RAG 回答</h3><span :class="['badge', statusClass(activeValidationRun.evaluation_verdict)]">{{ evaluationLabel(activeValidationRun.evaluation_verdict) }}</span></div>
                <pre>{{ activeValidationRun.answer || '未生成回答。' }}</pre>
                <div class="evaluation-metrics">
                  <span>回答-所选切分段：<b>{{ formatOptionalSimilarity(activeValidationRun.retrieval?.answer_match?.expected_similarity) }}</b></span>
                  <span>回答匹配排名：<b>Top {{ activeValidationRun.retrieval?.answer_match?.expected_rank || '—' }}</b></span>
                  <span>正确性：<b>{{ formatOptionalSimilarity(activeValidationRun.correctness_score) }}</b></span>
                  <span>忠实性：<b>{{ formatOptionalSimilarity(activeValidationRun.faithfulness_score) }}</b></span>
                </div>
                <p class="evaluation-reason">{{ activeValidationRun.evaluation_reason || '未选择预期分片，未进行证据评估。' }}</p>
              </section>
              <details v-if="activeValidationRun.retrieval?.answer_match?.items?.length" class="full-match-results" open>
                <summary>回答与全部 {{ activeValidationRun.retrieval.answer_match.total_chunks }} 个切片的匹配结果</summary>
                <p>所选切分段的回答匹配度为 {{ formatOptionalSimilarity(activeValidationRun.retrieval.answer_match.expected_similarity) }}，排名 Top {{ activeValidationRun.retrieval.answer_match.expected_rank || '—' }}。</p>
                <div class="retrieval-results">
                  <article v-for="(item, index) in activeValidationRun.retrieval.answer_match.items" :key="item.chunk_id" :class="['retrieval-result', item.is_expected ? 'is-expected' : '']">
                    <div class="retrieval-result-head"><b>Top {{ index + 1 }} · {{ item.section_path || '未标注章节' }}</b><span>{{ formatOptionalSimilarity(item.similarity) }}</span></div>
                    <p><em v-if="item.is_expected">所选切分段</em><span v-else>非所选切分段</span></p>
                    <details><summary>查看分片正文</summary><pre>{{ item.content }}</pre></details>
                  </article>
                </div>
              </details>
            </template>
          </template>
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  apiAdminCompanyKnowledgeArchive,
  apiAdminCompanyKnowledgeConfirmValidationRun,
  apiAdminCompanyKnowledgeConfirmChunkSet,
  apiAdminCompanyKnowledgeCreateValidationRun,
  apiAdminCompanyKnowledgeCreateChunkSet,
  apiAdminCompanyKnowledgeDelete,
  apiAdminCompanyKnowledgeDeleteJob,
  apiAdminCompanyKnowledgeIndexChunkSet,
  apiAdminCompanyKnowledgeJobs,
  apiAdminCompanyKnowledgePublish,
  apiAdminCompanyKnowledgeSource,
  apiAdminCompanyKnowledgeSources,
  apiAdminCompanyKnowledgeUpdate,
  apiAdminCompanyKnowledgeUpdateChunkSet,
  apiAdminCompanyKnowledgeUpload,
  apiAdminCompanyKnowledgeValidationRuns,
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
const runningValidation = ref(false)
const confirmingValidation = ref(false)
const sourceActing = ref(false)
const notice = ref(null)
const manualQuestion = ref('')
const expectedChunkId = ref('')
const validationRuns = computed(() => detail.value?.validation_runs || [])
const selectedValidationRunId = ref('')
const pendingValidationRunId = ref('')
let validationPollingTimer = null
let validationPollingDeadline = 0
let validationPollingFailures = 0
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
const activeValidationRun = computed(() => validationRuns.value.find((item) => item.id === selectedValidationRunId.value) || validationRuns.value[0] || null)
const canConfirmValidation = computed(() => {
  const run = activeValidationRun.value
  return selectedSetDisplayStatus.value === 'indexed' && run?.status === 'succeeded' && run?.retrieval?.can_confirm === true
})
const canUpload = computed(() => upload.value.file && upload.value.title.trim() && upload.value.version.trim() && upload.value.effective_at)
const canSaveEdit = computed(() => edit.value.id && edit.value.title.trim() && edit.value.version.trim() && edit.value.effective_at)

function emptyUpload() { return { file: null, title: '', version: '', effective_at: '', expires_at: '', category: '', knowledge_type: 'policy' } }
function emptyEdit() { return { id: '', title: '', version: '', effective_at: '', expires_at: '', category: '' } }
function statusLabel(value) {
  return ({ markdown_ready: '待切分', chunking: '切分草稿', chunk_ready: '待向量化', indexed: '待问答验证', validated: '待发布', indexing: '向量化中', published: '已发布', archived: '已下架', draft: '草稿', confirmed: '已确认', superseded: '已替换', failed: '失败', running: '进行中', succeeded: '成功', skipped: '未评估' }[value] || value)
}
function statusClass(value) {
  return ({ published: 'badge-moss', succeeded: 'badge-moss', pass: 'badge-moss', indexed: 'badge-gold', validated: 'badge-gold', markdown_ready: 'badge-gold', chunking: 'badge-gold', chunk_ready: 'badge-gold', indexing: 'badge-gold', running: 'badge-gold', skipped: 'badge-gold', failed: 'badge-berry', fail: 'badge-berry', archived: 'badge-berry' }[value] || '')
}
function modeLabel(value) { return ({ auto: '自动切分', manual: '手动切分', auto_then_manual: '自动后调优', legacy: '历史分片' }[value] || value) }
function validationModeLabel() { return '人工验证' }
function evaluationLabel(value) { return ({ pass: '通过', fail: '未通过', pending: '待评估', skipped: '未评估' }[value] || value || '未评估') }
function chunkSetDisplayStatus(chunkSet) {
  if (chunkSet && detail.value?.source.status === 'published' && detail.value.source.active_chunk_set_id === chunkSet.id) return 'published'
  return chunkSet?.status || ''
}
function jobLabel(value) { return ({ convert: '转换 Markdown', auto_chunk: '自动切分', manual_chunk: '手动切分', index: '显式向量化', reindex: '重新索引' }[value] || value) }
function formatDate(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—' }
function formatOptionalSimilarity(value) { return value === null || value === undefined ? '—' : Number(value).toFixed(4) }
function showNotice(text, type = 'success') { notice.value = { text, type } }
function goKnowledge() { router.push('/company-knowledge') }
function replaceSourceQuery(id) { router.replace({ query: id ? { source: id } : {} }) }
function clearValidationInput() { selectedValidationRunId.value = '' }
function selectExpectedChunk(event) {
  expectedChunkId.value = String(event.target.value || '')
  clearValidationInput()
}
function validationRunMessage(run) {
  if (run.status === 'running') return { text: '问答验证已提交，正在后台生成回答和评估结果。', type: 'success' }
  if (run.status === 'failed') return { text: run.error_message || '问答验证运行失败', type: 'error' }
  return run.retrieval?.can_confirm
    ? { text: '问答验证通过，可以确认发布。', type: 'success' }
    : { text: '问答验证完成，请查看检索和证据评估结果。', type: 'error' }
}
function stopValidationPolling({ clearPending = false } = {}) {
  if (validationPollingTimer) window.clearInterval(validationPollingTimer)
  validationPollingTimer = null
  validationPollingDeadline = 0
  validationPollingFailures = 0
  if (clearPending) pendingValidationRunId.value = ''
}
function finishValidationRun(run, { notify = true } = {}) {
  selectedValidationRunId.value = run.id
  runningValidation.value = false
  stopValidationPolling({ clearPending: true })
  if (notify) {
    const message = validationRunMessage(run)
    showNotice(message.text, message.type)
  }
}
async function pollValidationRun(runId, pollingSourceId, pollingChunkSetId) {
  if (
    !runningValidation.value
    || pendingValidationRunId.value !== runId
    || sourceId.value !== pollingSourceId
    || selectedSet.value?.id !== pollingChunkSetId
  ) {
    // 热更新或切换资料时，旧轮询仍可能执行一次，必须一并清理界面的运行态。
    runningValidation.value = false
    stopValidationPolling({ clearPending: true })
    return
  }
  try {
    const runs = await loadValidationRuns({ notify: false, throwOnError: true })
    validationPollingFailures = 0
    const targetRun = runs.find((item) => item.id === runId)
    if (targetRun && targetRun.status !== 'running') {
      finishValidationRun(targetRun)
      await loadDetail()
      return
    }
    if (Date.now() >= validationPollingDeadline) {
      runningValidation.value = false
      stopValidationPolling({ clearPending: true })
      showNotice('验证超过 90 秒仍未完成，请刷新验证记录后重试。', 'error')
    }
  } catch (error) {
    validationPollingFailures += 1
    if (validationPollingFailures >= 3 || Date.now() >= validationPollingDeadline) {
      runningValidation.value = false
      stopValidationPolling({ clearPending: true })
      showNotice(error.message || '连续加载验证结果失败，请检查后端服务后重试。', 'error')
    }
  }
}
function startValidationPolling(runId, pollingSourceId, pollingChunkSetId) {
  stopValidationPolling()
  pendingValidationRunId.value = runId
  validationPollingDeadline = Date.now() + 90000
  const poll = () => { void pollValidationRun(runId, pollingSourceId, pollingChunkSetId) }
  validationPollingTimer = window.setInterval(poll, 2000)
  poll()
}

async function loadSources() {
  const res = await apiAdminCompanyKnowledgeSources('policy', 'all', 1, 100)
  if (res.success) sources.value = res.data.items
}
async function loadJobs() {
  const res = await apiAdminCompanyKnowledgeJobs()
  if (res.success) jobs.value = res.data.items
}
async function fetchValidationRuns(targetSourceId, targetChunkSetId) {
  const res = await apiAdminCompanyKnowledgeValidationRuns(targetSourceId, targetChunkSetId)
  if (!res.success) throw new Error(res.message || '加载问答验证记录失败')
  // 自动验证已停用；历史记录留在数据库中，但不进入当前人工验证流程。
  return (res.data.items || []).filter((item) => item.mode === 'manual')
}
function setValidationRuns(runs) {
  if (detail.value) detail.value.validation_runs = runs
  if (!runs.some((item) => item.id === selectedValidationRunId.value)) {
    selectedValidationRunId.value = runs[0]?.id || ''
  }
  return runs
}
async function loadValidationRuns({ notify = true, throwOnError = false } = {}) {
  if (!sourceId.value || !selectedSet.value) return []
  try {
    return setValidationRuns(await fetchValidationRuns(sourceId.value, selectedSet.value.id))
  } catch (error) {
    if (notify) showNotice(error.message || '加载问答验证记录失败', 'error')
    if (throwOnError) throw error
    return null
  }
}
function resumeRunningValidation() {
  const runningRun = validationRuns.value.find((item) => item.status === 'running')
  if (!runningRun || !sourceId.value || !selectedSet.value) return
  selectedValidationRunId.value = runningRun.id
  runningValidation.value = true
  startValidationPolling(runningRun.id, sourceId.value, selectedSet.value.id)
}
async function loadDetail() {
  if (!sourceId.value) { detail.value = null; return }
  const targetSourceId = sourceId.value
  const targetChunkSetId = activeChunkSetId.value
  stopValidationPolling({ clearPending: true })
  runningValidation.value = false
  detail.value = null
  await nextTick()
  const res = await apiAdminCompanyKnowledgeSource(targetSourceId, targetChunkSetId)
  if (!res.success) { showNotice(res.message || '加载资料失败', 'error'); return }
  const nextDetail = res.data
  const nextChunkSetId = nextDetail.selected_chunk_set_id || ''
  const nextChunkSet = nextDetail.chunk_sets.find((item) => item.id === nextChunkSetId) || null
  const nextChunkSetStatus = nextDetail.source.status === 'published' && nextDetail.source.active_chunk_set_id === nextChunkSetId
    ? 'published'
    : nextChunkSet?.status || ''
  const shouldOpenValidation = ['indexed', 'validated'].includes(nextChunkSetStatus)
  let nextValidationRuns = []
  if (shouldOpenValidation && nextChunkSetId) {
    try {
      nextValidationRuns = await fetchValidationRuns(targetSourceId, nextChunkSetId)
    } catch (error) {
      showNotice(error.message || '加载问答验证记录失败', 'error')
    }
  }
  if (sourceId.value !== targetSourceId) return
  activeChunkSetId.value = nextChunkSetId
  draftChunks.value = nextDetail.chunks.map((item) => ({ section_path: item.section_path || '', content: item.content || '' }))
  manualQuestion.value = ''
  expectedChunkId.value = ''
  selectedValidationRunId.value = ''
  nextDetail.validation_runs = nextValidationRuns
  if (!nextValidationRuns.some((item) => item.id === selectedValidationRunId.value)) {
    selectedValidationRunId.value = nextValidationRuns[0]?.id || ''
  }
  validationOpen.value = shouldOpenValidation
  // 先准备验证记录，再挂载详情区域，避免结果区以空记录状态首次渲染。
  detail.value = nextDetail
  if (shouldOpenValidation) {
    resumeRunningValidation()
  }
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
    showNotice('向量化完成，请在下方完成问答验证。')
  } catch (error) { showNotice(error.message || '向量化失败', 'error') } finally { indexing.value = false }
}
async function openValidation() {
  validationOpen.value = true
  await loadValidationRuns()
  resumeRunningValidation()
  await nextTick()
  validationPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
async function runAnswerValidation() {
  if (!selectedSet.value) return
  if (!expectedChunkId.value) {
    showNotice('请先选择本问题预期命中的切分段。', 'error')
    return
  }
  if (!manualQuestion.value.trim()) {
    showNotice('请输入需要验证的问题。', 'error')
    return
  }
  const pollingSourceId = sourceId.value
  const pollingChunkSetId = selectedSet.value.id
  runningValidation.value = true
  let waitingForBackgroundRun = false
  try {
    const res = await apiAdminCompanyKnowledgeCreateValidationRun(pollingSourceId, pollingChunkSetId, {
      question: manualQuestion.value.trim(),
      expected_chunk_id: expectedChunkId.value,
    })
    if (res.success) {
      const run = res.data.run
      setValidationRuns([run, ...validationRuns.value.filter((item) => item.id !== run.id)])
      selectedValidationRunId.value = run.id
      const message = validationRunMessage(run)
      showNotice(message.text, message.type)
      waitingForBackgroundRun = run.status === 'running'
      if (waitingForBackgroundRun) startValidationPolling(run.id, pollingSourceId, pollingChunkSetId)
      else finishValidationRun(run, { notify: false })
    } else showNotice(res.message || '问答验证失败', 'error')
  } catch (error) { showNotice(error.message || '问答验证失败', 'error') } finally {
    if (!waitingForBackgroundRun) {
      runningValidation.value = false
      stopValidationPolling({ clearPending: true })
    }
  }
}
async function confirmValidation() {
  const run = activeValidationRun.value
  if (!selectedSet.value || !run || !canConfirmValidation.value || !confirm('确认当前问答验证已通过，并允许发布？')) return
  confirmingValidation.value = true
  try {
    const res = await apiAdminCompanyKnowledgeConfirmValidationRun(sourceId.value, selectedSet.value.id, run.id)
    if (res.success) { await Promise.all([loadDetail(), loadSources()]); validationOpen.value = true; showNotice('问答验证已确认，可以直接发布。') }
    else showNotice(res.message || '确认失败', 'error')
  } catch (error) { showNotice(error.message || '确认失败', 'error') } finally { confirmingValidation.value = false }
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
async function restoreSource() {
  const source = detail.value?.source
  if (!source || !confirm(`上架「${source.title} ${source.version}」？恢复后该资料将重新参与新问答。`)) return
  sourceActing.value = true
  try {
    const res = await apiAdminCompanyKnowledgePublish(source.id)
    if (!res.success) { showNotice(res.message || '上架失败', 'error'); return }
    await refreshSourceContext()
    showNotice('资料已重新上架。')
  } catch (error) { showNotice(error.message || '上架失败', 'error') } finally { sourceActing.value = false }
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
onBeforeUnmount(() => stopValidationPolling({ clearPending: true }))
</script>

<style scoped>
.page-head, .source-head, .workspace-head, .jobs-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }
.page-actions, .source-actions, .workspace-actions, .workflow-action { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.source-picker { display:flex; align-items:center; gap:12px; margin:18px 0; flex-wrap:wrap; }
.source-picker label, .source-picker select { font-size:13px; }
.source-picker select, .set-select, .rule-fields input, .chunk-editor input, .chunk-editor textarea { border:1px solid var(--line); border-radius:6px; background:var(--card); color:var(--ink); font:inherit; }
.source-picker select { min-width:280px; max-width:100%; padding:8px 10px; }
.row-btn { border:1px solid var(--line); border-radius:6px; background:transparent; color:var(--ink-soft); padding:4px 8px; font-size:12px; }
.row-btn:hover { border-color:var(--gold); color:var(--ink); }
.row-btn.moss:hover { border-color:var(--moss); color:var(--moss); }
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
.validation-run-picker { display:block; margin-top:12px; color:var(--ink-soft); font-size:12px; }
.validation-run-picker select { display:block; min-width:min(100%, 340px); max-width:100%; margin-top:5px; padding:8px 9px; border:1px solid var(--line); border-radius:6px; background:var(--card); color:var(--ink); font:inherit; }
.validation-mode { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; margin-top:12px; }
.validation-mode-option { display:flex; gap:8px; min-height:54px; padding:9px; border:1px solid var(--line); border-radius:6px; cursor:pointer; }
.validation-mode-option.selected { border-color:var(--gold); background:var(--gold-soft); }
.validation-mode-option input { margin-top:2px; accent-color:var(--gold); }
.validation-mode-option b, .validation-mode-option small { display:block; }
.validation-mode-option b { font-size:13px; }
.validation-mode-option small { margin-top:3px; color:var(--ink-soft); font-size:11px; line-height:1.35; }
.manual-question { display:block; margin-top:10px; color:var(--ink-soft); font-size:12px; }
.manual-question textarea, .manual-question select { display:block; box-sizing:border-box; width:100%; margin-top:5px; padding:8px 9px; border:1px solid var(--line); border-radius:6px; background:var(--card); color:var(--ink); font:inherit; }
.manual-question textarea { resize:vertical; line-height:1.5; }
.validation-actions { justify-content:flex-start; margin-top:10px; }
.validation-complete, .validation-failed { align-self:center; font-size:12px; }
.validation-complete { color:var(--moss); }
.validation-failed { color:var(--berry); }
.validation-summary { margin:12px 0; padding:9px 10px; border-left:3px solid var(--moss); background:var(--bg); color:var(--ink-soft); font-size:12px; line-height:1.55; }
.validation-summary.is-miss { border-color:var(--berry); color:var(--berry); }
.validation-question-result { display:grid; gap:4px; margin-top:12px; padding:10px; border:1px solid var(--line); border-radius:6px; background:var(--bg); }
.validation-question-result span { color:var(--ink-soft); font-size:12px; }
.validation-question-result b { font-size:14px; line-height:1.5; }
.retrieval-results, .chunk-list { display:grid; gap:8px; }
.retrieval-results h3 { margin:4px 0 2px; font-size:13px; }
.retrieval-result { padding:10px; border:1px solid var(--line); border-radius:6px; background:var(--card); }
.retrieval-result-head b { font-size:13px; }
.retrieval-result-head span { color:var(--moss); font:600 13px ui-monospace, SFMono-Regular, Consolas, monospace; }
.retrieval-result p { margin-top:4px; color:var(--ink-soft); font-size:11px; }
.retrieval-result em { margin-left:7px; color:var(--moss); font-style:normal; }
.retrieval-result details { margin-top:8px; }
.retrieval-result summary { cursor:pointer; color:var(--ink-soft); font-size:12px; }
.retrieval-result pre { max-height:220px; overflow:auto; margin:7px 0 0; padding:8px; background:var(--bg); color:var(--ink); white-space:pre-wrap; overflow-wrap:anywhere; font:11px/1.55 ui-monospace, SFMono-Regular, Consolas, monospace; }
.answer-evaluation { margin-top:12px; padding:12px; border:1px solid var(--line); border-radius:6px; background:var(--card); }
.answer-evaluation-head { display:flex; justify-content:space-between; align-items:center; gap:10px; }
.answer-evaluation-head h3 { font-size:14px; }
.answer-evaluation pre { max-height:240px; overflow:auto; margin:10px 0 0; padding:10px; background:var(--bg); color:var(--ink); white-space:pre-wrap; overflow-wrap:anywhere; font:12px/1.6 ui-monospace, SFMono-Regular, Consolas, monospace; }
.evaluation-metrics { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px 12px; margin-top:10px; color:var(--ink-soft); font-size:12px; }
.evaluation-metrics b { color:var(--ink); font-family:ui-monospace, SFMono-Regular, Consolas, monospace; }
.evaluation-reason { margin-top:10px; color:var(--ink-soft); font-size:12px; line-height:1.55; }
.full-match-results { margin-top:12px; padding:12px; border:1px solid var(--line); border-radius:6px; background:var(--bg); }
.full-match-results summary { cursor:pointer; font-size:13px; font-weight:700; }
.full-match-results > p { margin:9px 0; color:var(--ink-soft); font-size:12px; line-height:1.5; }
.retrieval-result.is-expected { border-left:3px solid var(--gold); background:var(--gold-soft); }
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
  .mode-options, .validation-mode, .evaluation-metrics, .form-row { grid-template-columns:1fr; }
  .form-row { gap:0; }
  .job-row { grid-template-columns:1fr 76px; }
  .job-row .error-text { grid-column:1 / -1; }
}
</style>
