<template>
  <div class="scroll">
    <div class="page-title">面试训练</div>

    <!-- 开始页 -->
    <div v-if="!sessionId" class="page-card">
      <div style="margin-bottom:12px;">
        <label class="form-label">简历内容</label>
        <textarea v-model="resume" rows="4" placeholder="粘贴你的简历内容..." class="form-input" style="resize:none;"></textarea>
      </div>
      <div style="margin-bottom:12px;">
        <label class="form-label">目标岗位</label>
        <input v-model="targetRole" placeholder="如：前端开发" class="form-input" />
      </div>
      <div style="margin-bottom:16px;">
        <label class="form-label">目标公司</label>
        <input v-model="targetCompany" placeholder="如：字节跳动" class="form-input" />
      </div>
      <button @click="startInterview" :disabled="state !== 'idle'" class="btn-primary">
        {{ state === 'loading' ? '准备中...' : '开始模拟面试' }}
      </button>

      <!-- 历史记录（最近3条） -->
      <div v-if="!showAllHistory && history.length > 0" style="margin-top:20px;">
        <div class="page-label">历史面试</div>
        <div v-for="s in history.slice(0,3)" :key="s.id" class="page-card" style="margin-top:6px;padding:10px 12px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div style="flex:1;cursor:pointer;" @click="s.status === 'completed' ? showEval(s) : viewHistory(s.id)">
              <div style="font-weight:600;font-size:14px;">{{ s.title || s.target_role || '未命名' }}</div>
              <div style="font-size:12px;color:var(--sub);">
                {{ s.target_company }} · 第{{ s.round_number }}/3轮
                <span :style="{color: s.status === 'completed' ? 'var(--sprout)' : 'var(--honey-deep)'}">{{ s.status === 'completed' ? '✅ 已完成' : '⏳ 进行中' }}</span>
              </div>
            </div>
            <div style="display:flex;gap:4px;">
              <button v-if="s.status === 'completed'" @click.stop="showEval(s)" class="hist-btn" style="color:var(--sprout);">📄 评价</button>
              <button v-else @click.stop="viewHistory(s.id)" class="hist-btn" style="color:var(--honey-deep);">继续 →</button>
            </div>
          </div>
        </div>
        <div v-if="history.length > 3" style="text-align:center;margin-top:8px;">
          <button @click="showAllHistory = true" style="font-size:13px;color:var(--honey);padding:6px 16px;border:1px solid var(--honey-soft);border-radius:var(--r-sm);">查看全部 {{ history.length }} 条</button>
        </div>
      </div>

      <!-- 全部历史记录管理 -->
      <div v-if="showAllHistory" style="margin-top:20px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
          <button @click="showAllHistory = false" style="font-size:18px;padding:4px;color:var(--ink-soft);">←</button>
          <div class="page-label" style="margin:0;">历史面试（{{ history.length }}）</div>
        </div>
        <div v-for="s in history" :key="s.id" class="page-card" style="margin-top:6px;padding:10px 12px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div style="flex:1;cursor:pointer;" @click="renamingId !== s.id && viewHistory(s.id)">
              <div style="font-weight:600;font-size:14px;">
                <template v-if="renamingId === s.id">
                  <input v-model="renameText" @keydown.enter="confirmRename(s)" @blur="confirmRename(s)" @click.stop class="form-input" style="font-size:14px;padding:2px 6px;" autofocus />
                </template>
                <template v-else>{{ s.title || s.target_role || '未命名' }}</template>
              </div>
              <div style="font-size:12px;color:var(--sub);">
                {{ s.target_company }} · 第{{ s.round_number }}/3轮
                <span :style="{color: s.status === 'completed' ? 'var(--sprout)' : 'var(--honey-deep)'}">{{ s.status === 'completed' ? '✅ 已完成' : '⏳ 进行中' }}</span>
              </div>
            </div>
            <div style="display:flex;gap:4px;align-items:center;">
              <button @click.stop="startRename(s)" style="font-size:14px;padding:4px 6px;opacity:.4;">✏️</button>
              <button v-if="s.status === 'completed'" @click.stop="showEval(s)" class="hist-btn" style="color:var(--sprout);">📄 评价</button>
              <button v-else @click.stop="viewHistory(s.id)" class="hist-btn" style="color:var(--honey-deep);">继续 →</button>
              <button @click.stop="deleteHistory(s.id)" style="font-size:14px;padding:4px 8px;color:var(--berry);opacity:.5;">🗑</button>
            </div>
          </div>
        </div>
        <div v-if="history.length === 0" style="text-align:center;font-size:13px;color:var(--sub);padding:20px;">暂无记录</div>
      </div>
    </div>

    <!-- 面试中 -->
    <div v-else class="page-card">
      <!-- 返回按钮 -->
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
        <button @click="backToHistory" style="font-size:20px;padding:4px 8px;color:var(--ink-soft);">← 返回</button>
        <button @click="confirmEnd" style="font-size:12px;padding:4px 10px;border-radius:var(--r-sm);border:1px solid var(--berry);color:var(--berry);">结束面试</button>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:13px;color:var(--sub);margin-bottom:12px;">
        <span>第 {{ currentRound }} / 3 轮</span>
        <span>{{ statusText }}</span>
      </div>

      <!-- 历史问答 -->
      <div v-if="qaHistory.length > 0" style="margin-bottom:12px;">
        <div class="page-label" style="margin:0 0 6px;">历史回答</div>
        <div v-for="(qa, idx) in qaHistory" :key="idx" class="page-card" style="padding:8px 10px;margin-top:4px;">
          <div style="font-size:12px;font-weight:600;margin-bottom:2px;">Q{{ idx+1 }}: <span v-html="renderMd(qa.question)"></span></div>
          <div style="font-size:11px;color:var(--sub);">
            回答：
            <template v-if="editingQA === idx">
              <textarea v-model="editingQAText" rows="2" class="form-input" style="resize:none;font-size:11px;" />
              <button @click="saveQA(qa, idx)" class="btn-primary" style="width:auto;padding:2px 10px;font-size:11px;margin-top:2px;">保存</button>
              <button @click="cancelEditQA" style="padding:2px 10px;font-size:11px;color:var(--sub);">取消</button>
            </template>
            <template v-else>
              {{ qa.answer }}
              <button @click="startEditQA(qa, idx)" style="font-size:10px;color:var(--honey);margin-left:4px;">编辑</button>
            </template>
          </div>
        </div>
      </div>

      <!-- 当前题目 -->
      <div v-if="currentQuestion" class="interview-q">
        <div style="font-size:13px;font-weight:600;margin-bottom:6px;">面试官：</div>
        <div v-html="renderMd(currentQuestion)"></div>
      </div>

      <!-- 轮次切换横幅 -->
      <div v-if="roundBanner" class="round-banner">{{ roundBanner }}</div>

      <!-- 进度条（loading/thinking/evaluating 状态） -->
      <div v-if="state === 'loading' || state === 'thinking' || state === 'evaluating'" class="progress-wrap">
        <div class="progress-bar"><div class="progress-fill" :style="{width: progress + '%'}"></div></div>
        <div class="progress-label">{{ state === 'loading' ? '正在准备面试…' : thinkingLabel }}</div>
        <button v-if="state === 'evaluating'" @click="cancelStream" class="thinking-cancel">取消</button>
      </div>

      <!-- 评估结果（流式） -->
      <div v-if="streamEval" class="interview-eval" style="margin-top:12px;">
        <div style="font-weight:600;font-size:12px;margin-bottom:4px;">评估</div>
        <div v-html="renderMd(streamEval)"></div>
      </div>

      <!-- 输入框（非 thinking/evaluating 状态时显示） -->
      <div v-if="state === 'idle' || state === 'done'" style="margin-top:12px;">
        <textarea v-model="answer" rows="3" placeholder="输入你的回答..." class="form-input" style="resize:none;"></textarea>
        <button @click="submitAnswer" class="btn-primary" style="margin-top:8px;">提交回答</button>
      </div>

      <!-- 控制按钮 -->
      <div v-if="state === 'feedback_done'" class="control-bar">
        <button @click="nextQuestion" class="btn-primary" style="flex:1;">下一题 →</button>
        <button @click="confirmEnd" style="padding:10px 16px;border-radius:var(--r-sm);border:1.5px solid var(--berry);color:var(--berry);font-size:14px;">结束面试</button>
      </div>

      <!-- 结束确认弹窗 -->
      <div v-if="showEndConfirm" class="dialog-overlay" @click="showEndConfirm=false">
        <div class="dialog-box" @click.stop>
          <div style="font-size:16px;font-weight:700;margin-bottom:8px;">确定结束面试吗？</div>
          <div style="font-size:14px;color:var(--sub);margin-bottom:16px;">将生成您的面试总结报告。</div>
          <div style="display:flex;gap:10px;">
            <button @click="showEndConfirm=false" style="flex:1;padding:10px;border-radius:var(--r-sm);border:1.5px solid var(--line);font-size:14px;">取消</button>
            <button @click="doEnd" class="btn-primary" style="flex:1;background:var(--berry);">确定结束</button>
          </div>
        </div>
      </div>

      <!-- 错误提示 -->
      <div v-if="errorMsg" class="interview-eval" style="margin-top:12px;border-left-color:var(--berry);">
        <div style="font-size:12px;color:var(--berry);">{{ errorMsg }}</div>
        <button v-if="state === 'error'" @click="retryAnswer" style="margin-top:4px;font-size:12px;color:var(--sprout);">重试</button>
      </div>

      <!-- 评价报告覆盖层 -->
      <div v-if="evalReport" class="dialog-overlay" @click="closeEval">
        <div class="dialog-box eval-box" @click.stop>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <div class="page-label" style="margin:0;">面试评价报告</div>
            <button @click="closeEval" style="font-size:18px;padding:4px;color:var(--sub);">✕</button>
          </div>
          <div v-if="evalReport.overall_score !== undefined" style="text-align:center;padding:8px 0 16px;">
            <span style="font-size:28px;font-weight:700;color:var(--honey-deep);">{{ evalReport.overall_score }}/100</span>
            <div style="font-size:12px;color:var(--sub);">共 {{ evalReport.questions ? evalReport.questions.length : 0 }} 题</div>
            <div v-if="evalReport.report_generated_at" style="font-size:11px;color:var(--sub);margin-top:4px;">更新于 {{ formatTime(evalReport.report_generated_at) }}</div>
          </div>
          <div style="max-height:60vh;overflow-y:auto;">
            <div v-for="(q, idx) in evalReport.questions || []" :key="idx" class="page-card" style="margin-top:8px;padding:10px;">
              <div style="font-size:13px;font-weight:600;margin-bottom:4px;" v-html="renderMd(q.question)"></div>
              <div style="font-size:11px;color:var(--sub);margin-bottom:4px;">回答：{{ q.answer }}</div>
              <div v-if="q.score !== undefined" style="font-size:12px;margin-bottom:2px;">
                <span :style="{color: q.score/q.max_score >= 0.7 ? 'var(--sprout)' : q.score/q.max_score >= 0.4 ? 'var(--honey-deep)' : 'var(--berry)'}">
                  {{ q.score }}/{{ q.max_score }}分
                </span>
              </div>
              <div style="font-size:11px;color:var(--ink-soft);" v-html="renderMd(q.evaluation)"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { marked } from 'marked'
