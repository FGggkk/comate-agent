<template>
  <div class="scroll persona-scroll">
    <div class="persona-top">
      <button class="icon-btn" @click="$emit('back')" aria-label="返回">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path d="M15 18l-6-6 6-6" />
        </svg>
      </button>
      <div>
        <div class="page-title">灵魂卡池</div>
        <div class="persona-sub">抽取并放置管理端注入的灵魂</div>
      </div>
      <div class="persona-count">{{ occupiedCount }}/{{ slotCapacity }}</div>
    </div>

    <div v-if="loading" class="persona-loading">
      <span class="loading-orb" aria-hidden="true"></span>
      <span>加载中...</span>
    </div>

    <template v-else>
      <!-- 当前注入 -->
      <section class="persona-current">
        <div
          class="current-avatar"
          :style="currentTemplate ? cardFace(currentTemplate) : {}"
        >
          <img v-if="currentTemplate?.avatar_image" :src="currentTemplate.avatar_image" alt="" />
          <span v-else>{{ currentTemplate?.name?.[0] || '?' }}</span>
        </div>
        <div class="persona-current-text">
          <div class="page-label">当前注入</div>
          <h2>{{ currentTemplate?.name || '尚未注入灵魂' }}</h2>
          <p>{{ currentSoulLine }}</p>
        </div>
      </section>

      <!-- 抽取入口 -->
      <section class="persona-actions">
        <button class="draw-btn" :disabled="!hasUnowned" @click="openGacha">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M12 3v18M3 12h18" />
          </svg>
          {{ hasUnowned ? '抽取灵魂' : '全部灵魂已放置' }}
        </button>
      </section>

      <p v-if="message" :class="['persona-msg', messageTone]">{{ message }}</p>

      <!-- 我的卡槽 -->
      <section class="orb-section">
        <div class="section-head">
          <div>
            <div class="page-label">我的卡槽</div>
            <strong>{{ occupiedCount }}/{{ slotCapacity }} · 点击卡片注入灵魂</strong>
          </div>
          <button class="fold-btn" :class="{ folded: slotsCollapsed }" @click="slotsCollapsed = !slotsCollapsed" :aria-label="slotsCollapsed ? '展开卡槽' : '收起卡槽'">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M6 9l6 6 6-6" /></svg>
          </button>
        </div>
        <div v-show="!slotsCollapsed" class="slot-grid">
          <div v-for="n in slotCells" :key="n" class="slot-cell-wrap">
            <div
              v-if="!slotAt(n - 1)"
              :class="['slot-cell', 'slot-empty', { clickable: hasUnowned }]"
              @click="openGacha"
            >
              <span class="slot-empty-num">{{ n }}</span>
              <small>{{ hasUnowned ? '点击抽取' : '空' }}</small>
            </div>
            <div
              v-else
              :class="['slot-cell', { injected: slotAt(n - 1).active }]"
              @click="inject(slotAt(n - 1))"
            >
              <div class="slot-front" :style="cardFace(slotAt(n - 1))">
                <span class="slot-badge" :class="slotAt(n - 1).active ? 'on' : ''">{{ slotBadge(slotAt(n - 1)) }}</span>
                <span v-if="slotAt(n - 1).slug === 'warm_companion'" class="classic-badge">经典</span>
                <img v-if="slotAt(n - 1).avatar_image" class="slot-avatar" :src="slotAt(n - 1).avatar_image" alt="" />
                <span v-else class="slot-avatar-fallback">{{ slotAt(n - 1).name?.[0] }}</span>
                <span class="slot-name">{{ slotAt(n - 1).name }}</span>
                <div class="slot-actions" @click.stop>
                  <button v-if="!slotAt(n - 1).active" class="slot-act primary" @click="inject(slotAt(n - 1))">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" /></svg>
                    <span class="tip">注入</span>
                  </button>
                  <button class="slot-act" @click="openDetail(slotAt(n - 1))">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" /></svg>
                    <span class="tip">详情</span>
                  </button>
                  <button class="slot-act danger" :class="{ armed: deleteArmed === slotAt(n - 1).slot_id }" @click="armDelete(slotAt(n - 1))">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" /></svg>
                    <span class="tip">{{ deleteArmed === slotAt(n - 1).slot_id ? '确认删除' : '删除' }}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 灵魂图鉴 -->
      <section v-if="templates.length" class="orb-section">
        <div class="section-head">
          <div>
            <div class="page-label">灵魂图鉴</div>
            <strong>{{ galleryDesc }}</strong>
          </div>
          <div class="head-right">
            <div class="gallery-tabs">
              <button :class="{ active: galleryFilter === 'all' }" @click="setGalleryFilter('all')">全部</button>
              <button :class="{ active: galleryFilter === 'owned' }" @click="setGalleryFilter('owned')">已点亮</button>
              <button :class="{ active: galleryFilter === 'unowned' }" @click="setGalleryFilter('unowned')">未点亮</button>
            </div>
            <button class="fold-btn" :class="{ folded: galleryCollapsed }" @click="galleryCollapsed = !galleryCollapsed" :aria-label="galleryCollapsed ? '展开图鉴' : '收起图鉴'">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M6 9l6 6 6-6" /></svg>
            </button>
          </div>
        </div>
        <div v-show="!galleryCollapsed">
          <div class="deck-grid">
            <div v-for="item in galleryPageSouls" :key="item.id" class="deck-card" :class="{ dim: !item.owned }" @click="openDetail(item)">
              <div class="deck-inner">
                <div class="deck-face deck-front" :style="cardFace(item)">
                  <span v-if="item.slug === 'warm_companion'" class="classic-badge">经典</span>
                  <img v-if="item.avatar_image" class="deck-avatar" :src="item.avatar_image" alt="" />
                  <span v-else class="deck-avatar-fallback">{{ item.name?.[0] }}</span>
                  <span class="deck-name">{{ item.name }}</span>
                  <small class="deck-status" :class="{ owned: item.owned, active: item.active }">{{ deckStatus(item) }}</small>
                </div>
                <div class="deck-face deck-back">
                  <div class="deck-back-name">{{ item.name }}</div>
                  <p class="deck-desc">{{ deckDesc(item) }}</p>
                  <div v-if="item.tags?.length" class="deck-tags">
                    <span v-for="tag in item.tags.slice(0, 3)" :key="tag">{{ tag }}</span>
                  </div>
                  <div v-if="item.orb?.tone" class="deck-tone">{{ item.orb.tone }}</div>
                </div>
              </div>
            </div>
          </div>
          <div v-if="galleryTotalPages > 1" class="gallery-pager">
            <button class="pager-btn" :disabled="galleryPage <= 1" @click="galleryPage--">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M15 18l-6-6 6-6" /></svg>
            </button>
            <span class="pager-num">{{ galleryPage }} / {{ galleryTotalPages }}</span>
            <button class="pager-btn" :disabled="galleryPage >= galleryTotalPages" @click="galleryPage++">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M9 6l6 6-6 6" /></svg>
            </button>
          </div>
        </div>
      </section>

      <!-- 命运抽卡弹窗 -->
      <div v-if="gachaOpen" class="gacha-overlay" @click.self="tryCloseGacha">
        <div class="gacha-modal" :class="'phase-' + gacha.phase" role="dialog" aria-label="命运抽卡">
          <div class="gacha-glow" aria-hidden="true"></div>
          <div class="gacha-head">
            <div>
              <div class="page-label gacha-label">命运抽卡</div>
              <strong class="gacha-hint">{{ gachaHint }}</strong>
            </div>
            <button class="gacha-close" @click="tryCloseGacha" aria-label="关闭">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>

          <TransitionGroup name="shuffle" tag="div" class="gacha-stage">
            <div
              v-for="(slot, i) in gachaSlots"
              :key="slot?.id ?? i"
              :class="[
                'gacha-card',
                { picked: i === gacha.picked },
                { faded: (gacha.phase === 'revealing' || gacha.phase === 'done') && i !== gacha.picked },
                'rs' + gacha.revealStep,
              ]"
              @click="pickCard(i)"
            >
              <!-- 光柱（③ 升卡后出现，卡色联动） -->
              <div v-if="i === gacha.picked && gacha.revealStep >= 2" class="gacha-beam" :style="beamStyle" aria-hidden="true">
                <span class="beam-dot d1"></span>
                <span class="beam-dot d2"></span>
                <span class="beam-dot d3"></span>
              </div>
              <!-- 光圈（④ 翻面时扩散） -->
              <div v-if="i === gacha.picked && gacha.revealStep >= 3" class="gacha-ring" :style="ringStyle" aria-hidden="true"></div>
              <div
                class="gacha-inner"
                :class="{ flipped: gacha.revealStep >= 3 && i === gacha.picked }"
              >
                <div class="gacha-face gacha-back">
                  <span class="gacha-back-star s1">✦</span>
                  <span class="gacha-back-star s2">✧</span>
                  <span class="gacha-back-star s3">✦</span>
                  <div class="gacha-back-core"></div>
                  <small>命运之卡</small>
                </div>
                <div class="gacha-face gacha-result" :style="resultStyle">
                  <img v-if="drawnTemplate?.avatar_image" class="gacha-result-img" :src="drawnTemplate.avatar_image" alt="" />
                  <span v-else class="gacha-result-fallback">{{ drawnTemplate?.name?.[0] || '✦' }}</span>
                  <span class="gacha-result-name">{{ drawnTemplate?.name || '✦' }}</span>
                  <span class="gacha-result-tone">{{ drawnTemplate?.orb?.tone || drawnTemplate?.description || '' }}</span>
                  <span v-if="gacha.phase === 'done'" class="gacha-new-badge">NEW</span>
                  <span v-if="gacha.revealStep === 3" v-for="n in 6" :key="n" class="gacha-spark" :style="sparkStyle(n)" aria-hidden="true"></span>
                </div>
              </div>
            </div>
          </TransitionGroup>

          <p v-if="message" :class="['gacha-msg', messageTone]">{{ message }}</p>

          <div class="gacha-cta">
            <button v-if="gacha.phase === 'idle'" class="draw-btn" :disabled="gacha.busy || !hasUnowned" @click="startGacha()">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M12 3v18M3 12h18" />
              </svg>
              {{ !hasUnowned ? '全部灵魂已放置' : gacha.busy ? '命运读取中...' : '开始抽取' }}
            </button>

            <template v-else-if="gacha.phase === 'done' && !replaceMode">
              <button class="draw-btn" :disabled="saving" @click="saveDrawn">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
                  <path d="M17 21v-8H7v8M7 3v5h8" />
                </svg>
                {{ slotsFull ? '替换保存' : '保存到卡槽' }}
              </button>
              <button class="draw-btn ghost" :disabled="saving" @click="reroll">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6" />
                </svg>
                丢弃重抽
              </button>
              <button class="draw-btn ghost" :disabled="saving" @click="tryCloseGacha">放弃</button>
            </template>

            <template v-else-if="gacha.phase === 'done' && replaceMode">
              <div class="replace-hint">卡槽已满，先点选一张旧灵魂，再确认替换（{{ drawnTemplate?.name }} 将入槽）</div>
              <div class="replace-grid">
                <button
                  v-for="item in ownedSouls"
                  :key="item.id"
                  class="replace-item"
                  :class="{ active: item.active, selected: replaceSelected === item.slot_id }"
                  @click="replaceSelected = replaceSelected === item.slot_id ? '' : item.slot_id"
                >
                  <img v-if="item.avatar_image" class="replace-avatar" :src="item.avatar_image" alt="" />
                  <span v-else class="replace-fallback" :style="{ background: soulColor(item) }">{{ item.name?.[0] }}</span>
                  <span class="replace-name">{{ item.name }}</span>
                  <small>{{ item.active ? '已注入' : '' }}</small>
                </button>
              </div>
              <div class="replace-cta">
                <button class="draw-btn confirm-btn" :disabled="!replaceSelected || saving" @click="confirmReplace">
                  {{ replaceSelected ? '确认替换' : '请先选择一张旧灵魂' }}
                </button>
                <button class="draw-btn ghost" @click="replaceMode = false">取消</button>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- 灵魂详情弹窗 -->
      <div v-if="detailSoul" class="gacha-overlay" @click.self="detailSoul = null">
        <div class="detail-modal">
          <div class="detail-head">
            <div class="detail-avatar" :style="cardFace(detailSoul)">
              <img v-if="detailSoul.avatar_image" :src="detailSoul.avatar_image" alt="" />
              <span v-else>{{ detailSoul.name?.[0] }}</span>
            </div>
            <div class="detail-title">
              <b>{{ detailSoul.name }}</b>
              <small>{{ deckDesc(detailSoul) }}</small>
            </div>
            <button class="gacha-close" @click="detailSoul = null" aria-label="关闭">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="detail-md" v-html="renderMd(detailSoul.soul_markdown || '')"></div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { marked } from 'marked'
