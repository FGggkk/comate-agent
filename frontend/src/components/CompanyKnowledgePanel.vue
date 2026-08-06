<template>
  <section class="knowledge-panel" aria-label="公司制度">
    <div class="knowledge-head">
      <div class="knowledge-title">
        <span class="knowledge-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M5 4.5h10.5A3.5 3.5 0 0 1 19 8v11H8.5A3.5 3.5 0 0 1 5 15.5v-11Z"/><path d="M8 8h7M8 11h7M8 14h4"/></svg>
        </span>
        <strong>公司制度</strong>
      </div>
      <button class="knowledge-close" title="收起公司制度" aria-label="收起公司制度" @click="$emit('close')">×</button>
    </div>

    <div v-if="!answer && !isSubmitting" class="knowledge-suggestions">
      <button v-for="item in suggestions" :key="item" @click="useSuggestion(item)">{{ item }}</button>
    </div>

    <div class="knowledge-editor">
      <textarea
        ref="questionInput"
        :value="question"
        rows="2"
        :disabled="isSubmitting || voiceState !== 'idle'"
        placeholder="问问公司制度…"
        @input="$emit('update:question', $event.target.value)"
        @keydown.enter.exact.prevent="submit"
      />
      <div class="knowledge-editor-actions">
        <span v-if="voiceHint" class="voice-hint" role="status">{{ voiceHint }}</span>
        <span v-else-if="isSubmitting" class="query-hint" role="status">正在检索制度…</span>
        <span v-else></span>
        <div class="knowledge-buttons">
          <button
            :class="['knowledge-voice', `is-${voiceState}`]"
            :disabled="isSubmitting"
            :title="voiceButtonLabel"
            :aria-label="voiceButtonLabel"
            @click="$emit('voice')"
          >
            <svg v-if="voiceState === 'recording' || voiceState === 'responding'" viewBox="0 0 24 24"><rect x="7" y="7" width="10" height="10" rx="1.5"/></svg>
            <svg v-else viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"/></svg>
          </button>
          <button class="knowledge-send" :disabled="isSubmitting || !question.trim()" title="发送制度问题" aria-label="发送制度问题" @click="submit">
            <svg viewBox="0 0 24 24"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z"/></svg>
          </button>
        </div>
      </div>
    </div>

    <div v-if="error" class="knowledge-error" role="status">{{ error }}</div>

    <div v-if="answer || isSubmitting || sources.length" class="knowledge-result">
      <div v-if="answer" class="knowledge-answer" v-html="renderMd(answer)"></div>
      <div v-else-if="isSubmitting" class="knowledge-wait"><i></i><i></i><i></i></div>

      <div v-if="sources.length" class="knowledge-sources">
        <div class="sources-title">参考制度</div>
        <div class="source-list">
          <article v-for="(source, index) in sources" :key="source.chunk_id || index" class="source-item">
            <button class="source-summary" @click="toggleSource(index)">
              <span class="source-copy">
                <b>{{ source.title }}</b>
                <span>{{ source.section_path || '未标注章节' }} · {{ source.version }} · {{ source.effective_at || '未标注生效日期' }}</span>
              </span>
              <span class="source-toggle">{{ expandedSource === index ? '收起' : '片段' }}</span>
            </button>
            <p v-if="expandedSource === index" class="source-excerpt">{{ source.excerpt }}</p>
          </article>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  question: { type: String, default: '' },
  answer: { type: String, default: '' },
  sources: { type: Array, default: () => [] },
  isSubmitting: Boolean,
  voiceState: { type: String, default: 'idle' },
  voiceHint: { type: String, default: '' },
  error: { type: String, default: '' },
})
const emit = defineEmits(['update:question', 'submit', 'voice', 'close'])
const questionInput = ref(null)
const expandedSource = ref(-1)
const suggestions = ['年假如何计算？', '报销需要哪些材料？', '出差申请怎么处理？']

const voiceButtonLabel = computed(() => {
  if (props.voiceState === 'recording') return '结束录音'
  if (props.voiceState === 'responding') return '停止语音识别'
  if (props.voiceState === 'connecting') return '正在连接语音服务'
  return '语音输入制度问题'
})

function renderMd(text) {
  return text ? marked.parse(text) : ''
}

function submit() {
  if (!props.question.trim() || props.isSubmitting) return
  emit('submit')
}

function useSuggestion(text) {
  emit('update:question', text)
  nextTick(() => questionInput.value?.focus())
}

function toggleSource(index) {
  expandedSource.value = expandedSource.value === index ? -1 : index
}

function focus() {
  nextTick(() => questionInput.value?.focus())
}

defineExpose({ focus })
</script>

