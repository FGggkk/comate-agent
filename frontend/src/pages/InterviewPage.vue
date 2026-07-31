<template>
  <div class="scroll">
    <!-- 返回栏（嵌入模式） -->
    <div v-if="embedded" class="back-bar" style="margin-left:-16px;padding-left:4px;padding-right:16px;">
      <button @click="embeddedBack" class="back-btn">
        <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="13,4 7,10 13,16"/></svg>
        {{ sessionId ? '返回' : (props.origin === 'chat' ? '返回聊天' : '返回工作台') }}
      </button>
    </div>
    <div class="page-title">面试训练</div>

    <!-- 开始页 -->
    <div v-if="!sessionId" class="page-card">
      <!-- 快速开始 -->
      <div style="margin-bottom:16px;padding:12px;background:var(--honey-soft);border-radius:var(--r-md);">
        <div style="font-weight:600;font-size:15px;margin-bottom:8px;">🚀 快速面试</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <input v-model="targetRole" placeholder="目标岗位 *" class="form-input" style="flex:2;min-width:140px;" />
          <select v-model="difficulty" class="form-input" style="flex:1;min-width:80px;">
            <option value="easy">😊 简单</option>
            <option value="medium">🤔 中等</option>
            <option value="hard">😈 困难</option>
          </select>
        </div>
        <button @click="startInterview" :disabled="state !== 'idle'" class="btn-primary" style="margin-top:10px;width:100%;">
          {{ state === 'loading' ? '准备中...' : '🚀 开始模拟面试' }}
        </button>
      </div>
      <div v-if="errorMsg" style="margin-top:8px;font-size:13px;color:var(--berry);text-align:center;">⚠ {{ errorMsg }}</div>

      <!-- 更多设置 -->
      <details style="margin-bottom:16px;">
        <summary style="font-size:13px;color:var(--honey);cursor:pointer;padding:4px 0;">📋 更多设置</summary>
        <div style="margin-top:8px;">
          <div style="margin-bottom:10px;">
            <label class="form-label">面试类型</label>
            <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px;">
              <button v-for="t in interviewTypes" :key="t.value"
                @click="interviewType = t.value"
                :style="{flex:1,minWidth:'70px',padding:'6px 10px',fontSize:'12px',borderRadius:'var(--r-sm)',border:'1.5px solid',background: interviewType === t.value ? 'var(--honey-soft)' : 'transparent',borderColor: interviewType === t.value ? 'var(--honey)' : 'var(--line)',color: interviewType === t.value ? 'var(--honey-deep)' : 'var(--sub)'}">
                {{ t.label }}
              </button>
            </div>
          </div>
          <div style="margin-bottom:10px;">
            <label class="form-label">简历内容（选填）</label>
            <textarea v-model="resume" rows="3" placeholder="粘贴你的简历内容..." class="form-input" style="resize:none;"></textarea>
          </div>
          <div>
            <label class="form-label">目标公司（选填）</label>
            <input v-model="targetCompany" placeholder="如：字节跳动" class="form-input" />
          </div>
        </div>
      </details>

      <!-- 历史记录 -->
      <div v-if="!showAllHistory && history.length > 0" style="margin-top:20px;">
        <div class="page-label">历史面试</div>
        <div v-for="s in history.slice(0,3)" :key="s.id" class="page-card" style="margin-top:6px;padding:10px 12px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div style="flex:1;cursor:pointer;" @click="renamingId !== s.id && (s.status === 'completed' ? showEval(s) : viewHistory(s.id))">
              <div style="font-weight:600;font-size:14px;">
                <template v-if="renamingId === s.id">
                  <span style="display:flex;align-items:center;gap:4px;">
                    <input v-model="renameText" @keydown.enter="confirmRename(s)" @click.stop class="form-input" style="font-size:14px;padding:2px 6px;flex:1;" autofocus />
                    <button @click.stop="confirmRename(s)" style="font-size:14px;padding:2px 6px;color:var(--sprout);background:none;border:none;cursor:pointer;">✓</button>
                  </span>
                </template>
                <template v-else>{{ s.title || s.target_role || '未命名' }}</template>
              </div>
              <div style="font-size:12px;color:var(--sub);">
                {{ s.target_company }} · 第{{ s.round_number }}/{{ s.max_rounds || 3 }}轮
                <span :style="{color: s.status === 'completed' ? 'var(--sprout)' : 'var(--honey-deep)'}">{{ s.status === 'completed' ? '✅ 已完成' : '⏳ 进行中' }}</span>
              </div>
            </div>
            <div style="display:flex;gap:4px;align-items:center;position:relative;">
              <button @click.stop="toggleMenu(s.id)" style="font-size:16px;padding:2px 6px;color:var(--sub);border:1px solid var(--line);border-radius:var(--r-sm);background:transparent;cursor:pointer;">⋮</button>
              <div v-if="openMenuId === s.id" style="position:absolute;top:100%;right:0;z-index:20;min-width:120px;background:var(--card);border:1px solid var(--line);border-radius:var(--r-sm);box-shadow:0 4px 12px rgba(0,0,0,.1);padding:4px 0;">
                <button @click.stop="startRename(s);openMenuId=''" style="display:block;width:100%;text-align:left;padding:6px 14px;font-size:13px;color:var(--ink);background:none;border:none;cursor:pointer;">✎ 重命名</button>
                <button v-if="s.status === 'completed'" @click.stop="showEval(s);openMenuId=''" style="display:block;width:100%;text-align:left;padding:6px 14px;font-size:13px;color:var(--sprout);background:none;border:none;cursor:pointer;">☰ 查看报告</button>
                <button v-else @click.stop="viewHistory(s.id);openMenuId=''" style="display:block;width:100%;text-align:left;padding:6px 14px;font-size:13px;color:var(--honey-deep);background:none;border:none;cursor:pointer;">▸ 继续</button>
                <button @click.stop="deleteHistory(s.id);openMenuId=''" style="display:block;width:100%;text-align:left;padding:6px 14px;font-size:13px;color:var(--berry);background:none;border:none;cursor:pointer;">✕ 删除</button>
              </div>
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
                  <span style="display:flex;align-items:center;gap:4px;">
                    <input v-model="renameText" @keydown.enter="confirmRename(s)" @click.stop class="form-input" style="font-size:14px;padding:2px 6px;flex:1;" autofocus />
                    <button @click.stop="confirmRename(s)" style="font-size:14px;padding:2px 6px;color:var(--sprout);background:none;border:none;cursor:pointer;">✓</button>
                  </span>
                </template>
                <template v-else>{{ s.title || s.target_role || '未命名' }}</template>
              </div>
              <div style="font-size:12px;color:var(--sub);">
                {{ s.target_company }} · 第{{ s.round_number }}/{{ s.max_rounds || 3 }}轮
                <span :style="{color: s.status === 'completed' ? 'var(--sprout)' : 'var(--honey-deep)'}">{{ s.status === 'completed' ? '✅ 已完成' : '⏳ 进行中' }}</span>
              </div>
            </div>
            <div style="display:flex;gap:4px;align-items:center;position:relative;">
              <button @click.stop="toggleMenu(s.id)" style="font-size:16px;padding:2px 6px;color:var(--sub);border:1px solid var(--line);border-radius:var(--r-sm);background:transparent;cursor:pointer;">⋮</button>
              <div v-if="openMenuId === s.id" style="position:absolute;top:100%;right:0;z-index:20;min-width:120px;background:var(--card);border:1px solid var(--line);border-radius:var(--r-sm);box-shadow:0 4px 12px rgba(0,0,0,.1);padding:4px 0;">
                <button @click.stop="startRename(s);openMenuId=''" style="display:block;width:100%;text-align:left;padding:6px 14px;font-size:13px;color:var(--ink);background:none;border:none;cursor:pointer;">✎ 重命名</button>
                <button v-if="s.status === 'completed'" @click.stop="showEval(s);openMenuId=''" style="display:block;width:100%;text-align:left;padding:6px 14px;font-size:13px;color:var(--sprout);background:none;border:none;cursor:pointer;">☰ 查看报告</button>
                <button v-else @click.stop="viewHistory(s.id);openMenuId=''" style="display:block;width:100%;text-align:left;padding:6px 14px;font-size:13px;color:var(--honey-deep);background:none;border:none;cursor:pointer;">▸ 继续</button>
                <button @click.stop="deleteHistory(s.id);openMenuId=''" style="display:block;width:100%;text-align:left;padding:6px 14px;font-size:13px;color:var(--berry);background:none;border:none;cursor:pointer;">✕ 删除</button>
              </div>
            </div>
          </div>
        </div>
        <div v-if="history.length === 0" style="text-align:center;font-size:13px;color:var(--sub);padding:20px;">暂无记录</div>
      </div>
    </div>

    <!-- 面试中 -->
    <div v-else class="page-card">
      <!-- 顶部：返回 + 步骤指示器 + 结束 -->
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
        <button v-if="!embedded" @click="backToHistory" class="back-btn"><svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="13,4 7,10 13,16"/></svg> 返回</button>
        <button @click="confirmEnd" style="font-size:12px;padding:4px 10px;border-radius:var(--r-sm);border:1px solid var(--berry);color:var(--berry);">结束面试</button>
      </div>
      <div style="margin-bottom:12px;">
        <div style="display:flex;align-items:center;gap:4px;justify-content:center;">
          <template v-for="r in maxRounds" :key="r">
            <div :style="{width:'28px',height:'28px',borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',fontSize:'12px',fontWeight:600,
              background: r < currentRound ? 'var(--sprout)' : r === currentRound ? 'var(--honey)' : 'var(--line)',
              color: r <= currentRound ? '#fff' : 'var(--sub)'}">{{ r }}</div>
            <div v-if="r < maxRounds" :style="{flex:1,height:'3px',background: r < currentRound ? 'var(--sprout)' : 'var(--line)',borderRadius:'2px',maxWidth:'60px'}"></div>
          </template>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--sub);margin-top:4px;padding:0 10px;">
          <span>第 {{ currentRound }} / {{ maxRounds }} 轮</span>
          <span>{{ statusText }}</span>
        </div>
      </div>

      <!-- 历史问答（对话气泡样式） -->
      <div v-if="qaHistory.length > 0" style="margin-bottom:12px;max-height:40vh;overflow-y:auto;">
        <div v-for="(qa, idx) in qaHistory" :key="idx" style="margin-bottom:10px;">
          <!-- 面试官气泡（题目） -->
          <div style="display:flex;margin-bottom:4px;">
            <div style="background:var(--honey-soft);border-radius:12px 12px 12px 4px;padding:8px 12px;max-width:85%;font-size:13px;">
              <div style="font-size:11px;font-weight:600;color:var(--honey-deep);margin-bottom:2px;">面试官 Q{{ idx+1 }}</div>
              <div v-html="renderMd(qa.question)"></div>
            </div>
          </div>
          <!-- 用户回答气泡 -->
          <div style="display:flex;flex-direction:row-reverse;">
            <div style="background:var(--sprout-soft);border-radius:12px 12px 4px 12px;padding:8px 12px;max-width:85%;font-size:13px;">
              <div style="font-size:11px;font-weight:600;color:var(--sprout);margin-bottom:2px;">你的回答</div>
              <template v-if="editingQA === idx">
                <textarea v-model="editingQAText" rows="2" class="form-input" style="resize:none;font-size:12px;" />
                <div style="display:flex;gap:4px;margin-top:4px;">
                  <button @click="saveQA(qa, idx)" style="font-size:11px;padding:2px 10px;background:var(--sprout);color:#fff;border:none;border-radius:4px;">保存</button>
                  <button @click="cancelEditQA" style="font-size:11px;padding:2px 10px;color:var(--sub);border:1px solid var(--line);border-radius:4px;">取消</button>
                </div>
              </template>
              <template v-else>
                <div style="color:var(--ink);">{{ qa.answer }}</div>
                <button @click="startEditQA(qa, idx)" style="font-size:10px;color:var(--honey);margin-top:2px;padding:0;">编辑</button>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- 当前题目 -->
      <div v-if="currentQuestion" class="interview-q" style="margin-bottom:10px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
          <div style="flex:1;">
            <div style="font-size:13px;font-weight:600;margin-bottom:6px;">面试官：</div>
            <div v-html="renderMd(currentQuestion)"></div>
          </div>
          <button v-if="state === 'idle'" @click="getHint" style="font-size:11px;padding:3px 8px;border-radius:var(--r-sm);border:1px solid var(--honey);color:var(--honey);background:transparent;white-space:nowrap;margin-left:8px;">💡 提示</button>
          <button v-if="state === 'idle'" @click="rerollQuestion" style="font-size:11px;padding:3px 8px;border-radius:var(--r-sm);border:1px solid var(--sub);color:var(--sub);background:transparent;white-space:nowrap;margin-left:4px;">🔄</button>
        </div>
        <div v-if="hintText" style="margin-top:8px;padding:8px 10px;background:var(--honey-soft);border-radius:var(--r-sm);font-size:12px;color:var(--ink-soft);border-left:3px solid var(--honey);">
          <div style="font-weight:600;margin-bottom:2px;">💡 思路引导</div>
          <div v-html="renderMd(hintText)"></div>
        </div>
      </div>

      <!-- 轮次切换横幅 -->
      <div v-if="roundBanner" class="round-banner">{{ roundBanner }}</div>

      <!-- 阶段进度条 -->
      <div v-if="progressVisible" class="progress-wrap">
        <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--sub);margin-bottom:4px;">
          <span>{{ progressLabel || progressPhases[progressPhaseIndex] || '' }}</span>
          <span>{{ Math.round(progressPercent) }}%</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{width: progressPercent + '%'}"></div>
        </div>
        <div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;">
          <span v-for="(ph, i) in progressPhases" :key="i" :style="{fontSize:'11px',color: i <= progressPhaseIndex ? 'var(--honey-deep)' : 'var(--sub)',opacity: i <= progressPhaseIndex ? 1 : .5}">
            {{ i > 0 ? ' · ' : '' }}{{ i <= progressPhaseIndex ? '✓' : '○' }} {{ ph }}
          </span>
        </div>
        <div v-if="progressDoneText" style="margin-top:6px;font-size:12px;color:var(--sprout);font-weight:600;">{{ progressDoneText }}</div>
        <button v-if="state === 'evaluating'" @click="cancelStream" class="thinking-cancel" style="margin-top:6px;">取消</button>
      </div>

      <!-- 评估结果（流式） -->
      <div v-if="streamEval" class="interview-eval" style="margin-top:12px;">
        <div style="font-weight:600;font-size:12px;margin-bottom:4px;">评估</div>
        <div v-html="renderMd(streamEval)"></div>
      </div>

      <!-- 输入框（非 thinking/evaluating 且未完成时显示） -->
      <div v-if="(state === 'idle' || state === 'done') && statusText !== '已完成' && statusText !== '已结束'" style="margin-top:12px;">
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

    </div>

    <!-- 评价报告覆盖层（放在最外层，不受 v-if/v-else 影响） -->
    <div v-if="evalReport" class="dialog-overlay" @click="closeEval">
      <div :class="['dialog-box', 'eval-box', isFullscreen ? 'eval-fullscreen' : '']" @click.stop>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <div class="page-label" style="margin:0;">面试评价报告</div>
          <div style="display:flex;gap:6px;">
            <button @click="toggleFullscreen" style="font-size:16px;padding:4px 6px;color:var(--sub);background:none;border:none;cursor:pointer;" :title="isFullscreen ? '退出全屏' : '全屏'">⛶</button>
            <button @click="exportReport" style="font-size:12px;padding:4px 10px;border-radius:var(--r-sm);border:1px solid var(--honey);color:var(--honey);background:transparent;">📄 导出</button>
            <button @click="closeEval" style="font-size:18px;padding:4px;color:var(--sub);">✕</button>
          </div>
        </div>

        <!-- 总分 + 雷达图 -->
        <div v-if="evalReport.overall_score !== undefined" style="display:flex;gap:16px;align-items:center;padding:8px 0 16px;border-bottom:1px solid var(--line);margin-bottom:12px;">
          <div style="text-align:center;flex-shrink:0;">
            <div :style="{fontSize:'32px',fontWeight:700,color: evalReport.overall_score >= 70 ? 'var(--sprout)' : evalReport.overall_score >= 40 ? 'var(--honey-deep)' : 'var(--berry)'}">{{ evalReport.overall_score }}</div>
            <div style="font-size:11px;color:var(--sub);">/100</div>
            <div style="font-size:11px;color:var(--sub);margin-top:2px;">共 {{ evalReport.questions ? evalReport.questions.length : 0 }} 题</div>
          </div>
          <!-- CSS雷达图 -->
          <div v-if="radarData.length > 0" style="flex:1;display:flex;flex-wrap:wrap;gap:4px 12px;justify-content:center;">
            <div v-for="d in radarData" :key="d.key" style="display:flex;align-items:center;gap:4px;font-size:12px;">
              <div :style="{width:'8px',height:'8px',borderRadius:'50%',background:d.color}"></div>
              <span style="color:var(--ink-soft);min-width:44px;">{{ d.label }}</span>
              <div style="width:60px;height:6px;background:var(--line);border-radius:3px;overflow:hidden;">
                <div :style="{width:(d.value/10*100)+'%',height:'100%',background:d.color,borderRadius:'3px',transition:'width .5s ease'}"></div>
              </div>
              <span :style="{fontWeight:600,color:d.value >= 7 ? 'var(--sprout)' : d.value >= 4 ? 'var(--honey-deep)' : 'var(--berry)'}">{{ d.value }}</span>
            </div>
          </div>
          <div v-if="evalReport.report_generated_at" style="font-size:11px;color:var(--sub);margin-top:4px;">更新于 {{ formatTime(evalReport.report_generated_at) }}</div>
        </div>
        <div style="max-height:60vh;overflow-y:auto;">
          <div v-for="(q, idx) in evalReport.questions || []" :key="idx" class="page-card" style="margin-top:8px;padding:10px;">
            <div style="font-size:13px;font-weight:600;margin-bottom:4px;" v-html="renderMd(q.question)"></div>
            <div style="font-size:11px;color:var(--sub);margin-bottom:4px;">回答：{{ q.answer }}</div>
            <div v-if="q.max_score && q.max_score > 0" style="font-size:12px;margin-bottom:2px;">
              <span :style="{color: q.score/q.max_score >= 0.7 ? 'var(--sprout)' : q.score/q.max_score >= 0.4 ? 'var(--honey-deep)' : 'var(--berry)'}">
                {{ q.score ?? '-' }}/{{ q.max_score }}分
              </span>
            </div>
            <div v-else style="font-size:12px;color:var(--sub);margin-bottom:2px;">-/{{ q.max_score || '?' }}分（待评估）</div>
            <div style="font-size:11px;color:var(--ink-soft);" v-html="renderMd(q.evaluation)"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onActivated } from 'vue'