import { apiStartInterview, apiAnswerQuestionStream, apiGetReport, apiListInterviews, apiNextQuestion, apiEndInterview, apiEditInterviewAnswer, apiDeleteInterview, apiRenameInterview } from '../api/index'

function renderMd(text) {
  if (!text) return ''
  return marked.parse(text)
}

const sessionId = ref('')
const resume = ref('')
const targetRole = ref('')
const targetCompany = ref('')
const currentRound = ref(1)
const currentQuestion = ref('')
const answer = ref('')
const lastEvaluation = ref('')
const statusText = ref('')
const report = ref(null)
const streamEval = ref('')
const errorMsg = ref('')
const thinkingLabel = ref('')
const progress = ref(0)
let progressTimer = null
const history = ref([])
const showEndConfirm = ref(false)
const showAllHistory = ref(false)
const roundBanner = ref('')
const evalReport = ref(null)
const qaHistory = ref([])
const editingQA = ref(-1)
const editingQAText = ref('')
const renamingId = ref('')
const renameText = ref('')
const editingAnswerIdx = ref(-1)
const editingAnswerText = ref('')

// 状态机：idle | loading | thinking | evaluating | done | error
const state = ref('idle')

let abortController = null

async function loadHistory() {
  try {
    const res = await apiListInterviews()
    if (res.sessions) history.value = res.sessions
  } catch {}
}

