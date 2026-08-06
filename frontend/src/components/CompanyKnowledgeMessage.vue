<template>
  <div :class="role === 'user' ? 'knowledge-msg-user' : 'knowledge-msg-agent'">
    <SoulOrb v-if="role === 'agent'" :template="soul || {}" size="xs" class="knowledge-soul" />
    <div :class="role === 'user' ? 'knowledge-user-bubble' : 'knowledge-agent-bubble'">
      <div class="knowledge-message-label">公司制度</div>
      <div v-if="role === 'user'" class="knowledge-user-content">{{ content }}</div>
      <div v-else class="knowledge-agent-content" v-html="renderMd(content)"></div>
      <section v-if="role === 'agent' && citations.length" class="message-sources">
        <div class="message-sources-title">参考制度</div>
        <button v-for="(source, index) in citations" :key="source.chunk_id || index" class="message-source" @click="toggleSource(index)">
          <span class="message-source-copy"><b>{{ source.title }}</b><span>{{ source.section_path || '未标注章节' }} · {{ source.version }}</span></span>
          <span>{{ expandedSource === index ? '收起' : '片段' }}</span>
        </button>
        <p v-if="expandedSource >= 0" class="message-excerpt">{{ citations[expandedSource]?.excerpt }}</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { marked } from 'marked'
import SoulOrb from './SoulOrb.vue'

defineProps({
  role: { type: String, default: 'agent' },
  content: { type: String, default: '' },
  citations: { type: Array, default: () => [] },
  soul: { type: Object, default: null },
})
const expandedSource = ref(-1)

function renderMd(text) {
  return text ? marked.parse(text) : ''
}

function toggleSource(index) {
  expandedSource.value = expandedSource.value === index ? -1 : index
}
</script>

<style scoped>
.knowledge-msg-agent { display:flex; gap:8px; align-items:flex-end; margin:12px 56px 4px 0; }
.knowledge-msg-user { display:flex; justify-content:flex-end; margin:12px 0 4px 56px; }
.knowledge-soul { flex-shrink:0; align-self:flex-end; margin-bottom:2px; }
.knowledge-agent-bubble, .knowledge-user-bubble { overflow:hidden; border-radius:6px 20px 20px 20px; padding:10px 12px; font-size:14px; line-height:1.6; }
.knowledge-agent-bubble { background:#F7FCF7; border:1px solid #D7E7D8; color:var(--ink); box-shadow:var(--shadow-sm); }
.knowledge-user-bubble { background:linear-gradient(135deg,#79BF79,#4C9C5B); color:#fff; border-radius:20px 20px 6px 20px; box-shadow:0 6px 16px rgba(70,140,80,.24); }
.knowledge-message-label { display:inline-flex; margin-bottom:5px; border-radius:8px; padding:2px 6px; background:#E4F1E4; color:#397747; font-size:10px; font-weight:700; }
.knowledge-user-bubble .knowledge-message-label { background:rgba(255,255,255,.18); color:#fff; }
.knowledge-user-content { white-space:pre-wrap; overflow-wrap:anywhere; }
.knowledge-agent-content { overflow-wrap:anywhere; }
.knowledge-agent-content :deep(p + p) { margin-top:6px; }
.knowledge-agent-content :deep(ul), .knowledge-agent-content :deep(ol) { padding-left:18px; margin:4px 0; }
.message-sources { margin-top:9px; padding-top:8px; border-top:1px solid #DCEBDD; }
.message-sources-title { color:#4C7854; font-size:11px; font-weight:700; margin-bottom:5px; }
.message-source { width:100%; display:flex; justify-content:space-between; align-items:center; gap:7px; padding:5px 0; text-align:left; color:#4C7854; font-size:11px; }
.message-source-copy { min-width:0; display:flex; flex-direction:column; gap:1px; }
.message-source-copy b, .message-source-copy span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.message-source-copy b { color:var(--ink); font-size:11px; }
.message-source-copy span { color:var(--sub); }
.message-excerpt { margin-top:3px; border-radius:6px; padding:7px; background:#fff; color:var(--ink-soft); font-size:11px; line-height:1.55; white-space:pre-wrap; overflow-wrap:anywhere; }
</style>