import { marked } from 'marked'
import { apiStartInterview, apiAnswerQuestionStream, apiGetReport, apiListInterviews, apiNextQuestion, apiEndInterview, apiEditInterviewAnswer, apiDeleteInterview, apiRenameInterview, apiRerollQuestion } from '../api/index'

const props = defineProps({
  embedded: { type: Boolean, default: false },
  origin: { type: String, default: 'home' },
})
const emit = defineEmits(['back'])

function renderMd(text) {
  if (!text) return ''
  return marked.parse(text)
}

const sessionId = ref('')
const resume = ref('')
const targetRole = ref('')
const targetCompany = ref('')
const interviewType = ref('comprehensive')
const difficulty = ref('medium')
const interviewTypes = [
  { value: 'tech', label: '💻 技术面' },
  { value: 'behavior', label: '🤝 行为面' },
  { value: 'project', label: '📁 项目深挖' },
  { value: 'stress', label: '🔥 压力面' },
  { value: 'comprehensive', label: '🎯 综合面' },
]
const currentRound = ref(1)
const currentQuestion = ref('')
const hintText = ref('')
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
const roundBanner = ref('')
const evalReport = ref(null)
const qaHistory = ref([])
const maxRounds = computed(() => ({ easy: 1, medium: 2, hard: 3 }[difficulty.value] || 2))