async function viewHistory(id) {
  try {
    const data = await apiGetReport(id)
    sessionId.value = id
    currentRound.value = data.rounds_completed || 1
    statusText.value = '进行中'
    currentQuestion.value = ''
    streamEval.value = ''
    state.value = 'idle'
    qaHistory.value = []
    if (data.questions && data.questions.length > 0) {
      // 已回答的问题显示为历史
      const answered = data.questions.filter(q => q.answer)
      qaHistory.value = answered
      // 第一个未回答的作为当前问题
      const pending = data.questions.find(q => !q.answer)
      if (pending) currentQuestion.value = pending.question
    }
  } catch {}
}

onMounted(loadHistory)

async function showEval(session) {
  try {
    const res = await apiGetReport(session.id)
    evalReport.value = res
  } catch {}
}

function closeEval() {
  evalReport.value = null
}

async function deleteHistory(id) {
  if (!confirm('确定删除此面试记录？')) return
  try {
    const res = await apiDeleteInterview(id)
    if (res.success) history.value = history.value.filter(s => s.id !== id)
  } catch {}
}

function startRename(s) {
  renamingId.value = s.id
  renameText.value = s.title || s.target_role || ''
}

async function confirmRename(s) {
  if (!renameText.value.trim()) { renamingId.value = ''; return }
  try {
    const res = await apiRenameInterview(s.id, renameText.value.trim())
    if (res.success) { s.title = renameText.value.trim() }
  } catch {}
  renamingId.value = ''
}

