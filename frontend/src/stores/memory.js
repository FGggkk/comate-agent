import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMemoryStore = defineStore('memory', () => {
  const layers = ref({ priors: [], co_created: [], tacit: [] })
  const forbiddenTopics = ref([])
  const pendingAnchors = ref([])

  function load(data) {
    layers.value = data.layers || { priors: [], co_created: [], tacit: [] }
    forbiddenTopics.value = data.forbidden_topics || []
    pendingAnchors.value = data.pending_anchors || []
  }

  return { layers, forbiddenTopics, pendingAnchors, load }
})