const dimLabels = {
  tech_depth: '技术深度', communication: '沟通表达', logic: '逻辑思维',
  project_exp: '项目经验', adaptability: '应变能力',
}
const dimColors = {
  tech_depth: '#5FB0E8', communication: '#FFB088', logic: '#9B6FD8',
  project_exp: '#5FBE63', adaptability: '#FF9F45',
}
const radarData = computed(() => {
  const ds = evalReport.value?.dimension_scores
  if (!ds) return []
  return Object.entries(dimLabels).map(([key, label]) => ({
    key, label, value: ds[key] || 0,
    color: dimColors[key] || 'var(--honey)',
  }))
})
const editingQA = ref(-1)
const editingQAText = ref('')
const renamingId = ref('')
const renameText = ref('')
const openMenuId = ref('')
function toggleMenu(id) {
  openMenuId.value = openMenuId.value === id ? '' : id
  if (openMenuId.value) {
    setTimeout(() => document.addEventListener('click', () => { openMenuId.value = '' }, { once: true }), 0)
  }
}
const editingAnswerIdx = ref(-1)
const editingAnswerText = ref('')
const progressVisible = ref(false)
const progressPercent = ref(0)
const progressPhaseIndex = ref(0)
const progressPhases = ref([])
const progressLabel = ref('')
const progressDoneText = ref('')
let progressTimer = null