function startEditQA(qa, idx) {
  editingQA.value = idx
  editingQAText.value = qa.answer || ''
}

function cancelEditQA() {
  editingQA.value = -1
}

async function saveQA(qa, idx) {
  if (!editingQAText.value.trim()) return
  const newText = editingQAText.value.trim()
  editingQA.value = -1
  try {
    const res = await apiEditInterviewAnswer(sessionId.value, qa.id, newText)
    qa.answer = newText
    if (res.status === 'in_progress') {
      // 删除后续历史
      qaHistory.value = qaHistory.value.slice(0, idx + 1)
      if (res.next_question) {
        currentQuestion.value = res.next_question
        streamEval.value = ''
        state.value = 'idle'
      }
    }
  } catch {}
}

async function startInterview() {
  startProgress()
  state.value = 'loading'
  errorMsg.value = ''
  try {
    const res = await apiStartInterview({
      resume_text: resume.value, target_role: targetRole.value, target_company: targetCompany.value,
    })
    sessionId.value = res.session_id; currentRound.value = res.round; currentQuestion.value = res.question; statusText.value = '面试进行中'; state.value = 'idle'
  } catch { errorMsg.value = '启动失败，请重试'; state.value = 'error' }
}

async function submitAnswer() {
  if (!answer.value.trim()) return
  if (state.value === 'thinking' || state.value === 'evaluating') return

  errorMsg.value = ''
  streamEval.value = ''
  const text = answer.value
  answer.value = ''

  abortController = new AbortController()
  startProgress()
  state.value = 'thinking'
  thinkingLabel.value = '正在分析您的回答…'

  try {
    const response = await fetch(`/api/interview/${sessionId.value}/answer/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('comate_token')}` },
      body: JSON.stringify({ answer: text }),
      signal: abortController.signal,
    })
    if (!response.ok) throw new Error('请求失败')

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          if (event.type === 'thinking') {
            thinkingLabel.value = event.data.label || '正在思考…'
            state.value = 'thinking'
          } else if (event.type === 'answer_saved') {
            state.value = 'feedback_done'
          } else if (event.type === 'round_change') {
            currentRound.value = event.data.round
            roundBanner.value = `第 ${event.data.round} 轮面试开始`
            setTimeout(() => roundBanner.value = '', 3000)
          } else if (event.type === 'question') {
            currentRound.value = event.data.round
            currentQuestion.value = event.data.text
            state.value = 'idle'
          } else if (event.type === 'done') {
            if (event.data && event.data.message === '面试完成！可以查看报告了') {
              report.value = await apiGetReport(sessionId.value)
              currentQuestion.value = ''
              statusText.value = '已完成'
            }
            state.value = 'idle'
          } else if (event.type === 'error') {
            errorMsg.value = event.data.message || '出错了'
            state.value = 'error'
          }
        } catch { continue }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      state.value = 'idle'
    } else {
      errorMsg.value = '网络异常，请稍后重试'
      state.value = 'error'
    }
  }
}