import { apiDrawSoul, apiGetSoulInventory, apiInjectSoul, apiSaveSoulSlot, apiDeleteSoulSlot } from '../api/index'

const props = defineProps({
  refreshKey: { type: Number, default: 0 },
})
const emit = defineEmits(['back', 'changed'])

const loading = ref(true)
const saving = ref(false)
const injectingId = ref('')
const deleteArmed = ref('')
const inventory = ref({ templates: [], current: null, owned_count: 0, total_count: 5, slot_capacity: 4, occupied_count: 0 })
const message = ref('')
const messageTone = ref('')

// —— 命运抽卡状态机 ——
const gacha = ref({ phase: 'idle', picked: null, busy: false, drawn: null })
const gachaOpen = ref(false)
const replaceMode = ref(false)
const replaceSelected = ref('')
const gachaSlots = ref([])
const shuffleSeed = ref(0)
let shuffleTimer = null
let revealTimer = null
let pickTimer = null
let deleteTimer = null
let loadSeq = 0

// —— 灵魂详情 ——
const detailSoul = ref(null)

// —— 卡色提取缓存 ——
const colorMap = ref({})

const templates = computed(() => inventory.value.templates || [])
const ownedSouls = computed(() => templates.value.filter((item) => item.owned))
const unownedSouls = computed(() => templates.value.filter((item) => !item.owned))
// 图鉴筛选：全部 / 已点亮 / 未点亮
const galleryFilter = ref('all')
const gallerySouls = computed(() => {
  if (galleryFilter.value === 'owned') return ownedSouls.value
  if (galleryFilter.value === 'unowned') return unownedSouls.value
  return templates.value
})
const galleryDesc = computed(() => {
  if (galleryFilter.value === 'owned') return `已点亮 ${ownedSouls.value.length} 张 · 点击卡片查看详情`
  if (galleryFilter.value === 'unowned') return `未点亮 ${unownedSouls.value.length} 张 · 抽取后点亮`
  return `全部灵魂 ${templates.value.length} 张 · 点击卡片查看详情`
})
// 区块折叠
const slotsCollapsed = ref(false)
const galleryCollapsed = ref(false)
// 图鉴分页（每页 6 个）
const GALLERY_PAGE_SIZE = 6
const galleryPage = ref(1)
const galleryTotalPages = computed(() => Math.max(1, Math.ceil(gallerySouls.value.length / GALLERY_PAGE_SIZE)))
const galleryPageSouls = computed(() => {
  const start = (galleryPage.value - 1) * GALLERY_PAGE_SIZE
  return gallerySouls.value.slice(start, start + GALLERY_PAGE_SIZE)
})
function setGalleryFilter(f) {
  galleryFilter.value = f
  galleryPage.value = 1
}
const currentTemplate = computed(() => inventory.value.current || ownedSouls.value.find((item) => item.active) || null)
// 当前注入第三行：语气 → 标签 → 简介 依次兜底
const currentSoulLine = computed(() => {
  const t = currentTemplate.value
  if (!t) return '在卡槽中选择一个灵魂注入'
  if (t.orb?.tone) return t.orb.tone
  if (t.tags?.length) return t.tags.slice(0, 3).join(' · ')
  if (t.description) return t.description
  return '点击卡槽卡片注入灵魂'
})
const ownedCount = computed(() => inventory.value.owned_count || ownedSouls.value.length)
const slotCapacity = computed(() => inventory.value.slot_capacity || 6)
const occupiedCount = computed(() => inventory.value.occupied_count ?? ownedCount.value)
const slotsFull = computed(() => occupiedCount.value >= slotCapacity.value)
const hasUnowned = computed(() => inventory.value.has_unowned ?? unownedSouls.value.length > 0)
const drawnTemplate = computed(() => gacha.value.drawn)
// 网格格数 = max(容量, 已有卡数)：卡槽被管理员降档时，多出的卡仍可见可删，避免 UI 死锁
const slotCells = computed(() => Math.max(slotCapacity.value, ownedSouls.value.length))