function showProgress(phases) {
  progressPhases.value = phases
  progressPhaseIndex.value = 0
  progressPercent.value = 5
  progressVisible.value = true
  progressLabel.value = phases[0] || ''
  progressDoneText.value = ''
  if (progressTimer) clearInterval(progressTimer)
  progressTimer = setInterval(() => {
    const phaseStart = (progressPhaseIndex.value / Math.max(phases.length, 1)) * 90
    const phaseEnd = ((progressPhaseIndex.value + 1) / Math.max(phases.length, 1)) * 90
    const range = phaseEnd - phaseStart
    if (progressPercent.value < phaseEnd - 2) {
      progressPercent.value = Math.min(progressPercent.value + 1, phaseEnd - 2)
    }
  }, 400)
}

function advancePhase() {
  if (progressPhaseIndex.value < progressPhases.value.length - 1) {
    progressPhaseIndex.value++
    progressLabel.value = progressPhases.value[progressPhaseIndex.value] || ''
    const newPct = ((progressPhaseIndex.value + 1) / Math.max(progressPhases.value.length, 1)) * 90
    progressPercent.value = Math.max(progressPercent.value, newPct - 5)
  }
}

function hideProgress() {
  progressPercent.value = 100
  progressVisible.value = false
  progressPhaseIndex.value = 0
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
}

