export const ADMIN_COMPANY_KNOWLEDGE_TYPES = Object.freeze([
  { key: 'policy', label: '公司制度', import_enabled: true, query_enabled: true },
  { key: 'faq', label: '常见问答', import_enabled: false, query_enabled: false },
  { key: 'history', label: '公司历史', import_enabled: false, query_enabled: false },
  { key: 'news', label: '近期动态', import_enabled: false, query_enabled: false },
  { key: 'department_knowledge', label: '部门知识', import_enabled: false, query_enabled: false },
])

export function mergeAdminCompanyKnowledgeTypes(serverTypes = []) {
  const serverByKey = new Map(serverTypes.map((item) => [item.key, item]))
  return ADMIN_COMPANY_KNOWLEDGE_TYPES.map((item) => ({ ...item, ...(serverByKey.get(item.key) || {}) }))
}
