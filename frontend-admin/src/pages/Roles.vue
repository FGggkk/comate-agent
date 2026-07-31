<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:flex-end;">
      <div>
        <div class="page-title">角色管理</div>
        <div class="page-sub">自建角色，或从外部导入 SOUL.md 角色设定</div>
      </div>
      <div style="display:flex;gap:8px;">
        <button class="btn-ghost" @click="openImport">⬇ 导入角色</button>
        <button class="btn-gold" @click="openCreate">＋ 新建角色</button>
      </div>
    </div>

    <!-- 筛选 -->
    <div style="display:flex;gap:6px;margin:18px 0 12px;">
      <button v-for="t in tabs" :key="t.key" :class="['tab-filter', status === t.key ? 'active' : '']" @click="switchStatus(t.key)">
        {{ t.label }}
      </button>
    </div>

    <!-- 角色网格 -->
    <div class="soul-grid">
      <div v-for="s in items" :key="s.id" class="soul-card" :class="{ off: s.status !== 'active' }">
        <div class="soul-orb" :style="s.avatar_image ? { backgroundImage: `url(${s.avatar_image})`, backgroundSize: 'cover', backgroundPosition: 'center' } : { background: orbGrad(s) }">
          <span v-if="!s.avatar_image">{{ s.name[0] }}</span>
        </div>
        <div class="soul-info">
          <div style="display:flex;align-items:center;gap:6px;">
            <b>{{ s.name }}</b>
            <span class="badge" :class="s.status === 'active' ? 'badge-moss' : 'badge-berry'">{{ s.status === 'active' ? '上架' : '下架' }}</span>
          </div>
          <div style="font-size:12px;color:var(--ink-soft);margin-top:2px;">{{ s.description || '—' }}</div>
          <div style="display:flex;gap:4px;margin-top:6px;flex-wrap:wrap;">
            <span v-for="tag in (s.tags || []).slice(0, 3)" :key="tag" class="soul-tag">{{ tag }}</span>
          </div>
          <div style="font-size:11px;color:var(--ink-soft);margin-top:6px;">
            {{ sourceLabel(s.source) }} · 排序 {{ s.sort_order }}
          </div>
        </div>
        <div class="soul-actions">
          <button class="row-btn" @click="openEdit(s)">编辑</button>
          <button v-if="s.status === 'active'" class="row-btn danger" @click="toggleStatus(s, 'inactive')">下架</button>
          <button v-else class="row-btn moss" @click="toggleStatus(s, 'active')">上架</button>
        </div>
      </div>
      <div v-if="!items.length" class="soul-empty">暂无角色</div>
    </div>

    <!-- 分页 -->
    <div v-if="total > 0" style="display:flex;justify-content:flex-end;gap:8px;margin-top:14px;align-items:center;">
      <span class="num" style="font-size:12px;color:var(--ink-soft);">共 {{ total }} 条</span>
      <button class="btn-ghost" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
      <span class="num">{{ page }}</span>
      <button class="btn-ghost" :disabled="page * size >= total" @click="goPage(page + 1)">下一页</button>
    </div>

    <!-- 创建/编辑弹窗 -->
    <div v-if="editor" class="modal-mask" @click.self="editor = null">
      <div class="modal wide">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
          <b>{{ editor.id ? '编辑角色' : '新建角色' }}</b>
          <button class="modal-close" @click="editor = null">×</button>
        </div>
        <div style="display:flex;gap:12px;">
          <div class="field" style="flex:2;">
            <label>名称 *</label>
            <input v-model="editor.name" class="set-input" placeholder="角色名称" />
          </div>
          <div class="field" style="flex:1;">
            <label>主题色</label>
            <input v-model="editor.color" type="color" class="color-input" />
          </div>
        </div>
        <div class="field">
          <label>简介</label>
          <input v-model="editor.description" class="set-input" placeholder="一句话介绍角色" />
        </div>
        <div class="img-row">
          <div class="field" style="flex:1;">
            <label>角色头像图</label>
            <div class="img-upload" @click="pickImage('avatar')">
              <img v-if="editor.avatar_image" :src="editor.avatar_image" />
              <span v-else>＋ 上传头像</span>
            </div>
          </div>
          <div class="field" style="flex:1;">
            <label>卡面图</label>
            <div class="img-upload" @click="pickImage('card')">
              <img v-if="editor.card_image" :src="editor.card_image" />
              <span v-else>＋ 上传卡面</span>
            </div>
          </div>
        </div>
        <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onFilePicked" />
        <div class="field">
          <label>标签（逗号分隔）</label>
          <input v-model="editor.tagsText" class="set-input" placeholder="温柔, 陪伴, 高冷" />
        </div>
        <div class="field">
          <label>角色设定（SOUL.md）*</label>
          <textarea v-model="editor.soul_markdown" class="set-input md-input" rows="10" placeholder="# 角色名&#10;&#10;你是……"></textarea>
        </div>
        <button class="btn-gold" style="width:100%;" @click="saveEditor">{{ editor.id ? '保存修改' : '创建角色' }}</button>
      </div>
    </div>

    <!-- 导入弹窗 -->
    <div v-if="importOpen" class="modal-mask" @click.self="importOpen = false">
      <div class="modal wide">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
          <b>导入角色（SOUL.md）</b>
          <button class="modal-close" @click="importOpen = false">×</button>
        </div>
        <div style="font-size:12px;color:var(--ink-soft);margin-bottom:10px;">
          粘贴带 frontmatter 的角色设定文本（可从 skillhub 等导出），支持 name / slug / description / color / tags：
          <pre style="background:var(--bg);padding:10px;border-radius:6px;margin-top:6px;font-size:11px;">---
