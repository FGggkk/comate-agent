<template>
  <div class="scroll">
    <div class="page-title">记忆</div>

    <div v-if="!loaded" style="text-align:center;color:var(--sub);padding:20px 0;">加载中...</div>

    <template v-else>
      <!-- 三层卡片 -->
      <div class="mem-layers">
        <div class="mlayer g"><div class="mn">先验层</div><div class="md">系统已知信息</div><div class="mc">{{ countLayer('priors') }}<small> 条</small></div></div>
        <div class="mlayer o"><div class="mn">共建层</div><div class="md">你主动告诉我的</div><div class="mc">{{ countLayer('co_created') }}<small> 条</small></div></div>
        <div class="mlayer p"><div class="mn">默契层</div><div class="md">长期互动沉淀</div><div class="mc">{{ countLayer('tacit') }}<small> 条</small></div></div>
      </div>

      <!-- 记忆列表：先验层 -->
      <div class="page-label" style="margin-top:16px;">🧠 先验层</div>
      <div class="page-card" style="padding:10px 14px;">
        <div v-for="m in memoryStore.layers.priors" :key="m.id" class="mitem">
          <span class="mtype">先验</span>
          <span class="mtext">{{ m.summary }}</span>
        </div>
        <div v-if="memoryStore.layers.priors.length === 0" style="font-size:13px;color:var(--sub);padding:6px 0;">暂无先验记忆</div>
      </div>

      <!-- 记忆列表：共建层 -->
      <div class="page-label" style="margin-top:16px;">🤝 共建层</div>
      <div class="page-card" style="padding:10px 14px;">
        <div v-for="m in memoryStore.layers.co_created" :key="m.id" style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--line);">
          <span class="mtext" style="flex:1;font-size:14px;">{{ m.summary }}</span>
          <button v-if="!m.user_confirmed" @click="confirmMemory(m.id)" style="font-size:12px;color:var(--sprout);padding:4px 8px;">确认</button>
          <button @click="deleteMemory(m.id)" style="font-size:12px;color:var(--berry);padding:4px 8px;">删除</button>
        </div>
        <div v-if="memoryStore.layers.co_created.length === 0" style="font-size:13px;color:var(--sub);padding:6px 0;">暂无共建记忆</div>
      </div>

      <!-- 记忆列表：默契层 -->
      <div class="page-label" style="margin-top:16px;">💭 默契层</div>
      <div class="page-card" style="padding:10px 14px;">
        <div v-for="m in memoryStore.layers.tacit" :key="m.id" class="mitem">
          <span class="mtype warn">推断</span>
          <span class="mtext">{{ m.summary }}</span>
        </div>
        <div v-if="memoryStore.layers.tacit.length === 0" style="font-size:13px;color:var(--sub);padding:6px 0;">暂无默契记忆</div>
      </div>

      <!-- 禁区 -->
      <div class="page-label" style="margin-top:16px;">🚫 禁区话题</div>
      <div class="page-card" style="padding:10px 14px;">
        <div v-for="f in memoryStore.forbiddenTopics" :key="f.id" style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--line);">
          <span style="font-size:14px;">{{ f.topic }}</span>
          <button @click="removeForbidden(f.id)" style="font-size:12px;color:var(--berry);padding:4px 8px;">解除</button>
        </div>
        <div style="display:flex;gap:8px;margin-top:8px;">
          <input v-model="newForbidden" placeholder="添加禁区话题..." class="form-input" style="flex:1;" />
          <button @click="addForbidden" class="btn-primary" style="width:auto;padding:10px 16px;font-size:13px;">添加</button>
        </div>
      </div>

      <!-- 未完待续 -->
      <div class="page-label" style="margin-top:16px;">📌 未完待续</div>
      <div class="page-card" style="padding:10px 14px;">
        <div v-for="a in memoryStore.pendingAnchors" :key="a.id" style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--line);">
          <span style="font-size:14px;">{{ a.topic }}</span>
          <button @click="fulfillAnchor(a.id)" style="font-size:12px;color:var(--sprout);padding:4px 8px;">已完成</button>
        </div>
        <div v-if="memoryStore.pendingAnchors.length === 0" style="font-size:13px;color:var(--sub);padding:6px 0;">暂无待续话题</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMemoryStore } from '../stores/memory'
import { apiGetMemories, apiUpdateMemory, apiDeleteMemory, apiAddForbidden, apiRemoveForbidden, apiFulfillAnchor } from '../api/index'

const memoryStore = useMemoryStore()
const loaded = ref(false)
const newForbidden = ref('')

function countLayer(layer) { return (memoryStore.layers[layer] || []).length }

onMounted(async () => {
  const data = await apiGetMemories()
  memoryStore.load(data)
  loaded.value = true
})

async function addForbidden() {
  if (!newForbidden.value.trim()) return
  await apiAddForbidden(newForbidden.value, '')
  newForbidden.value = ''
  memoryStore.load(await apiGetMemories())
}

async function removeForbidden(id) {
  await apiRemoveForbidden(id)
  memoryStore.load(await apiGetMemories())
}

async function confirmMemory(id) {
  await apiUpdateMemory(id, { user_confirmed: true })
  memoryStore.load(await apiGetMemories())
}

async function deleteMemory(id) {
  await apiDeleteMemory(id)
  memoryStore.load(await apiGetMemories())
}

async function fulfillAnchor(id) {
  await apiFulfillAnchor(id)
  memoryStore.load(await apiGetMemories())
}
</script>
