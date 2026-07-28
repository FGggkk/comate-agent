import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMemoryStore = defineStore('memory', () => {
  const layers = ref({ priors: [], co_created: [], tacit: [] })
  const tacitProfile = ref({})
  const forbiddenTopics = ref([])
  const pendingAnchors = ref([])

  function load(data) {
    layers.value = data.layers || { priors: [], co_created: [], tacit: [] }
    tacitProfile.value = data.tacit_profile || {}
    forbiddenTopics.value = data.forbidden_topics || []
    pendingAnchors.value = data.pending_anchors || []
  }

  return { layers, tacitProfile, forbiddenTopics, pendingAnchors, load }
})