name: 冷面男神
color: #5B7FA6
tags: [高冷, 细心]
---
# 冷面男神
你是……</pre>
        </div>
        <div class="field">
          <textarea v-model="importText" class="set-input md-input" rows="12" placeholder="粘贴 SOUL.md 内容…"></textarea>
        </div>
        <button class="btn-gold" style="width:100%;" :disabled="!importText.trim()" @click="doImport">导入</button>
        <p v-if="importMsg" style="font-size:12px;color:var(--moss);margin-top:8px;">{{ importMsg }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiAdminSouls, apiAdminCreateSoul, apiAdminUpdateSoul, apiAdminSoulStatus, apiAdminImportSoul, apiAdminSoulsUpload } from '../api'

const tabs = [
  { key: 'all', label: '全部' },
  { key: 'active', label: '上架' },
  { key: 'inactive', label: '下架' },
]

const status = ref('all')
const items = ref([])
const total = ref(0)
const page = ref(1)
const size = 20

const editor = ref(null)
const importOpen = ref(false)
const importText = ref('')
const importMsg = ref('')

const orbPalette = ['#FF9F7A', '#5FBE63', '#5FB0E8', '#FF6F91', '#FF9F45', '#9B6FD8', '#5B7FA6']
const orbGrad = (s) => {
  const c = s.color || orbPalette[(s.name.length + s.slug.length) % orbPalette.length]
  return `radial-gradient(circle at 30% 30%, ${c}, ${c}88)`
}
const sourceLabel = (src) => ({ builtin: '内置', custom: '自建', imported: '导入' }[src] || src)

async function load() {
  const res = await apiAdminSouls(status.value, page.value)
  if (res.success) {
    items.value = res.data.items
    total.value = res.data.total
  }
}
function switchStatus(k) { status.value = k; page.value = 1; load() }
function goPage(p) { page.value = p; load() }

function openCreate() {
  editor.value = { id: null, name: '', description: '', color: '#C99A2E', tagsText: '', soul_markdown: '', card_image: '', avatar_image: '' }
}
function openEdit(s) {
  editor.value = { id: s.id, name: s.name, description: s.description, color: s.color || '#C99A2E', tagsText: (s.tags || []).join(', '), soul_markdown: s.soul_markdown, card_image: s.card_image || '', avatar_image: s.avatar_image || '' }
}

const fileInput = ref(null)
let uploadTarget = 'avatar'

function pickImage(target) {
  uploadTarget = target
  fileInput.value?.click()
}

async function onFilePicked(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  const res = await apiAdminSoulsUpload(file)
  if (res.success) {
    if (uploadTarget === 'avatar') editor.value.avatar_image = res.url
    else editor.value.card_image = res.url
  }
}