async function nextQuestion() {
  startProgress()
  state.value = 'thinking'
  thinkingLabel.value = '正在准备下一题…'
  try {
    const response = await apiNextQuestion(sessionId.value)
    if (!response.ok) throw new Error('请求失败')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          if (event.type === 'thinking') {
            thinkingLabel.value = event.data.label || '正在准备…'
          } else if (event.type === 'round_change') {
            currentRound.value = event.data.round
            roundBanner.value = `第 ${event.data.round} 轮面试开始`
            setTimeout(() => roundBanner.value = '', 3000)
          } else if (event.type === 'question') {
            currentRound.value = event.data.round
            currentQuestion.value = event.data.text
            streamEval.value = ''
            state.value = 'idle'
          } else if (event.type === 'done') {
            if (event.data && event.data.message === '面试完成！可以查看报告了') {
              report.value = await apiGetReport(sessionId.value)
              currentQuestion.value = ''
              statusText.value = '已完成'
            }
            state.value = 'idle'
          } else if (event.type === 'error') {
            errorMsg.value = event.data.message || '出错了'
            state.value = 'error'
          }
        } catch { continue }
      }
    }
  } catch {
    errorMsg.value = '获取下一题失败，请重试'
    state.value = 'error'
  }
}

function confirmEnd() {
  showEndConfirm.value = true
}

async function doEnd() {
  showEndConfirm.value = false
  startProgress()
  state.value = 'loading'
  try {
    const res = await apiEndInterview(sessionId.value)
    if (res.success) {
      report.value = res
      currentQuestion.value = ''
      statusText.value = '已结束'
      state.value = 'idle'
    }
  } catch {
    errorMsg.value = '结束失败，请重试'
    state.value = 'error'
  }
}

function startProgress() {
  progress.value = 0
  if (progressTimer) clearInterval(progressTimer)
  progressTimer = setInterval(() => {
    if (progress.value < 95) {
      // 前80%快一些，后面越来越慢
      const step = progress.value < 50 ? 3 : progress.value < 80 ? 1.5 : 0.3
      progress.value = Math.min(progress.value + step, 99)
    }
  }, 200)
}

function stopProgress() {
  progress.value = 100
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

function cancelStream() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  state.value = 'idle'
}

function retryAnswer() {
  state.value = 'idle'
  answer.value = streamEval.value ? '' : answer.value
}

