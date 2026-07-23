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
      <button @click="startInterview" :disabled="loading" class="btn-primary">
        {{ loading ? '准备中...' : '开始模拟面试' }}
      </button>
    </div>

    <!-- 面试中 -->
    <div v-else class="page-card">
      <div style="display:flex;justify-content:space-between;font-size:13px;color:var(--sub);margin-bottom:12px;">
        <span>第 {{ currentRound }} / 3 轮</span>
        <span>{{ statusText }}</span>
      </div>

      <div v-if="currentQuestion" class="interview-q">
        <div style="font-size:13px;font-weight:600;margin-bottom:6px;">面试官：</div>
        <div>{{ currentQuestion }}</div>
      </div>

      <div v-if="currentQuestion && !loading" style="margin-top:12px;">
        <textarea v-model="answer" rows="3" placeholder="输入你的回答..." class="form-input" style="resize:none;"></textarea>
        <button @click="submitAnswer" class="btn-primary" style="margin-top:8px;">提交回答</button>
      </div>

      <div v-if="lastEvaluation" class="interview-eval" style="margin-top:12px;">
        <div style="font-weight:600;font-size:12px;margin-bottom:4px;">评估</div>
        <div>{{ lastEvaluation }}</div>
      </div>

      <!-- 报告 -->
      <div v-if="report" style="margin-top:16px;">
        <div class="page-label">面试报告</div>
        <div v-for="q in report.questions" :key="q.id" class="page-card" style="margin-top:8px;padding:12px;">
          <div style="font-size:14px;font-weight:600;margin-bottom:4px;">{{ q.question }}</div>
          <div style="font-size:12px;color:var(--sub);margin-bottom:4px;">回答：{{ q.answer }}</div>
          <div style="font-size:12px;color:var(--ink-soft);">评估：{{ q.evaluation }}</div>
        </div>
        <button @click="resetInterview" style="width:100%;margin-top:12px;padding:10px;border-radius:var(--r-sm);border:1.5px solid var(--line);font-size:14px;color:var(--ink-soft);">再来一次</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { apiStartInterview, apiAnswerQuestion, apiGetReport } from '../api/index'

const sessionId = ref('')
const resume = ref('')
const targetRole = ref('')
const targetCompany = ref('')
const currentRound = ref(1)
const currentQuestion = ref('')
const answer = ref('')
const lastEvaluation = ref('')
const loading = ref(false)
const statusText = ref('')
const report = ref(null)

async function startInterview() {
  loading.value = true
  try {
    const res = await apiStartInterview({ resume_text: resume.value, target_role: targetRole.value, target_company: targetCompany.value })
    sessionId.value = res.session_id; currentRound.value = res.round; currentQuestion.value = res.question; statusText.value = '面试进行中'
  } finally { loading.value = false }
}

async function submitAnswer() {
  if (!answer.value.trim()) return
  loading.value = true
  try {
    const res = await apiAnswerQuestion(sessionId.value, answer.value)
    lastEvaluation.value = res.evaluation || ''
    answer.value = ''
    if (res.done) {
      report.value = await apiGetReport(sessionId.value)
      currentQuestion.value = ''; statusText.value = '已完成'
    } else {
      currentRound.value = res.round; currentQuestion.value = res.question || ''
    }
  } finally { loading.value = false }
}

function resetInterview() {
  sessionId.value = ''; currentQuestion.value = ''; lastEvaluation.value = ''; report.value = null; statusText.value = ''; currentRound.value = 1
}
</script>
