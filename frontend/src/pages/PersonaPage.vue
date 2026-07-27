<template>
  <div class="scroll persona-scroll">
    <div class="persona-top">
      <button class="icon-btn" @click="$emit('back')" aria-label="返回">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>
      <div>
        <div class="page-title">人设小球</div>
        <div class="persona-sub">抽取、保留并切换伴行的陪伴风格</div>
      </div>
      <div class="persona-count">{{ ownedCount }}/{{ totalCount }}</div>
    </div>

    <div v-if="loading" class="persona-loading">
      <SoulOrb size="lg" />
      <span>加载中...</span>
    </div>

    <template v-else>
      <section class="persona-current">
        <SoulOrb :template="currentTemplate || {}" size="lg" :active="!!currentTemplate" />
        <div class="persona-current-text">
          <div class="page-label">当前风格</div>
          <h2>{{ currentTemplate?.name || '还未注入人设' }}</h2>
          <p>{{ currentTemplate?.orb?.tone || '抽到人设后，可以在这里切换。' }}</p>
        </div>
      </section>

      <section class="persona-actions">
        <button class="draw-btn" :disabled="drawing || ownedCount >= totalCount" @click="draw">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <rect x="3" y="3" width="18" height="18" rx="4" />
            <circle cx="8" cy="8" r="1" />
            <circle cx="16" cy="8" r="1" />
            <circle cx="12" cy="12" r="1" />
            <circle cx="8" cy="16" r="1" />
            <circle cx="16" cy="16" r="1" />
          </svg>
          {{ drawing ? '抽取中...' : ownedCount >= totalCount ? '已全部获得' : '随机抽取人设' }}
        </button>
      </section>

      <p v-if="message" :class="['persona-msg', messageTone]">{{ message }}</p>

      <section class="orb-section">
        <div class="section-head">
          <div>
            <div class="page-label">已获得</div>
            <strong>{{ ownedCount ? '点击小球切换当前风格' : '还没有获得人设' }}</strong>
          </div>
        </div>
        <div v-if="ownedSouls.length" class="owned-list">
          <button
            v-for="item in ownedSouls"
            :key="item.id"
            :class="['owned-item', item.active ? 'active' : '']"
            @click="inject(item)"
          >
            <SoulOrb :template="item" size="sm" :active="item.active" />
            <span>{{ item.name }}</span>
          </button>
        </div>
        <div v-else class="empty-state">点击上方按钮，先抽取一个人设小球。</div>
      </section>

      <section class="orb-section">
        <div class="page-label">全部小球</div>
        <div class="orb-grid">
          <button
            v-for="item in templates"
            :key="item.id"
            :class="['orb-cell', item.owned ? 'owned' : 'locked', item.active ? 'active' : '']"
            @click="item.owned ? inject(item) : null"
          >
            <SoulOrb :template="item" size="md" :locked="!item.owned" :active="item.active" />
            <span>{{ item.name }}</span>
            <small>{{ item.owned ? (item.active ? '当前' : '可切换') : '未获得' }}</small>
          </button>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import SoulOrb from '../components/SoulOrb.vue'
import { apiDrawSoul, apiGetSoulInventory, apiInjectSoul } from '../api/index'

const props = defineProps({
  refreshKey: { type: Number, default: 0 },
})
const emit = defineEmits(['back', 'changed'])

const loading = ref(true)
const drawing = ref(false)
const injectingId = ref('')
const inventory = ref({ templates: [], current: null, owned_count: 0, total_count: 5 })
const message = ref('')
const messageTone = ref('')

const templates = computed(() => inventory.value.templates || [])
const ownedSouls = computed(() => templates.value.filter((item) => item.owned))
const currentTemplate = computed(() => inventory.value.current || ownedSouls.value.find((item) => item.active) || null)
const ownedCount = computed(() => inventory.value.owned_count || ownedSouls.value.length)
const totalCount = computed(() => inventory.value.total_count || templates.value.length || 5)

onMounted(loadInventory)
watch(() => props.refreshKey, loadInventory)

async function loadInventory() {
  loading.value = true
  message.value = ''
  try {
    inventory.value = await apiGetSoulInventory()
  } catch (e) {
    console.error('load soul inventory error:', e)
    messageTone.value = 'error'
    message.value = '加载失败，请确认后端已经启动。'
  } finally {
    loading.value = false
  }
}

