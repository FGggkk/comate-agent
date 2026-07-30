import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useMemoryStore = defineStore('memory', () => {
  const layers = ref({ priors: [], co_created: [], tacit: [] })
  const tacitProfile = ref({})
  const forbiddenTopics = ref([])
  const documents = ref([])
  const documentRoot = ref('')

  function load(data) {
    layers.value = data.layers || { priors: [], co_created: [], tacit: [] }
    tacitProfile.value = data.tacit_profile || {}
    forbiddenTopics.value = data.forbidden_topics || []
  }

  function loadDocuments(data) {
    documents.value = data?.documents || []
    documentRoot.value = data?.root || ''
  }

  return { layers, tacitProfile, forbiddenTopics, documents, documentRoot, load, loadDocuments }
})