function markProgressDone(doneText) {
  progressPercent.value = 100
  progressPhaseIndex.value = progressPhases.value.length - 1
  progressLabel.value = progressDoneText.value = doneText || '完成'
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
}

function completeProgress() {
  progressPercent.value = 100
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
  return new Promise(r => setTimeout(r, 500))
}

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

onActivated(loadHistory)

async function showEval(session) {
  try {
    const res = await apiGetReport(session.id)
    if (res && res.questions) {
      evalReport.value = res
    }
  } catch (e) {
    console.error('showEval error:', e)
  }
}

const isFullscreen = ref(false)
function toggleFullscreen() { isFullscreen.value = !isFullscreen.value }
function closeEval() {
  evalReport.value = null
  isFullscreen.value = false
}

function exportReport() {
  if (!evalReport.value) return
  const r = evalReport.value
  let text = `面试评价报告\n${'='.repeat(30)}\n`
  text += `总分：${r.overall_score || '-'}/100\n`
  if (r.dimension_scores) {
    text += `\n维度评分：\n`
    for (const [key, val] of Object.entries(r.dimension_scores)) {
      text += `  ${dimLabels[key] || key}: ${val}/10\n`
    }
  }
  text += `\n共 ${r.questions?.length || 0} 题\n\n`
  ;(r.questions || []).forEach((q, i) => {
    text += `Q${i+1}: ${q.question}\n回答：${q.answer || '（未回答）'}\n评分：${q.score}/${q.max_score}\n评语：${q.evaluation || '无'}\n\n`
  })
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = `面试报告_${new Date().toISOString().slice(0,10)}.txt`
  a.click()
  URL.revokeObjectURL(url)
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
  if (!targetRole.value.trim()) { errorMsg.value = '请填写目标岗位'; return }
  showProgress(['准备题目', '生成中', '完成'])
  state.value = 'loading'
  errorMsg.value = ''
  hintText.value = ''
  try {
    const res = await apiStartInterview({
      resume_text: resume.value, target_role: targetRole.value, target_company: targetCompany.value,
      interview_type: interviewType.value, difficulty: difficulty.value,
    })
    markProgressDone('面试已开始')
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
  showProgress(['提交回答', '已保存', '等待下一题'])
  state.value = 'thinking'

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
            markProgressDone('✅ 回答已保存')
            // 把刚答的题加入历史
            qaHistory.value.push({question: currentQuestion.value, answer: text, id: ''})
            currentQuestion.value = ''
            await new Promise(r => setTimeout(r, 400))
            state.value = 'feedback_done'
          } else if (event.type === 'round_change') {
            currentRound.value = event.data.round
            roundBanner.value = `第 ${event.data.round} 轮面试开始`
            setTimeout(() => roundBanner.value = '', 3000)
          } else if (event.type === 'question') {
            currentRound.value = event.data.round
            hintText.value = ''
            currentQuestion.value = event.data.text
            state.value = 'idle'
          } else if (event.type === 'done') {
            if (event.data && event.data.message === '面试完成！可以查看报告了') {
              report.value = await apiGetReport(sessionId.value)
                await new Promise(r => setTimeout(r, 400))
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
    hideProgress()
    if (err.name === 'AbortError') {
      state.value = 'idle'
    } else {
      errorMsg.value = '网络异常，请稍后重试'
      state.value = 'error'
    }
  }
}

async function nextQuestion() {
  showProgress(['准备题目', '生成中', '完成'])
  state.value = 'thinking'
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
            advancePhase()
          } else if (event.type === 'round_change') {
            currentRound.value = event.data.round
            roundBanner.value = `第 ${event.data.round} 轮面试开始`
            setTimeout(() => roundBanner.value = '', 3000)
          } else if (event.type === 'question') {
            markProgressDone('题目已就绪')
            hintText.value = ''
            currentRound.value = event.data.round
            currentQuestion.value = event.data.text
            streamEval.value = ''
            await new Promise(r => setTimeout(r, 300))
            state.value = 'idle'
          } else if (event.type === 'done') {
            if (event.data && event.data.message === '面试完成！可以查看报告了') {
              markProgressDone('面试完成')
              await new Promise(r => setTimeout(r, 500))
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
  showProgress(['生成评分文档', '评估中', '完成'])
  state.value = 'loading'
  try {
    const res = await apiEndInterview(sessionId.value)
    if (res.success) {
      markProgressDone('评分完成')
      await new Promise(r => setTimeout(r, 500))
      evalReport.value = res
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

async function getHint() {
  if (!sessionId.value || !currentQuestion.value) return
  showProgress(['生成思路引导', '完成'])
  try {
    const res = await fetch(`/api/interview/${sessionId.value}/hint`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('comate_token')}` },
      body: JSON.stringify({ question: currentQuestion.value }),
    })
    if (!res.ok) { hideProgress(); return }
    const raw = await res.json()
    markProgressDone('提示已生成')
    await new Promise(r => setTimeout(r, 300))
    hintText.value = (raw.data?.hint || raw.hint || '')
  } catch { hideProgress() }
}

async function rerollQuestion() {
  if (!sessionId.value || state.value !== 'idle') return
  showProgress(['重新出题', '生成中', '完成'])
  state.value = 'loading'
  try {
    const data = await apiRerollQuestion(sessionId.value)
    if (data.question) {
      markProgressDone('出题完成')
      await new Promise(r => setTimeout(r, 300))
      currentQuestion.value = data.question
      hintText.value = ''
      streamEval.value = ''
    }
  } catch { hideProgress(); errorMsg.value = '重试失败'; state.value = 'error' }
  state.value = 'idle'
}

function backToHistory() {
  sessionId.value = ''; currentQuestion.value = ''; lastEvaluation.value = ''
  report.value = null; statusText.value = ''; currentRound.value = 1
  streamEval.value = ''; errorMsg.value = ''; editingAnswerIdx.value = -1
  qaHistory.value = []; editingQA.value = -1
  state.value = 'idle'
}

function embeddedBack() {
  if (sessionId.value) {
    backToHistory()
  } else {
    emit('back')
  }
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
  transition: all .2s ease;
}
.eval-fullscreen {
  width: 95vw !important;
  max-width: 95vw !important;
  height: 90vh !important;
  max-height: 90vh !important;
}
.hist-btn { font-size: 11px; padding: 4px 8px; border-radius: var(--r-sm); }
.dialog-box {
  background: var(--card); border-radius: var(--r-lg);
  padding: 20px 24px; width: 320px; max-width: 90vw;
  box-shadow: 0 8px 30px rgba(0,0,0,.15);
}
.progress-wrap {
  margin-top: 12px; padding: 12px 14px;
  background: var(--honey-soft); border-radius: var(--r-md);
}
.progress-bar {
  height: 8px; background: var(--line); border-radius: 4px; overflow: hidden;
}
.progress-fill {
  height: 100%; background: linear-gradient(90deg, var(--honey), var(--honey-deep));
  border-radius: 4px; transition: width .3s ease;
}
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
.interview-eval {
  border-left: 3px solid var(--sprout); padding-left: 10px;
}
.back-bar { display: flex; align-items: center; padding: 4px 4px; }
.back-btn {
  display: flex; align-items: center; gap: 4px;
  font-size: 14px; color: var(--ink-soft); padding: 6px 8px;
  background: none; border: none; cursor: pointer;
}
.back-btn:hover { color: var(--ink); }
/* 长文本排版修复 */
.interview-q div, .eval-box div, [class*="bubble"] div {
  word-break: break-word; overflow-wrap: break-word; hyphens: auto;
}
.interview-q p, .eval-box p { margin: 4px 0; }
.interview-q code, .eval-box code {
  font-size: 12px; background: var(--line); padding: 1px 4px; border-radius: 3px; word-break: break-all;
}
.interview-q pre, .eval-box pre {
  font-size: 12px; background: var(--line); padding: 8px; border-radius: var(--r-sm);
  overflow-x: auto; white-space: pre-wrap; word-break: break-word;
}
</style>