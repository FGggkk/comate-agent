<template>
  <div :class="role === 'user' ? 'msg-user' : 'msg-bot'">
    <div v-if="role === 'agent'" :class="['companion', squished ? 'squish' : 'bob']" style="--s:28px;flex-shrink:0;" @click="squishIt">
      <div class="companion-body">
        <span class="companion-eye l"></span>
        <span class="companion-eye r"></span>
        <span class="companion-cheek l"></span>
        <span class="companion-cheek r"></span>
        <span class="companion-mouth"></span>
      </div>
      <div class="companion-sprout"><span class="companion-sprout-r"></span></div>
    </div>
    <div :class="role === 'user' ? 'bubble-user' : 'bubble-bot'">{{ content }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
defineProps({ role: String, content: String })
const squished = ref(false)
function squishIt() {
  squished.value = true
  setTimeout(() => { squished.value = false }, 450)
}
</script>