function slotAt(i) {
  return ownedSouls.value[i] || null
}

const gachaHint = computed(() => {
  if (replaceMode.value) return '替换旧灵魂'
  switch (gacha.value.phase) {
    case 'idle': return hasUnowned.value ? `从 ${unownedSouls.value.length} 张未拥有的灵魂中随机抽取，点一张翻开` : '全部灵魂都已收入卡槽'
    case 'shuffling': return '命运正在洗牌……'
    case 'picking': return '点一张卡，翻开你的灵魂'
    case 'revealing': return '命运揭晓……'
    case 'done': return drawnTemplate.value ? `抽到「${drawnTemplate.value.name}」` : ''
    default: return ''
  }
})

onMounted(async () => {
  await loadInventory()
})
watch(() => props.refreshKey, loadInventory)

// 弹窗打开时锁定页面滚动
watch(gachaOpen, (open) => {
  document.body.style.overflow = open ? 'hidden' : ''
})
watch(detailSoul, (s) => {
  document.body.style.overflow = s ? 'hidden' : ''
})

async function loadInventory() {
  if (['shuffling', 'picking', 'revealing'].includes(gacha.value.phase)) return
  const seq = ++loadSeq
  loading.value = true
  message.value = ''
  try {
    inventory.value = await apiGetSoulInventory()
    if (seq !== loadSeq) return
    extractMissingColors()
  } catch (e) {
    console.error('load soul inventory error:', e)
    messageTone.value = 'error'
    message.value = '加载失败，请确认后端已经启动。'
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

function openGacha() {
  if (!hasUnowned.value) return
  message.value = ''
  replaceMode.value = false
  // 展示台：随机取 6 张未拥有的灵魂作为候选卡面（不足 6 张则全部）
  gachaSlots.value = shuffleArr(unownedSouls.value).slice(0, 6)
  gacha.value = { phase: 'idle', picked: null, busy: false, drawn: null }
  gachaOpen.value = true
}

function tryCloseGacha() {
  if (gacha.value.phase !== 'idle' && gacha.value.phase !== 'done') return
  gachaOpen.value = false
  replaceMode.value = false
}

async function startGacha(excludeTemplateId = null) {
  if (gacha.value.busy || !hasUnowned.value) return
  gacha.value.busy = true
  message.value = ''
  gacha.value.phase = 'shuffling'
  gacha.value.picked = null
  replaceMode.value = false
  shuffleSeed.value = Math.floor(Math.random() * 1000)
  let rounds = 0
  shuffleTimer = setInterval(() => {
    gachaSlots.value = shuffleArr(gachaSlots.value)
    shuffleSeed.value = Math.floor(Math.random() * 1000)
    rounds += 1
    if (rounds >= 3) clearInterval(shuffleTimer)
  }, 450)
  try {
    const res = await apiDrawSoul(excludeTemplateId)
    if (res.success) {
      gacha.value.drawn = res.template
      if (res.inventory) inventory.value = res.inventory
      revealTimer = setTimeout(() => {
        gacha.value.busy = false
        gacha.value.phase = 'picking'
      }, 2000)
    } else {
      clearInterval(shuffleTimer)
      gacha.value.phase = 'idle'
      gacha.value.busy = false
      if (res.inventory) inventory.value = res.inventory
      messageTone.value = 'hint'
      message.value = res.message || '已经全部放置'
    }
  } catch (e) {
    console.error('draw soul error:', e)
    clearInterval(shuffleTimer)
    gacha.value.phase = 'idle'
    gacha.value.busy = false
    messageTone.value = 'error'
    message.value = '抽取失败，请稍后再试。'
  }
}

function pickCard(i) {
  if (gacha.value.phase !== 'picking' || gacha.value.busy || gacha.value.picked !== null) return
  gacha.value.busy = true
  gacha.value.picked = i
  gacha.value.phase = 'revealing'
  gacha.value.revealStep = 0
  // 在锁定（rs0，卡片仍在网格原位）时测量并计算 --lift-x/--lift-y，让任何位置选中的卡都飞到舞台正中央
  nextTick(() => {
    requestAnimationFrame(() => {
      const picked = document.querySelector('.gacha-card.picked')
      const stage = picked?.closest('.gacha-stage')
      if (!picked || !stage) return
      const stageRect = stage.getBoundingClientRect()
      const cardRect = picked.getBoundingClientRect()
      const dx = (stageRect.left + stageRect.width / 2) - (cardRect.left + cardRect.width / 2)
      const dy = (stageRect.top + stageRect.height / 2) - (cardRect.top + cardRect.height / 2)
      picked.style.setProperty('--lift-x', `${Math.round(dx)}px`)
      picked.style.setProperty('--lift-y', `${Math.round(dy)}px`)
    })
  })
  // 四步仪式：①锁定 → ②升卡 → ③光柱 → ④翻面
  setTimeout(() => { gacha.value.revealStep = 1 }, 260)
  setTimeout(() => { gacha.value.revealStep = 2 }, 620)
  setTimeout(() => { gacha.value.revealStep = 3 }, 980)
  pickTimer = setTimeout(() => {
    gacha.value.phase = 'done'
    gacha.value.revealStep = 4
    gacha.value.busy = false
  }, 1780)
}

// 丢弃重抽：排除刚抽到的那张，保证重抽结果不同
async function reroll() {
  if (saving.value) return
  // 展示台同步换一批随机未拥有候选
  gachaSlots.value = shuffleArr(unownedSouls.value).slice(0, 6)
  await startGacha(drawnTemplate.value?.id)
}

// 保存到卡槽（卡槽满则进入替换模式）
async function saveDrawn() {
  const t = drawnTemplate.value
  if (!t || saving.value) return
  if (slotsFull.value) {
    replaceSelected.value = ''
    replaceMode.value = true
    return
  }
  saving.value = true
  message.value = ''
  try {
    const res = await apiSaveSoulSlot(t.id)
    inventory.value = await apiGetSoulInventory()
    if (res.success) {
      messageTone.value = 'ok'
      message.value = res.message
      emit('changed')
      // 立即关闭弹窗，避免延迟窗口期内重复操作产生竞态
      gachaOpen.value = false
    } else {
      messageTone.value = 'error'
      message.value = res.message || '保存失败'
      if (res.need_replace) {
        replaceSelected.value = ''
        replaceMode.value = true
      }
    }
  } catch (e) {
    console.error('save soul error:', e)
    messageTone.value = 'error'
    message.value = '保存失败，请稍后再试。'
  } finally {
    saving.value = false
  }
}

// 确认替换：从选中的旧卡执行替换
function confirmReplace() {
  const item = ownedSouls.value.find(i => i.slot_id === replaceSelected.value)
  if (!item) return
  replaceWith(item)
}

async function replaceWith(item) {
  const t = drawnTemplate.value
  if (!t || saving.value) return
  saving.value = true
  message.value = ''
  try {
    const res = await apiSaveSoulSlot(t.id, item.slot_id)
    inventory.value = await apiGetSoulInventory()
    if (res.success) {
      messageTone.value = 'ok'
      message.value = res.message
      emit('changed')
      replaceMode.value = false
      gachaOpen.value = false
    } else {
      messageTone.value = 'error'
      message.value = res.message || '替换失败'
    }
  } catch (e) {
    console.error('replace soul error:', e)
    messageTone.value = 'error'
    message.value = '替换失败，请稍后再试。'
  } finally {
    saving.value = false
  }
}

function armDelete(item) {
  if (deleteArmed.value === item.slot_id) {
    // 二次确认后真正删除
    doDelete(item)
    return
  }
  deleteArmed.value = item.slot_id
  if (deleteTimer) clearTimeout(deleteTimer)
  deleteTimer = setTimeout(() => { deleteArmed.value = '' }, 3000)
}

async function doDelete(item) {
  if (!item.slot_id || saving.value) return
  saving.value = true
  message.value = ''
  try {
    const res = await apiDeleteSoulSlot(item.slot_id)
    // 无论返回什么，都以最新库存为准，避免卡槽数量显示不同步
    inventory.value = await apiGetSoulInventory()
    deleteArmed.value = ''
    messageTone.value = res.success ? 'ok' : 'error'
    message.value = res.success ? `已删除「${item.name}」` : (res.message || '删除失败')
    if (res.success) emit('changed')
  } catch (e) {
    console.error('delete soul error:', e)
    messageTone.value = 'error'
    message.value = '删除失败，请稍后再试。'
  } finally {
    saving.value = false
  }
}

async function inject(item) {
  if (!item?.owned || item.active || injectingId.value) return
  injectingId.value = item.id
  message.value = ''
  try {
    const res = await apiInjectSoul(item.id)
    inventory.value = await apiGetSoulInventory()
    messageTone.value = res.success ? 'ok' : 'error'
    message.value = res.success ? `已注入「${item.name}」` : (res.message || '注入失败')
    if (res.success) emit('changed')
  } catch (e) {
    console.error('inject soul error:', e)
    messageTone.value = 'error'
    message.value = '注入失败，请稍后再试。'
  } finally {
    injectingId.value = ''
  }
}

function openDetail(item) {
  detailSoul.value = item
}

function renderMd(text) {
  let html = ''
  try {
    html = marked.parse(text || '')
  } catch {
    return text || ''
  }
  // 防御性净化：内容来自管理端（可信域），但仍剥离脚本与事件属性
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
    .replace(/javascript:/gi, '')
}

// —— Fisher–Yates ——
function shuffleArr(arr) {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

// —— 卡色：优先管理端 color，缺失则从头像图提取主色 ——
const palette = ['#FF9F7A', '#5FBE63', '#5FB0E8', '#FF6F91', '#FF9F45', '#9B6FD8', '#5B7FA6', '#C99A2E', '#5B7FA6', '#E85D75', '#58A6B5', '#B48EAD']

function soulColor(item) {
  if (!item) return '#C99A2E'
  if (item.color) return item.color
  const cached = colorMap.value[item.id]
  if (cached) return cached
  if (item.orb?.colors?.length) return item.orb.colors[0]
  return palette[(item.name ? item.name.length : 0) % palette.length]
}

function cardFace(item) {
  if (!item) return {}
  const c = soulColor(item)
  return {
    background: `radial-gradient(circle at 28% 22%, ${c}, ${c}bb 55%, #f3e9dc 160%)`,
  }
}

function extractMissingColors() {
  const tasks = []
  for (const t of templates.value) {
    if (!t.avatar_image || t.color) continue
    if (colorMap.value[t.id]) continue
    tasks.push(extractAvatarColor(t.avatar_image).then((c) => {
      if (c) colorMap.value[t.id] = c
    }))
  }
  return Promise.allSettled(tasks)
}

function extractAvatarColor(url) {
  return new Promise((resolve) => {
    try {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => {
        try {
          const c = document.createElement('canvas')
          c.width = 48
          c.height = 48
          const ctx = c.getContext('2d')
          ctx.drawImage(img, 0, 0, 48, 48)
          const data = ctx.getImageData(0, 0, 48, 48).data
          let r = 0, g = 0, b = 0, n = 0
          for (let i = 0; i < data.length; i += 4) {
            if (data[i + 3] < 128) continue
            r += data[i]; g += data[i + 1]; b += data[i + 2]; n += 1
          }
          resolve(n ? `rgb(${Math.round(r / n)}, ${Math.round(g / n)}, ${Math.round(b / n)})` : null)
        } catch { resolve(null) }
      }
      img.onerror = () => resolve(null)
      img.src = url
    } catch { resolve(null) }
  })
}

// —— 抽卡视觉 ——
const resultStyle = computed(() => {
  const t = drawnTemplate.value
  const c = soulColor(t)
  return { background: `radial-gradient(circle at 32% 26%, ${c}, ${c}bb 58%, #3a2a55 130%)` }
})

// 揭示光效跟随抽到的灵魂卡色
const beamStyle = computed(() => {
  const c = soulColor(drawnTemplate.value)
  return { background: `linear-gradient(to top, ${c}80, ${c}26 60%, transparent)` }
})
const ringStyle = computed(() => {
  const c = soulColor(drawnTemplate.value)
  return { borderColor: c, boxShadow: `0 0 34px 8px ${c}66, inset 0 0 20px ${c}55` }
})
function burstStyle(n) {
  const angle = (n / 8) * Math.PI * 2
  const dist = 74 + (n % 3) * 20
  return {
    '--bx': `${Math.cos(angle) * dist}px`,
    '--by': `${Math.sin(angle) * dist}px`,
    color: soulColor(drawnTemplate.value),
    animationDelay: `${n * 0.045}s`,
  }
}

function sparkStyle(n) {
  const angle = (n / 6) * Math.PI * 2
  return {
    '--sx': `${Math.cos(angle) * 46}px`,
    '--sy': `${Math.sin(angle) * 46}px`,
    animationDelay: `${n * 0.07}s`,
  }
}

function deckDesc(item) {
  return item.description || item.orb?.intro || '一个神秘的灵魂，抽到后才知道它的故事。'
}

function deckStatus(item) {
  if (item.status && item.status !== 'active') return '已下架'
  if (item.active) return '已注入'
  if (item.owned) return '已点亮'
  return '未点亮'
}

function slotBadge(item) {
  if (item.status && item.status !== 'active') return '已下架'
  if (item.active) return '已注入'
  return '可注入'
}

onBeforeUnmount(() => {
  if (shuffleTimer) clearInterval(shuffleTimer)
  if (revealTimer) clearTimeout(revealTimer)
  if (pickTimer) clearTimeout(pickTimer)
  if (deleteTimer) clearTimeout(deleteTimer)
  document.body.style.overflow = ''
})
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
.loading-orb {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #ffe2a8, #f0a94e 60%, #c98a2e);
  animation: loading-bob 1.2s ease-in-out infinite;
}
@keyframes loading-bob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

/* 当前注入 */
.persona-current {
  min-height: 108px;
  display: grid;
  grid-template-columns: 82px 1fr;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border-radius: var(--r-md);
  background: rgba(255,255,255,.86);
  box-shadow: var(--shadow-sm);
}
.current-avatar {
  width: 78px;
  height: 78px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  color: #fff;
  font-size: 30px;
  font-weight: 800;
  box-shadow: 0 6px 16px rgba(0,0,0,.14);
  flex: 0 0 auto;
}
.current-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
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

/* 抽取入口 */
.persona-actions {
  display: flex;
  gap: 10px;
  margin: 14px 0 2px;
}
.draw-btn {
  width: 100%;
  height: 46px;
  border-radius: 23px;
  border: none;
  background: linear-gradient(135deg, #ffd76b, #ff9f45);
  color: #5b3a00;
  font-size: 15px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  box-shadow: 0 8px 22px rgba(255, 170, 60, .4);
  transition: transform .18s ease;
}
.draw-btn:hover { transform: translateY(-1px); }
.draw-btn:active { transform: scale(.97); }
.draw-btn:disabled {
  opacity: .6;
  cursor: not-allowed;
}
.draw-btn svg {
  width: 18px;
  height: 18px;
  stroke-width: 2.6;
}
.draw-btn.ghost {
  flex: 0 0 auto;
  background: rgba(255, 255, 255, .1);
  color: #efe9ff;
  box-shadow: none;
  border: 1px solid rgba(255, 220, 150, .35);
}

.persona-msg {
  min-height: 28px;
  padding: 7px 12px;
  border-radius: 14px;
  font-size: 13px;
  margin-top: 10px;
}
.persona-msg.ok { color: #37723A; background: var(--sprout-soft); }
.persona-msg.hint { color: var(--honey-deep); background: var(--honey-soft); }
.persona-msg.error { color: var(--berry); background: var(--berry-soft); }

/* 卡槽 */
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
  margin-bottom: 12px;
}
.section-head strong {
  font-size: 14px;
}
.gallery-tabs {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: 999px;
  background: var(--line);
  flex: 0 0 auto;
}
.gallery-tabs button {
  padding: 4px 13px;
  border: none;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  background: transparent;
  color: var(--ink-soft);
  cursor: pointer;
  transition: background .18s ease, color .18s ease;
}
.gallery-tabs button.active {
  background: #fff;
  color: var(--honey-deep);
  box-shadow: 0 1px 4px rgba(0,0,0,.1);
}
.head-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}
.fold-btn {
  width: 28px;
  height: 28px;
  border-radius: 9px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,.9);
  color: var(--ink-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform .25s ease, background .18s ease;
}
.fold-btn:hover { background: var(--honey-soft); }
.fold-btn svg {
  width: 15px;
  height: 15px;
  stroke-width: 2.2;
  transition: transform .25s ease;
}
.fold-btn.folded svg {
  transform: rotate(-90deg);
}
/* 图鉴分页 */
.gallery-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-top: 14px;
}
.pager-btn {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,.92);
  color: var(--honey-deep);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform .15s ease, opacity .15s ease;
}
.pager-btn:hover:not(:disabled) { transform: translateY(-1px); }
.pager-btn:active:not(:disabled) { transform: scale(.92); }
.pager-btn:disabled { opacity: .4; cursor: not-allowed; }
.pager-btn svg {
  width: 15px;
  height: 15px;
  stroke-width: 2.4;
}
.pager-num {
  font-size: 12px;
  font-weight: 700;
  color: var(--ink-soft);
  font-variant-numeric: tabular-nums;
}
.slot-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
@media (max-width: 420px) {
  .slot-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.slot-cell-wrap { min-width: 0; }
.slot-cell {
  position: relative;
  aspect-ratio: 3 / 4.3;
  border-radius: 16px;
  cursor: pointer;
  overflow: hidden;
  transition: transform .18s ease, box-shadow .18s ease;
}
.slot-cell:hover { transform: translateY(-4px); box-shadow: 0 10px 24px rgba(0,0,0,.18); }
.slot-cell.injected {
  box-shadow: 0 0 0 2.5px rgba(255, 159, 69, .85), 0 8px 20px rgba(255, 159, 69, .28);
}
.slot-empty {
  border: 2px dashed var(--line);
  background: rgba(250, 246, 240, .6);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: var(--sub);
  cursor: default;
}
.slot-empty-num {
  font-size: 20px;
  font-weight: 700;
  color: rgba(0,0,0,.12);
}
.slot-empty small { font-size: 11px; }
.slot-front {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 12px 8px;
  color: #fff;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.28), 0 6px 14px rgba(0,0,0,.12);
}
.slot-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  font-size: 9px;
  font-weight: 800;
  padding: 2px 9px;
  border-radius: 999px;
  background: rgba(0,0,0,.32);
  color: rgba(255,255,255,.85);
  letter-spacing: .06em;
}
.slot-badge.on {
  background: linear-gradient(135deg, #ffd76b, #ff9f45);
  color: #5b3a00;
}
.classic-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  background: linear-gradient(135deg, #ffd76b, #f0a94e);
  color: #5b3a00;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: .06em;
  box-shadow: 0 2px 6px rgba(240, 169, 78, .4);
  z-index: 2;
}
.slot-avatar {
  width: 46%;
  aspect-ratio: 1;
  border-radius: 50%;
  object-fit: cover;
  border: 2.5px solid rgba(255,255,255,.8);
  box-shadow: 0 4px 14px rgba(0,0,0,.3);
}
.slot-avatar-fallback {
  width: 46%;
  aspect-ratio: 1;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 800;
  color: #fff;
  border: 2.5px solid rgba(255,255,255,.8);
  box-shadow: 0 4px 14px rgba(0,0,0,.3);
}
.slot-name {
  max-width: 92%;
  font-size: 13px;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-shadow: 0 1px 4px rgba(0,0,0,.35);
}
.slot-actions {
  display: flex;
  gap: 5px;
  margin-top: 3px;
}
.slot-act {
  position: relative;
  width: 28px;
  height: 28px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: rgba(255,255,255,.94);
  color: #5a4632;
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(0,0,0,.2);
  transition: transform .14s ease, background .14s ease, color .14s ease;
}
.slot-act:hover { transform: translateY(-2px) scale(1.06); }
.slot-act:active { transform: scale(.9); }
.slot-act svg {
  width: 14px;
  height: 14px;
  stroke-width: 2.2;
}
.slot-act.primary {
  background: linear-gradient(135deg, #ffd76b, #ff9f45);
  color: #5b3a00;
}
.slot-act.danger { color: #c0392b; }
.slot-act.danger.armed {
  background: #c0392b;
  color: #fff;
  animation: slot-arm-pulse .5s ease;
}
@keyframes slot-arm-pulse {
  0% { transform: scale(1); }
  40% { transform: scale(1.25); }
  100% { transform: scale(1); }
}
/* hover tooltip */
.slot-act .tip {
  position: absolute;
  bottom: calc(100% + 7px);
  left: 50%;
  transform: translateX(-50%) translateY(3px);
  padding: 4px 9px;
  border-radius: 7px;
  background: rgba(28, 22, 48, .94);
  color: #fff;
  font-size: 10.5px;
  font-weight: 600;
  white-space: nowrap;
  letter-spacing: .02em;
  opacity: 0;
  pointer-events: none;
  transition: opacity .15s ease, transform .15s ease;
  z-index: 20;
}
.slot-act .tip::after {
  content: "";
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 4px solid transparent;
  border-top-color: rgba(28, 22, 48, .94);
}
.slot-act:hover .tip {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}
.deck-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: auto;
}
.deck-tags span {
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(255, 215, 107, .16);
  border: 1px solid rgba(255, 215, 107, .35);
  color: #ffe2a8;
  font-size: 9px;
}

/* 灵魂图鉴 */
.deck-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
@media (max-width: 420px) {
  .deck-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.deck-card {
  perspective: 800px;
  height: 190px;
  cursor: pointer;
}
/* 未拥有的灵魂：暗色未点亮，只显示卡面 */
.deck-card.dim {
  filter: grayscale(0.55) brightness(0.82);
  opacity: 0.6;
  transition: filter 0.25s, opacity 0.25s;
}
.deck-card.dim:hover {
  filter: grayscale(0.3) brightness(0.92);
  opacity: 0.85;
}
.deck-card.dim .deck-status {
  color: #e8e0d0;
}
.deck-inner {
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  transition: transform .6s cubic-bezier(.4, .2, .2, 1);
}
.deck-card:hover .deck-inner,
.deck-card:focus-visible .deck-inner {
  transform: rotateY(180deg);
}
.deck-face {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 12px 8px;
}
.deck-front {
  color: #fff;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.3), var(--shadow-sm);
}
.deck-avatar {
  width: 46%;
  aspect-ratio: 1;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid rgba(255,255,255,.75);
  box-shadow: 0 4px 12px rgba(0,0,0,.22);
}
.deck-avatar-fallback {
  width: 46%;
  aspect-ratio: 1;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 800;
  color: #fff;
  border: 2px solid rgba(255,255,255,.75);
  box-shadow: 0 4px 12px rgba(0,0,0,.22);
}
.deck-name {
  max-width: 94%;
  font-size: 12.5px;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-shadow: 0 1px 4px rgba(0,0,0,.3);
}
.deck-status {
  font-size: 9.5px;
  color: rgba(255,255,255,.92);
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(0,0,0,.28);
}
/* 已点亮：金色徽标 + 卡片金色光晕 */
.deck-status.owned {
  background: linear-gradient(135deg, #ffd76b, #e8a93d);
  color: #5b3a00;
}
.deck-card:not(.dim) {
  box-shadow: 0 3px 12px rgba(255, 200, 90, .28);
}
.deck-status.active {
  background: linear-gradient(135deg, #ffd76b, #ff9f45);
  color: #5b3a00;
}
.deck-back {
  transform: rotateY(180deg);
  align-items: flex-start;
  justify-content: flex-start;
  text-align: left;
  gap: 8px;
  padding: 13px 11px;
  border: 1px solid rgba(255, 220, 150, .4);
  background: linear-gradient(160deg, #3a2f68, #241d4a 60%, #1d1739);
  color: #efe9ff;
  box-shadow: 0 10px 22px rgba(43, 35, 80, .3);
}
.deck-back-name {
  font-size: 13.5px;
  font-weight: 800;
  color: #ffd76b;
}
.deck-desc {
  margin: 0;
  font-size: 11.5px;
  line-height: 1.55;
  color: #ddd4ff;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
}
.deck-tone {
  font-size: 10px;
  color: rgba(255, 226, 170, .75);
}

/* ============ 命运抽卡弹窗 ============ */
.gacha-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(12, 8, 26, .6);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  animation: gacha-overlay-in .25s ease;
  overflow-y: auto;
}
@keyframes gacha-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
.gacha-modal {
  position: relative;
  width: 100%;
  max-width: 380px;
  border-radius: 24px;
  padding: 18px 16px 16px;
  overflow: hidden;
  background: linear-gradient(160deg, #2b2350 0%, #1c1638 55%, #171233 100%);
  box-shadow: 0 24px 60px rgba(0, 0, 0, .5), 0 0 0 1px rgba(255, 220, 150, .16);
  animation: gacha-in .4s cubic-bezier(.34, 1.3, .64, 1);
}
@keyframes gacha-in {
  from { opacity: 0; transform: scale(.88) translateY(18px); }
  to { opacity: 1; transform: none; }
}
.gacha-glow {
  position: absolute;
  inset: -40% -20%;
  background:
    radial-gradient(circle at 20% 0%, rgba(255, 201, 101, .18), transparent 45%),
    radial-gradient(circle at 85% 100%, rgba(142, 111, 255, .22), transparent 50%);
  pointer-events: none;
}
.gacha-head {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
}
.gacha-label {
  color: #f5c76b;
  letter-spacing: .12em;
  font-weight: 800;
}
.gacha-hint {
  display: block;
  margin-top: 3px;
  color: #efe9ff;
  font-size: 14px;
  line-height: 1.4;
}
.gacha-close {
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 1px solid rgba(255, 220, 150, .3);
  background: rgba(255, 255, 255, .06);
  color: rgba(239, 233, 255, .8);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background .18s ease, transform .18s ease;
}
.gacha-close:hover { background: rgba(255, 255, 255, .14); }
.gacha-close:active { transform: scale(.9); }
.gacha-close svg {
  width: 15px;
  height: 15px;
  stroke-width: 2.4;
}
.gacha-stage {
  position: relative;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px 8px;
  perspective: 1000px;
  min-height: 208px;
  padding: 2px 0;
}
.gacha-card {
  position: relative;
  aspect-ratio: 3 / 4.2;
  cursor: default;
  border-radius: 12px;
  transition: transform .55s cubic-bezier(.34, 1.2, .64, 1), opacity .5s ease;
  pointer-events: none;
}
.gacha-card.picked { z-index: 5; }
@keyframes gacha-twinkle {
  0%, 100% { opacity: .45; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.08); }
}
.gacha-modal.phase-picking .gacha-card {
  cursor: pointer;
  pointer-events: auto;
}
.gacha-modal.phase-picking .gacha-card:hover {
  transform: translateY(-8px) scale(1.05);
  filter: drop-shadow(0 4px 14px rgba(255, 201, 101, .35));
}
.gacha-modal.phase-picking .gacha-card:active {
  transform: scale(.96);
}
/* TransitionGroup 洗牌换位：卡片平滑滑到新位置 */
.shuffle-move {
  transition: transform .42s cubic-bezier(.34, 1.2, .64, 1);
}
.gacha-modal.phase-shuffling .gacha-card {
  transition: transform .42s cubic-bezier(.34, 1.2, .64, 1), opacity .4s ease;
}
/* 揭示阶段：其他卡完全淡出，聚焦选中卡 */
.gacha-modal.phase-revealing .gacha-card:not(.picked),
.gacha-modal.phase-done .gacha-card:not(.picked) {
  opacity: 0;
  transform: scale(.8) translateY(14px);
  pointer-events: none;
  transition: transform .45s ease, opacity .4s ease;
}
/* 揭示四步：①锁定 ②升卡 ③光柱 ④翻面（--lift 由 JS 动态计算，选中卡统一对齐舞台中央） */
.gacha-modal.phase-revealing .gacha-card.picked,
.gacha-modal.phase-done .gacha-card.picked {
  transition: transform .38s cubic-bezier(.34, 1.4, .64, 1), filter .4s ease;
}
.gacha-card.picked.rs0 { transform: scale(.94); }
.gacha-card.picked.rs1 { transform: translate(calc(var(--lift-x, 0px)), calc(var(--lift-y, -52px) - 24px)) scale(1.5); z-index: 8; }
.gacha-card.picked.rs2 { transform: translate(calc(var(--lift-x, 0px)), calc(var(--lift-y, -52px) - 24px)) scale(1.5); z-index: 8; filter: drop-shadow(0 0 22px rgba(255, 201, 101, .6)); }
.gacha-card.picked.rs3 { transform: translate(calc(var(--lift-x, 0px)), calc(var(--lift-y, -44px) - 24px)) scale(1.32); z-index: 8; filter: drop-shadow(0 0 22px rgba(255, 201, 101, .6)); }
.gacha-card.picked.rs4 { transform: translate(calc(var(--lift-x, 0px)), calc(var(--lift-y, -34px) - 24px)) scale(1.26); z-index: 8; filter: drop-shadow(0 0 20px rgba(255, 201, 101, .5)); }

/* 揭示时舞台聚焦：暗角让中央卡面更突出 */
.gacha-modal.phase-revealing .gacha-stage::after,
.gacha-modal.phase-done .gacha-stage::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: 14px;
  background: radial-gradient(circle at 50% 50%, transparent 20%, rgba(10, 8, 20, .6) 78%);
  pointer-events: none;
  z-index: 4;
  transition: opacity .4s ease;
}

/* 光柱（卡色联动，从卡后上下延伸） */
.gacha-beam {
  position: absolute;
  left: 50%;
  bottom: -18%;
  width: 56%;
  height: 170%;
  transform: translateX(-50%);
  border-radius: 50%;
  opacity: 0;
  pointer-events: none;
  animation: beam-in .5s ease .05s forwards, beam-pulse 1.4s ease-in-out .5s infinite;
  z-index: 0;
}
@keyframes beam-in {
  from { opacity: 0; transform: translateX(-50%) scaleY(.3); }
  to { opacity: 1; transform: translateX(-50%) scaleY(1); }
}
@keyframes beam-pulse {
  0%, 100% { opacity: .85; }
  50% { opacity: .55; }
}
.beam-dot {
  position: absolute;
  left: 50%;
  bottom: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 0 10px 2px currentColor;
  transform: translateX(-50%);
  animation: beam-rise 1.1s linear infinite;
  opacity: 0;
}
.beam-dot.d1 { animation-delay: 0s; }
.beam-dot.d2 { animation-delay: .35s; }
.beam-dot.d3 { animation-delay: .7s; }
@keyframes beam-rise {
  0% { bottom: 4%; opacity: 0; }
  15% { opacity: .9; }
  100% { bottom: 92%; opacity: 0; }
}

/* 光圈（④ 翻面时扩散） */
.gacha-ring {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 100%;
  aspect-ratio: 1;
  border: 2px solid;
  border-radius: 50%;
  transform: translate(-50%, -50%) scale(.35);
  opacity: 0;
  pointer-events: none;
  animation: ring-out .8s ease-out .1s forwards;
  z-index: 6;
}
@keyframes ring-out {
  0% { transform: translate(-50%, -50%) scale(.35); opacity: .9; }
  100% { transform: translate(-50%, -50%) scale(1.7); opacity: 0; }
}

/* 星芒爆开（卡色联动） */
.gacha-burst {
  position: absolute;
  left: 50%;
  top: 50%;
  font-size: 13px;
  transform: translate(-50%, -50%);
  opacity: 0;
  pointer-events: none;
  text-shadow: 0 0 8px currentColor;
  animation: burst-fly .7s ease-out .1s forwards;
  z-index: 7;
}
@keyframes burst-fly {
  0% { transform: translate(-50%, -50%) scale(.4) rotate(0deg); opacity: 1; }
  100% { transform: translate(calc(-50% + var(--bx)), calc(-50% + var(--by))) scale(1) rotate(90deg); opacity: 0; }
}
.gacha-inner {
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  transition: transform .8s cubic-bezier(.3, .1, .2, 1);
}
.gacha-inner.flipped { transform: rotateY(180deg); }
.gacha-face {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  border-radius: 12px;
  overflow: hidden;
}
.gacha-back {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: linear-gradient(150deg, #3a2f68, #241d4a 60%, #1d1739);
  border: 1px solid rgba(255, 220, 150, .28);
  box-shadow: inset 0 0 22px rgba(0, 0, 0, .45), 0 6px 14px rgba(0, 0, 0, .35);
}
.gacha-back::before {
  content: "";
  position: absolute;
  inset: 6px;
  border-radius: 8px;
  border: 1px solid rgba(255, 220, 150, .18);
}
.gacha-back-core {
  width: 34%;
  aspect-ratio: 1;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, rgba(255, 236, 190, .95), rgba(214, 158, 62, .9) 60%, rgba(140, 96, 32, .9));
  box-shadow: 0 0 16px rgba(255, 201, 101, .55);
  animation: gacha-pulse 2.2s ease-in-out infinite;
}
@keyframes gacha-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.09); opacity: .85; }
}
.gacha-back small {
  color: rgba(255, 226, 170, .72);
  font-size: 10px;
  letter-spacing: .22em;
}
.gacha-back-star {
  position: absolute;
  color: rgba(255, 230, 170, .5);
  font-size: 12px;
  animation: gacha-twinkle 2.6s ease-in-out infinite;
}
.gacha-back-star.s1 { top: 12%; left: 16%; }
.gacha-back-star.s2 { top: 20%; right: 14%; animation-delay: .6s; font-size: 9px; }
.gacha-back-star.s3 { bottom: 18%; left: 20%; animation-delay: 1.1s; font-size: 9px; }
.gacha-result {
  transform: rotateY(180deg);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 8px 4px;
  border: 1px solid rgba(255, 220, 150, .5);
  color: #fff;
  box-shadow: inset 0 0 14px rgba(255, 255, 255, .08), 0 8px 20px rgba(0, 0, 0, .3);
}
.gacha-result-img {
  width: 60%;
  aspect-ratio: 1;
  border-radius: 50%;
  object-fit: cover;
  border: 2.5px solid rgba(255, 255, 255, .7);
  box-shadow: 0 5px 16px rgba(0, 0, 0, .35);
}
.gacha-result-fallback {
  width: 60%;
  aspect-ratio: 1;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30px;
  font-weight: 800;
  border: 2.5px solid rgba(255, 255, 255, .7);
  box-shadow: 0 5px 16px rgba(0, 0, 0, .35);
}
.gacha-result-name {
  margin-top: 6px;
  font-size: 15px;
  font-weight: 800;
  max-width: 92%;
  line-height: 1.3;
  text-align: center;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-all;
  text-shadow: 0 1px 6px rgba(0, 0, 0, .5);
}
.gacha-result-tone {
  font-size: 11px;
  opacity: .92;
  max-width: 96%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gacha-new-badge {
  position: absolute;
  top: 7px;
  right: 7px;
  padding: 2px 8px;
  border-radius: 999px;
  background: linear-gradient(135deg, #ffd76b, #ff9f45);
  color: #5b3a00;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: .08em;
  animation: gacha-pop .5s cubic-bezier(.34, 1.8, .64, 1) .25s both;
  box-shadow: 0 3px 10px rgba(255, 159, 69, .5);
}
.gacha-unowned-badge {
  position: absolute;
  top: 7px;
  left: 7px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(30, 40, 60, .55);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .06em;
  backdrop-filter: blur(2px);
}
@keyframes gacha-pop {
  0% { transform: scale(0); }
  100% { transform: scale(1); }
}
/* 卡面内金色粒子：仅在翻面瞬间（rs3）播一次，不遮卡面 */
.gacha-spark {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #ffe9a8;
  opacity: 0;
  box-shadow: 0 0 8px 2px rgba(255, 224, 150, .8);
  animation: gacha-spark .8s ease-out forwards;
}
@keyframes gacha-spark {
  0% { transform: translate(0, 0) scale(.4); opacity: 0; }
  15% { opacity: 1; }
  100% { transform: translate(var(--sx), var(--sy)) scale(.9); opacity: 0; }
}
.gacha-cta {
  position: relative;
  display: flex;
  gap: 10px;
  margin-top: 14px;
  flex-wrap: wrap;
}
/* done 阶段按钮逐个滑入 */
.gacha-modal.phase-done .gacha-cta button {
  animation: cta-rise .4s cubic-bezier(.34, 1.4, .64, 1) both;
}
.gacha-modal.phase-done .gacha-cta button:nth-child(2) { animation-delay: .08s; }
.gacha-modal.phase-done .gacha-cta button:nth-child(3) { animation-delay: .16s; }
@keyframes cta-rise {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: none; }
}
/* done 卡面定格后轻微呼吸 */
.gacha-modal.phase-done .gacha-card.picked .gacha-result {
  animation: result-float 2.6s ease-in-out .3s infinite;
}
@keyframes result-float {
  0%, 100% { transform: rotateY(180deg) translateY(0); }
  50% { transform: rotateY(180deg) translateY(-5px); }
}
.gacha-cta .draw-btn { flex: 1; }
.gacha-cta .draw-btn.ghost { flex: 0 0 auto; }
.gacha-msg {
  position: relative;
  margin-top: 10px;
  padding: 7px 12px;
  border-radius: 12px;
  font-size: 13px;
  text-align: center;
}
.gacha-msg.ok { color: #7fd48a; background: rgba(95, 190, 99, .16); }
.gacha-msg.hint { color: #ffd76b; background: rgba(255, 201, 101, .14); }
.gacha-msg.error { color: #ff9d9d; background: rgba(255, 107, 107, .16); }

/* 替换模式 */
.replace-hint {
  width: 100%;
  color: #ffd76b;
  font-size: 12.5px;
  text-align: center;
  margin-bottom: 2px;
}
.replace-grid {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 8px 0 4px;
}
.replace-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 9px 4px;
  border-radius: 12px;
  border: 1px solid rgba(255, 220, 150, .3);
  background: rgba(255, 255, 255, .06);
  color: #efe9ff;
  cursor: pointer;
  transition: transform .15s ease, border-color .15s ease;
}
.replace-item:hover { transform: translateY(-2px); border-color: rgba(255, 220, 150, .7); }
.replace-item.active { border-color: #ffd76b; background: rgba(255, 215, 107, .14); }
/* 选中的待替换旧卡：高亮描边 + 勾选标记 */
.replace-item.selected {
  border-color: #ffd76b;
  box-shadow: 0 0 0 2px rgba(255, 215, 107, .55), 0 4px 12px rgba(255, 159, 69, .25);
  background: rgba(255, 215, 107, .2);
}
.replace-item.selected::after {
  content: '✓';
  position: absolute;
  top: 5px;
  right: 6px;
  width: 17px;
  height: 17px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ffd76b, #ff9f45);
  color: #5b3a00;
  font-size: 11px;
  font-weight: 900;
  line-height: 17px;
  text-align: center;
  box-shadow: 0 2px 6px rgba(255, 159, 69, .5);
}
.replace-cta {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-top: 10px;
  width: 100%;
}
/* 确认替换：主按钮占大头；取消：小尺寸次级按钮 */
.replace-cta .draw-btn.confirm-btn {
  flex: 1.5 1 0;
  min-width: 0;
  height: 44px;
}
.replace-cta .draw-btn.ghost {
  flex: 0 0 auto;
  width: auto;
  min-width: 0;
  padding: 0 18px;
  height: 44px;
  font-size: 13px;
}
.replace-avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  object-fit: cover;
  border: 1.5px solid rgba(255, 255, 255, .5);
}
.replace-fallback {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 800;
  color: #fff;
}
.replace-name {
  max-width: 96%;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.replace-item small {
  font-size: 9px;
  color: #ffd76b;
  min-height: 11px;
}

/* 灵魂详情 */
.detail-modal {
  position: relative;
  width: 100%;
  max-width: 400px;
  max-height: 82vh;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 24px 60px rgba(0, 0, 0, .35);
  animation: gacha-in .35s cubic-bezier(.34, 1.3, .64, 1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.detail-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--line);
}
.detail-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 22px;
  font-weight: 800;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0,0,0,.14);
}
.detail-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.detail-title {
  flex: 1;
  min-width: 0;
}
.detail-title b {
  display: block;
  font-size: 16px;
}
.detail-title small {
  display: block;
  font-size: 12px;
  color: var(--ink-soft);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-md {
  padding: 14px 16px 18px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.65;
  color: var(--ink);
}
.detail-md h1, .detail-md h2, .detail-md h3 {
  font-size: 14px;
  margin: 14px 0 6px;
  color: var(--honey-deep);
}
.detail-md h1:first-child, .detail-md h2:first-child { margin-top: 0; }
.detail-md ul, .detail-md ol {
  margin: 6px 0;
  padding-left: 18px;
}
.detail-md li { margin: 3px 0; }
.detail-md blockquote {
  margin: 8px 0;
  padding: 6px 10px;
  border-left: 3px solid var(--honey);
  background: var(--honey-soft);
  border-radius: 0 8px 8px 0;
  color: var(--ink-soft);
}
.detail-md code {
  background: var(--line);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
}
.detail-md hr { border: none; border-top: 1px solid var(--line); margin: 12px 0; }
.detail-md strong { font-weight: 700; }
</style>
