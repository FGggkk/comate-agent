# 伴行agent v1 — Plan

## 架构概览

```
┌─────────────────────────────────────────┐
│             前端 (Vue 3 + Vite)          │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│  │ 聊聊  │ │ 记忆  │ │ 面试  │ │ 设置  │ ← TabBar
│  └──┬───┘ └──────┘ └──────┘ └──────┘  │
│     │                                    │
│  ┌──▼─────────────────────────────────┐ │
│  │         SSE Stream Handler          │ │
│  │  "思考中"→记忆卡→文字流→快捷按钮    │ │
│  └────────────────────────────────────┘ │
└────────────────┬────────────────────────┘
                 │ REST + SSE
                 ▼
┌─────────────────────────────────────────┐
│             后端 (FastAPI)               │
│  ┌─────────┐  ┌──────────┐              │
│  │ 路由层   │  │ 中间件    │              │
│  │ (REST+)  │  │ (安全/   │              │
│  │  SSE    │  │ 日志/    │              │
│  └────┬────┘  │ Trace)   │              │
│       │       └──────────┘              │
│  ┌────▼──────────────────────────────┐  │
│  │         Service 层                 │  │
│  │  SOUL / 记忆 / 面试 / 提醒 / 邮件  │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  编排引擎（B+C核心）               │  │
│  │  安全→SOUL→记忆→路由→模型→安检    │  │
│  └───────────────────────────────────┘  │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│   PostgreSQL 16 + pgvector              │
│  用户 / SOUL / 记忆 / 面试 / 提醒 / 验证码│
└─────────────────────────────────────────┘
```

## 核心数据结构

### SSE 事件（后端→前端流）

```python
SSEEvent:
  type: str    # status / memory_card / text_chunk / action_buttons / error / done
  data: dict
```

| type | 触发时机 | 前端渲染 |
|------|---------|---------|
| `status` | 每个节点开始 | 状态指示器文案更新 |
| `memory_card` | 记忆检索完成 | 卡片弹出（摘要 + 层级标签） |
| `text_chunk` | 模型逐 token 输出 | 追加到当前 Agent 消息 |
| `action_buttons` | 回复完成 | 快捷操作按钮组 |
| `done` | 全部完成 | 关闭流状态 |
| `error` | 任意节点出错 | 错误提示 |

### 用户与 SOUL

```python
User:
  id: UUID
  email: str (unique)
  onboarding_status: str  # none / soul_selected / completed
  created_at: datetime

SoulTemplate:
  id: UUID
  slug: str              # warm_companion, rational_clear, etc.
  name: str
  dimensions: dict
  soul_markdown: str

UserSoul:
  id: UUID
  user_id: UUID
  template_id: UUID
  version_no: int
  soul_markdown: str
  status: str            # active / superseded
```

### 记忆

```python
MemoryItem:
  id: UUID
  user_id: UUID
  layer: str             # priors / co_created / tacit
  memory_type: str       # identity / goal / event / preference / habit / boundary
  summary: str
  content: dict
  source_type: str       # user_input / system_inference / onboarding
  sensitivity: str       # normal / sensitive
  user_confirmed: bool
  is_inference: bool
  status: str            # active / deleted
  embedding: vector(1536)

ForbiddenTopic:
  id: UUID
  user_id: UUID
  topic_summary: str
  original_phrase: str

PendingAnchor:
  id: UUID
  user_id: UUID
  topic_summary: str
  context: str
  status: str            # pending / fulfilled / expired
  expires_at: datetime
```

## API 接口

### 认证

```
POST /api/auth/send-code       # 发送验证码
  → {email}                    # 请求
  ← {success, message}         # 响应

POST /api/auth/verify-code     # 验证码登录/注册
  → {email, code}
  ← {token, is_new_user}
```

### SOUL

```
GET    /api/souls/templates    # 5 种内置模板
POST   /api/souls/recommend    # 偏好测试推荐
POST   /api/souls/preview      # 预览 2-3 轮对话
POST   /api/users/me/soul      # 确认选择 SOUL
```

### 对话

```
POST /api/chat/send            # 发送消息（SSE 流式）
  → {message, conversation_id}
  ← SSE: status → memory_card → text_chunk... → action_buttons → done

GET  /api/chat/history         # 最近 50 条历史
```

### 记忆

```
GET    /api/memories                    # 三层 + 禁区 + 锚点
PUT    /api/memories/{id}               # 编辑
DELETE /api/memories/{id}               # 删除
POST   /api/memories/forbidden          # 添加禁区
DELETE /api/memories/forbidden/{id}     # 解除禁区
POST   /api/memories/anchor/{id}/fulfill # 锚点完成
```