async function saveEditor() {
  if (!editor.value.name.trim() || !editor.value.soul_markdown.trim()) return
  const tags = editor.value.tagsText.split(',').map((t) => t.trim()).filter(Boolean)
  if (editor.value.id) {
    const res = await apiAdminUpdateSoul(editor.value.id, {
      name: editor.value.name, description: editor.value.description, color: editor.value.color, tags, soul_markdown: editor.value.soul_markdown,
      card_image: editor.value.card_image || null, avatar_image: editor.value.avatar_image || null,
    })
    if (res.success) { editor.value = null; load() }
  } else {
    const res = await apiAdminCreateSoul({
      name: editor.value.name, description: editor.value.description, color: editor.value.color, tags, soul_markdown: editor.value.soul_markdown,
      card_image: editor.value.card_image || null, avatar_image: editor.value.avatar_image || null,
    })
    if (res.success) { editor.value = null; load() }
  }
}

async function toggleStatus(s, st) {
  const res = await apiAdminSoulStatus(s.id, st)
  if (res.success) load()
}

function openImport() { importOpen.value = true; importText.value = ''; importMsg.value = '' }
async function doImport() {
  const res = await apiAdminImportSoul(importText.value)
  if (res.success) {
    importMsg.value = res.message
    setTimeout(() => { importOpen.value = false; load() }, 800)
  } else {
    importMsg.value = res.message
  }
}

onMounted(load)
</script>

<style scoped>
.tab-filter {
  padding: 6px 16px; border-radius: 6px; border: 1px solid var(--line);
  background: transparent; font-size: 13px; color: var(--ink-soft); transition: all .15s;
}
.tab-filter:hover { color: var(--ink); border-color: var(--gold); }
.tab-filter.active { background: var(--gold-soft); border-color: var(--gold); color: #8A6A1C; font-weight: 600; }

.soul-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; margin-top: 14px; }
.soul-card {
  display: flex; gap: 12px; padding: 14px;
  background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
  align-items: flex-start; transition: all .2s;
}
.soul-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,.06); transform: translateY(-1px); }
.soul-card.off { opacity: .55; }
.soul-orb {
  width: 46px; height: 46px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 18px; font-weight: 700;
}
.soul-info { flex: 1; min-width: 0; }
.soul-tag {
  padding: 1px 8px; border-radius: 100px;
  background: var(--bg); border: 1px solid var(--line);
  font-size: 11px; color: var(--ink-soft);
}
.soul-actions { display: flex; flex-direction: column; gap: 4px; }
.soul-empty { grid-column: 1/-1; text-align: center; color: var(--ink-soft); padding: 40px 0; }

.row-btn {
  background: none; border: 1px solid var(--line); border-radius: 4px;
  font-size: 12px; color: var(--ink-soft); padding: 3px 10px;
}
.row-btn:hover { border-color: var(--gold); color: var(--ink); }
.row-btn.danger:hover { border-color: var(--berry); color: var(--berry); }
.row-btn.moss:hover { border-color: var(--moss); color: var(--moss); }

.modal-mask {
  position: fixed; inset: 0; background: rgba(20, 32, 26, .45);
  display: flex; align-items: center; justify-content: center; z-index: 50;
}
.modal { width: 440px; max-height: 85vh; overflow-y: auto; background: var(--bg); border-radius: 12px; padding: 24px; }
.modal.wide { width: 560px; }
.modal-close { background: none; border: none; font-size: 22px; color: var(--ink-soft); cursor: pointer; }

.field { margin-bottom: 12px; }
.field label { display: block; font-size: 12px; color: var(--ink-soft); margin-bottom: 6px; }
.set-input {
  width: 100%; padding: 9px 12px; border: 1px solid var(--line); border-radius: 6px;
  background: var(--card); font-size: 13px; outline: none;
}
.set-input:focus { border-color: var(--gold); }
.md-input { resize: vertical; font-family: 'SFMono-Regular', Consolas, monospace; font-size: 12px; line-height: 1.6; }
.color-input { width: 56px; height: 36px; padding: 2px; border: 1px solid var(--line); border-radius: 6px; background: var(--card); cursor: pointer; }

.img-row { display: flex; gap: 12px; }
.img-upload {
  height: 90px;
  border: 1.5px dashed var(--line);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; overflow: hidden;
  color: var(--ink-soft); font-size: 13px;
  background: var(--card);
  transition: border-color .15s;
}
.img-upload:hover { border-color: var(--gold); }
.img-upload img { width: 100%; height: 100%; object-fit: cover; }
</style>
