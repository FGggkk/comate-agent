export const COMPANY_KNOWLEDGE_TYPES = Object.freeze([
  {
    key: 'policy',
    label: '公司制度',
    description: '查询已发布、已生效的公司制度。',
    icon: 'BookOpen',
    import_enabled: true,
    query_enabled: true,
    user_visible: true,
    required_metadata: ['version', 'effective_at'],
  },
  {
    key: 'faq',
    label: '常见问答',
    description: '沉淀公司常见问题与标准答复。',
    icon: 'CircleHelp',
    import_enabled: false,
    query_enabled: false,
    user_visible: false,
    required_metadata: [],
  },
  {
    key: 'history',
    label: '公司历史',
    description: '记录公司发展历程和关键节点。',
    icon: 'History',
    import_enabled: false,
    query_enabled: false,
    user_visible: false,
    required_metadata: [],
  },
  {
    key: 'news',
    label: '近期动态',
    description: '发布近期公告和公司动态。',
    icon: 'Newspaper',
    import_enabled: false,
    query_enabled: false,
    user_visible: false,
    required_metadata: ['published_at'],
  },
  {
    key: 'department_knowledge',
    label: '部门知识',
    description: '沉淀部门范围内的流程和资料。',
    icon: 'Building2',
    import_enabled: false,
    query_enabled: false,
    user_visible: false,
    required_metadata: ['department'],
  },
])

export const DEFAULT_COMPANY_KNOWLEDGE_TYPE = 'policy'

export function mergeCompanyKnowledgeTypes(serverTypes = []) {
  const serverByKey = new Map(serverTypes.map((item) => [item.key, item]))
  return COMPANY_KNOWLEDGE_TYPES.map((item) => ({ ...item, ...(serverByKey.get(item.key) || {}) }))
}

export function visibleCompanyKnowledgeTypes(types = COMPANY_KNOWLEDGE_TYPES) {
  return types.filter((item) => item.user_visible && item.query_enabled)
}