### 面试

```
POST /api/interview/start               # 开始面试
POST /api/interview/{id}/answer         # 回答问题
GET  /api/interview/{id}/report         # 获取报告
```

### 提醒

```
POST   /api/reminders                   # 创建
GET    /api/reminders                   # 列表
DELETE /api/reminders/{id}              # 删除
```

## 编排引擎（B+C 核心）

一条消息的 9 步生命周期：

```
用户消息
  │ Step 1: 安全检查 → SSE status
  │ Step 2: 加载 SOUL → SSE status
  │ Step 3: 读取记忆 → SSE memory_card
  │ Step 4: 路由意图 → SSE status
  │ Step 5: 模型生成 → SSE text_chunk (逐 token)
  │ Step 6: 输出安全检查
  │ Step 7: 异步后处理（不阻塞）
  │ Step 8: 快捷按钮 → SSE action_buttons
  │ Step 9: 结束 → SSE done
  ▼
用户看到完整回复
```

v1 采用**函数链式调用**（非 LangGraph 框架），每条消息独立编排，不需要 checkpoint/interrupt。v1.1 加 Hermes 时再切到 LangGraph。

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| SSE 事件类型 | 6 种 | 类型少、协议简单，前端按 type 分发 |
| 编排引擎 | 函数链式调用 | v1 不需要 checkpoint/interrupt |
| 记忆检索 | pgvector HNSW (cosine) | 和 PostgreSQL 同一数据库 |
| 记忆写入 | 对话结束后异步批处理 | 不阻塞用户 |
| 模型调用 | DeepSeek v4 Flash | v1 单一模型，Gateway 预留拓展 |
| 验证码存储 | PostgreSQL 临时表 | 无需 Redis，v1 精简 |
| 前端状态管理 | Pinia | 轻量、Vue 3 原生 |
| 前端路由 | 无（Tab 切换） | 4 个 Tab，不需要 vue-router |
| 样式方案 | Tailwind CSS | 响应式 utility-first |
| SSE 前端处理 | fetch + ReadableStream | EventSource 不支持 POST |

## 文件组织

```
comate-agent/
├── docs/
│   ├── spec.md
│   ├── plan.md
│   ├── task.md
│   └── checklist.md
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── settings.py
│   │   │   └── model.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── chat.py
│   │   │   ├── souls.py
│   │   │   ├── memories.py
│   │   │   ├── interview.py
│   │   │   └── reminders.py
│   │   ├── graph/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   ├── state.py
│   │   │   ├── schemas.py
│   │   │   └── nodes/
│   │   │       ├── __init__.py
│   │   │       ├── safety.py
│   │   │       ├── soul_loader.py
│   │   │       ├── memory.py
│   │   │       ├── router.py
│   │   │       ├── llm_call.py
│   │   │       ├── postprocess.py
│   │   │       └── actions.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── soul_service.py
│   │   │   ├── memory_service.py
│   │   │   ├── interview_engine.py
│   │   │   ├── reminder_service.py
│   │   │   ├── email_service.py
│   │   │   └── model_gateway.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── soul.py
│   │   │   ├── memory.py
│   │   │   ├── interview.py
│   │   │   ├── reminder.py
│   │   │   ├── verification_code.py
│   │   │   ├── pending_anchor.py
│   │   │   └── forbidden_topic.py
│   │   └── db/
│   │       ├── __init__.py
│   │       └── session.py
│   ├── config/
│   │   ├── config.yaml
│   │   └── .env.example
│   ├── souls/
│   │   ├── warm_companion.md
│   │   ├── rational_clear.md
│   │   ├── direct_coach.md
│   │   ├── energetic_peer.md
│   │   └── patient_mentor.md
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── api/
│   │   │   ├── auth.js
│   │   │   ├── chat.js
│   │   │   ├── souls.js
│   │   │   ├── memories.js
│   │   │   ├── interview.js
│   │   │   └── reminders.js
│   │   ├── components/
│   │   │   ├── HeaderBar.vue
│   │   │   ├── MessageBubble.vue
│   │   │   ├── MemoryCard.vue
│   │   │   ├── ActionButtons.vue
│   │   │   ├── InputBar.vue
│   │   │   ├── StatusIndicator.vue
│   │   │   └── TabBar.vue
│   │   ├── pages/
│   │   │   ├── ChatPage.vue
│   │   │   ├── MemoryPage.vue
│   │   │   ├── InterviewPage.vue
│   │   │   └── SettingsPage.vue
│   │   ├── stores/
│   │   │   ├── chat.js
│   │   │   ├── user.js
│   │   │   └── memory.js
│   │   └── styles/
│   │       └── main.css
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```
