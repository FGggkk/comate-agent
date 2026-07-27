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
        <div v-for="s in history.slice(0,3)" :key="s.id" class="page-card" style="margin-top:6px;padding:10px 12px;cursor:pointer;" @click="viewHistory(s.id)">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div style="font-weight:600;font-size:14px;">{{ s.target_role || '未命名' }}</div>
              <div style="font-size:12px;color:var(--sub);">{{ s.target_company }} · 第{{ s.round_number }}/3轮 · {{ s.status === 'completed' ? '已完成' : '进行中' }}</div>
            </div>
            <span style="font-size:11px;color:var(--sub);">{{ formatTime(s.created_at) }}</span>
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
            <div style="flex:1;cursor:pointer;" @click="viewHistory(s.id)">
              <div style="font-weight:600;font-size:14px;">{{ s.target_role || '未命名' }}</div>
              <div style="font-size:12px;color:var(--sub);">{{ s.target_company }} · 第{{ s.round_number }}/3轮 · {{ s.status === 'completed' ? '已完成' : '进行中' }} · {{ formatTime(s.created_at) }}</div>
            </div>
            <button @click.stop="deleteHistory(s.id)" style="font-size:14px;padding:4px 8px;color:var(--berry);opacity:.5;">🗑</button>
          </div>
        </div>
        <div v-if="history.length === 0" style="text-align:center;font-size:13px;color:var(--sub);padding:20px;">暂无记录</div>
      </div>
    </div>

    <!-- 面试中 -->
    <div v-else class="page-card">
      <!-- 返回按钮（历史记录模式） -->
      <div v-if="statusText === '历史记录'" style="margin-bottom:10px;">
        <button @click="backToHistory" style="font-size:20px;padding:4px 8px;color:var(--ink-soft);">← 返回</button>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:13px;color:var(--sub);margin-bottom:12px;">
        <span>第 {{ currentRound }} / 3 轮</span>
        <span>{{ statusText }}</span>
      </div>

      <!-- 题目 -->
      <div v-if="currentQuestion" class="interview-q">
        <div style="font-size:13px;font-weight:600;margin-bottom:6px;">面试官：</div>
        <div v-html="renderMd(currentQuestion)"></div>
      </div>

      <!-- 思考条 -->
      <div v-if="state === 'thinking' || state === 'evaluating'" class="thinking-bar">
        <div class="thinking-pulse"></div>
        <div class="thinking-text">{{ thinkingLabel }}</div>
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

      <!-- 报告 -->
      <div v-if="report" style="margin-top:16px;">
        <div class="page-label">面试报告</div>
        <div v-for="(q, idx) in report.questions" :key="idx" class="page-card" style="margin-top:8px;padding:12px;">
          <div style="font-size:14px;font-weight:600;margin-bottom:4px;" v-html="renderMd(q.question)"></div>
          <div style="font-size:12px;color:var(--sub);margin-bottom:4px;">
            回答：
            <template v-if="editingAnswerIdx === idx">
              <textarea v-model="editingAnswerText" rows="2" class="form-input" style="resize:none;font-size:12px;" />
              <button @click="saveAnswer(q, idx)" class="btn-primary" style="width:auto;padding:4px 12px;font-size:11px;margin-top:4px;">保存</button>
              <button @click="cancelEditAnswer" style="padding:4px 12px;font-size:11px;color:var(--sub);margin-left:6px;">取消</button>
            </template>
            <template v-else>
              {{ q.answer }}
              <button @click="startEditAnswer(q, idx)" style="font-size:11px;color:var(--honey);margin-left:6px;">编辑</button>
            </template>
          </div>
          <div style="font-size:12px;color:var(--ink-soft);" v-html="renderMd(q.evaluation)"></div>
        </div>
        <button @click="resetInterview" style="width:100%;margin-top:12px;padding:10px;border-radius:var(--r-sm);border:1.5px solid var(--line);font-size:14px;color:var(--ink-soft);">再来一次</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { marked } from 'marked'
import { apiStartInterview, apiAnswerQuestionStream, apiGetReport, apiListInterviews, apiNextQuestion, apiEndInterview, apiEditInterviewAnswer, apiDeleteInterview } from '../api/index'

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
const history = ref([])
const showEndConfirm = ref(false)
const showAllHistory = ref(false)
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
    report.value = await apiGetReport(id)
    sessionId.value = id
    statusText.value = '历史记录'
  } catch {}
}

onMounted(loadHistory)

async function deleteHistory(id) {
  if (!confirm('确定删除此面试记录？')) return
  try {
    const res = await apiDeleteInterview(id)
    if (res.success) history.value = history.value.filter(s => s.id !== id)
  } catch {}
}

async function startInterview() {
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
          } else if (event.type === 'eval_chunk') {
            state.value = 'evaluating'
            streamEval.value += event.data.text || ''
          } else if (event.type === 'eval_done') {
            lastEvaluation.value = streamEval.value
            state.value = 'feedback_done'
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
  q.answer = editingAnswerText.value.trim()
  editingAnswerIdx.value = -1
  // 保存到后端
  try {
    await apiEditInterviewAnswer(sessionId.value, q.id, q.answer)
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
.interview-eval {
  border-left: 3px solid var(--sprout); padding-left: 10px;
}
</style>