function backToHistory() {
  sessionId.value = ''; currentQuestion.value = ''; lastEvaluation.value = ''
  report.value = null; statusText.value = ''; currentRound.value = 1
  streamEval.value = ''; errorMsg.value = ''; editingAnswerIdx.value = -1
  qaHistory.value = []; editingQA.value = -1
  state.value = 'idle'
}

function startEditAnswer(q, idx) {
  editingAnswerIdx.value = idx
  editingAnswerText.value = q.answer || ''
}

function cancelEditAnswer() {
  editingAnswerIdx.value = -1
}

async function saveAnswer(q, idx) {
  if (!editingAnswerText.value.trim()) return
  const newText = editingAnswerText.value.trim()
  editingAnswerIdx.value = -1
  try {
    const res = await apiEditInterviewAnswer(sessionId.value, q.id, newText)
    if (res.status === 'in_progress' && res.next_question) {
      // 进行中：后续题目已删除，直接出新题
      currentQuestion.value = res.next_question
      streamEval.value = ''
      state.value = 'idle'
    } else if (res.status === 'completed' && res.report) {
      // 已完成：评价已重新生成
      // 刷新评价报告
    }
  } catch {}
}

function resetInterview() {
  sessionId.value = ''; currentQuestion.value = ''; lastEvaluation.value = ''
  report.value = null; statusText.value = ''; currentRound.value = 1
  streamEval.value = ''; errorMsg.value = ''; editingAnswerIdx.value = -1
  state.value = 'idle'
  loadHistory()
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const month = d.getMonth()+1
  const day = d.getDate()
  const h = String(d.getHours()).padStart(2,'0')
  const m = String(d.getMinutes()).padStart(2,'0')
  return `${month}月${day}日 ${h}:${m}`
}
</script>

<style scoped>
.control-bar {
  display: flex; gap: 10px; margin-top: 16px; padding-top: 12px;
  border-top: 1px solid var(--line);
}
.dialog-overlay {
  position: fixed; inset: 0; z-index: 50;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,.3);
}
.eval-box {
  width: 600px; max-width: 92vw; max-height: 80vh;
  padding: 16px 20px; overflow: hidden;
  display: flex; flex-direction: column;
}
.hist-btn { font-size: 11px; padding: 4px 8px; border-radius: var(--r-sm); }
.dialog-box {
  background: var(--card); border-radius: var(--r-lg);
  padding: 20px 24px; width: 320px; max-width: 90vw;
  box-shadow: 0 8px 30px rgba(0,0,0,.15);
}
.thinking-bar {
  display: flex; align-items: center; gap: 10px;
  margin-top: 12px; padding: 12px 14px;
  background: var(--honey-soft); border-radius: var(--r-md);
}
.thinking-pulse {
  width: 12px; height: 12px; border-radius: 50%;
  background: var(--honey); animation: pulse 1.2s ease-in-out infinite;
  flex-shrink: 0;
}
@keyframes pulse {
  0%, 100% { opacity: .4; transform: scale(.8); }
  50% { opacity: 1; transform: scale(1.1); }
}
.thinking-text { flex: 1; font-size: 13px; color: var(--ink-soft); }
.thinking-cancel {
  font-size: 12px; padding: 4px 10px; border-radius: var(--r-sm);
  color: var(--berry); border: 1px solid var(--berry); background: transparent;
}
.round-banner {
  text-align: center; padding: 10px; margin: 8px 0;
  background: var(--honey-soft); border-radius: var(--r-md);
  font-size: 15px; font-weight: 700; color: var(--honey-deep);
  animation: fadeIn .3s ease;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }
.progress-wrap {
  margin-top: 12px; padding: 12px 14px;
  background: var(--honey-soft); border-radius: var(--r-md);
}
.progress-bar {
  height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; margin-bottom: 6px;
}
.progress-fill {
  height: 100%; background: var(--honey); border-radius: 3px;
  transition: width .2s ease;
}
.progress-label {
  font-size: 12px; color: var(--ink-soft); text-align: center;
}
.interview-eval {
  border-left: 3px solid var(--sprout); padding-left: 10px;
}
</style>