<style scoped>
.knowledge-panel { flex-shrink:0; margin:4px 12px 6px; padding:10px; border:1px solid #D7E7D8; border-radius:14px; background:rgba(250,255,250,.95); box-shadow:0 8px 24px rgba(64,116,70,.08); }
.knowledge-head, .knowledge-editor-actions, .knowledge-buttons, .source-summary { display:flex; align-items:center; }
.knowledge-head { justify-content:space-between; gap:8px; margin-bottom:8px; }
.knowledge-title { display:flex; align-items:center; gap:7px; font-size:14px; color:var(--ink); }
.knowledge-mark { width:28px; height:28px; display:flex; align-items:center; justify-content:center; border-radius:8px; background:#E4F1E4; color:#397747; }
.knowledge-mark svg, .knowledge-voice svg, .knowledge-send svg { width:17px; height:17px; fill:none; stroke:currentColor; stroke-width:1.9; stroke-linecap:round; stroke-linejoin:round; }
.knowledge-close { width:28px; height:28px; border-radius:50%; color:var(--sub); font-size:22px; line-height:1; }
.knowledge-close:active { background:var(--cream-2); color:var(--ink); }
.knowledge-suggestions { display:flex; gap:6px; overflow-x:auto; padding-bottom:8px; }
.knowledge-suggestions button { white-space:nowrap; border:1px solid #D7E7D8; border-radius:14px; background:#fff; color:#4C7854; padding:5px 9px; font-size:12px; }
.knowledge-editor { border:1px solid #D7E7D8; border-radius:10px; background:#fff; overflow:hidden; }
.knowledge-editor textarea { display:block; width:100%; min-height:46px; resize:none; border:0; outline:0; padding:9px 10px 4px; color:var(--ink); font:inherit; font-size:13px; line-height:19px; background:transparent; }
.knowledge-editor textarea::placeholder { color:var(--hint); }
.knowledge-editor textarea:disabled { color:var(--sub); }
.knowledge-editor-actions { justify-content:space-between; gap:8px; min-height:37px; padding:3px 5px 5px 10px; }
.voice-hint, .query-hint { min-width:0; color:#4C7854; font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.query-hint { color:var(--sub); }
.knowledge-buttons { gap:6px; }
.knowledge-voice, .knowledge-send { width:30px; height:30px; display:flex; align-items:center; justify-content:center; border-radius:50%; }
.knowledge-voice { color:#4C7854; background:#F3FAF3; border:1px solid #D7E7D8; }
.knowledge-voice.is-recording { color:#fff; background:var(--berry); border-color:var(--berry); animation:voice-pulse 1.2s ease-in-out infinite; }
.knowledge-voice.is-responding { color:#fff; background:#4C7854; border-color:#4C7854; }
.knowledge-voice.is-connecting { color:var(--sub); animation:voice-pulse 1s ease-in-out infinite; }
.knowledge-voice:disabled, .knowledge-send:disabled { opacity:.45; cursor:not-allowed; }
.knowledge-send { color:#fff; background:#4C9C5B; box-shadow:0 3px 8px rgba(59,135,71,.22); }
.knowledge-error { margin-top:8px; padding:7px 9px; border-radius:7px; background:#FFF0F3; color:#C85672; font-size:12px; line-height:17px; }
.knowledge-result { margin-top:9px; }
.knowledge-answer { color:var(--ink); font-size:13px; line-height:1.65; overflow-wrap:anywhere; }
.knowledge-answer :deep(p + p) { margin-top:7px; }
.knowledge-answer :deep(ul), .knowledge-answer :deep(ol) { padding-left:18px; margin:5px 0; }
.knowledge-wait { display:inline-flex; gap:4px; padding:8px 1px; }
.knowledge-wait i { width:6px; height:6px; border-radius:50%; background:#5FBE63; animation:knowledge-dot 1.1s infinite; }
.knowledge-wait i:nth-child(2) { animation-delay:.14s; }
.knowledge-wait i:nth-child(3) { animation-delay:.28s; }
.knowledge-sources { margin-top:10px; border-top:1px solid #E2EEE2; padding-top:9px; }
.sources-title { color:#4C7854; font-size:12px; font-weight:700; margin-bottom:6px; }
.source-list { display:grid; gap:5px; }
.source-item { border:1px solid #E0ECDD; border-radius:8px; background:#fff; overflow:hidden; }
.source-summary { width:100%; justify-content:space-between; gap:8px; padding:7px 8px; text-align:left; }
.source-copy { min-width:0; display:flex; flex-direction:column; gap:2px; }
.source-copy b { color:var(--ink); font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.source-copy span { color:var(--sub); font-size:11px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.source-toggle { flex-shrink:0; color:#4C7854; font-size:11px; }
.source-excerpt { padding:0 8px 8px; color:var(--ink-soft); font-size:12px; line-height:1.55; white-space:pre-wrap; overflow-wrap:anywhere; }
@keyframes knowledge-dot { 0%,60%,100% { transform:translateY(0); opacity:.4; } 30% { transform:translateY(-4px); opacity:1; } }
@keyframes voice-pulse { 50% { transform:scale(1.08); box-shadow:0 0 0 4px rgba(95,190,99,.15); } }
</style>