async function draw() {
  if (drawing.value || ownedCount.value >= totalCount.value) return
  drawing.value = true
  message.value = ''
  try {
    const res = await apiDrawSoul()
    if (res.inventory) inventory.value = res.inventory
    messageTone.value = res.success ? 'ok' : 'hint'
    message.value = res.success ? `抽到了「${res.template?.name || '新人设'}」` : (res.message || '已经全部获得')
    if (res.success) emit('changed')
  } catch (e) {
    console.error('draw soul error:', e)
    messageTone.value = 'error'
    message.value = '抽取失败，请稍后再试。'
  } finally {
    drawing.value = false
  }
}

async function inject(item) {
  if (!item?.owned || item.active || injectingId.value) return
  injectingId.value = item.id
  message.value = ''
  try {
    const res = await apiInjectSoul(item.id)
    if (res.inventory) inventory.value = res.inventory
    messageTone.value = res.success ? 'ok' : 'error'
    message.value = res.success ? `已切换到「${item.name}」` : (res.message || '切换失败')
    if (res.success) emit('changed')
  } catch (e) {
    console.error('inject soul error:', e)
    messageTone.value = 'error'
    message.value = '切换失败，请稍后再试。'
  } finally {
    injectingId.value = ''
  }
}
</script>

<style scoped>
.persona-scroll {
  padding-bottom: 22px;
}
.persona-top {
  display: grid;
  grid-template-columns: 34px 1fr auto;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(255,255,255,.72);
  border: 1px solid var(--line);
  color: var(--ink-soft);
  display: flex;
  align-items: center;
  justify-content: center;
}
.icon-btn svg {
  width: 20px;
  height: 20px;
  stroke-width: 2.4;
}
.persona-sub {
  color: var(--sub);
  font-size: 12px;
  margin-top: -8px;
}
.persona-count {
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,.72);
  border: 1px solid var(--line);
  color: var(--honey-deep);
  font-size: 12px;
  font-weight: 700;
}
.persona-loading {
  min-height: 360px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  color: var(--sub);
}
.persona-current {
  min-height: 126px;
  display: grid;
  grid-template-columns: 98px 1fr;
  align-items: center;
  gap: 14px;
  padding: 18px;
  border-radius: var(--r-md);
  background: rgba(255,255,255,.86);
  box-shadow: var(--shadow-sm);
}
.persona-current-text h2 {
  font-size: 20px;
  line-height: 1.25;
  margin: 0 0 5px;
}
.persona-current-text p {
  color: var(--ink-soft);
  font-size: 13px;
  line-height: 1.5;
}
.persona-actions {
  display: flex;
  gap: 10px;
  margin: 14px 0 10px;
}
.draw-btn {
  flex: 1;
  height: 46px;
  border-radius: 23px;
  background: linear-gradient(135deg, #FFB78A, #FF8F6E);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 8px 20px rgba(255,130,80,.28);
}
.draw-btn:disabled {
  opacity: .55;
}
.draw-btn svg {
  width: 19px;
  height: 19px;
  stroke-width: 2.2;
}
.persona-msg {
  min-height: 28px;
  padding: 7px 12px;
  border-radius: 14px;
  font-size: 13px;
  margin-bottom: 10px;
}
.persona-msg.ok {
  color: #37723A;
  background: var(--sprout-soft);
}
.persona-msg.hint {
  color: var(--honey-deep);
  background: var(--honey-soft);
}
.persona-msg.error {
  color: var(--berry);
  background: var(--berry-soft);
}
.orb-section {
  margin-top: 12px;
  padding: 16px;
  border-radius: var(--r-md);
  background: rgba(255,255,255,.82);
  box-shadow: var(--shadow-sm);
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.section-head strong {
  font-size: 14px;
}
.owned-list {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 4px 0;
}
.owned-item {
  min-width: 92px;
  height: 88px;
  border-radius: 16px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,.68);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: var(--ink-soft);
  font-size: 12px;
  font-weight: 600;
}
.owned-item.active {
  color: var(--honey-deep);
  border-color: rgba(255,143,110,.45);
  background: var(--honey-soft);
}
.empty-state {
  padding: 12px 0 4px;
  color: var(--sub);
  font-size: 13px;
}
.orb-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.orb-cell {
  min-height: 122px;
  border-radius: 18px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,.66);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 10px 6px;
}
.orb-cell.locked {
  color: var(--sub);
}
.orb-cell.active {
  border-color: rgba(255,143,110,.45);
  background: var(--honey-soft);
}
.orb-cell span {
  max-width: 100%;
  font-size: 12px;
  font-weight: 700;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.orb-cell small {
  font-size: 10px;
  color: var(--sub);
}
@media (max-width: 380px) {
  .orb-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
