import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMemoryStore = defineStore('memory', () => {
  const layers = ref({ priors: [], co_created: [], tacit: [] })
  const tacitProfile = ref({})
  const forbiddenTopics = ref([])

  function load(data) {
    layers.value = data.layers || { priors: [], co_created: [], tacit: [] }
    tacitProfile.value = data.tacit_profile || {}
    forbiddenTopics.value = data.forbidden_topics || []
  }

  return { layers, tacitProfile, forbiddenTopics, load }
})
