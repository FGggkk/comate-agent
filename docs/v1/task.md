# 伴行agent v1 — Tasks

> 共 18 个任务，按依赖顺序执行。每个任务 2-5 分钟。

## 执行顺序

```
T1 → T2 → T3 → T4
                  ↓
           T5 → T6 → T7
                  ↓    ↓
                 T8  ←─┘
                  ↓
                 T9
                  ↓
        ┌────────┼────────┐
        ↓        ↓        ↓
       T10      T11      T12
                          ↓
                        T13
                          ↓
                  ┌───────┘
                  ↓
            T14 → T15 → T16
                          ↓
                        T17
                          ↓
                        T18
```

---

## T1: 项目脚手架

**文件：** `docker-compose.yml`, `backend/`, `frontend/` 目录
**依赖：** 无
**步骤：**
1. 创建 `comate-agent/` 根目录
2. 编写 `docker-compose.yml`（PostgreSQL 16 + pgvector 镜像）
3. 创建 `backend/` 目录结构（app/api/, app/graph/, app/services/, app/models/, app/db/, config/）
4. 编写 `backend/requirements.txt`（FastAPI, uvicorn, sqlalchemy, asyncpg, pgvector, pydantic, httpx, python-multipart, alembic, pyyaml, python-jose, aiosmtplib）
5. 编写 `frontend/package.json`（vue 3, vite, tailwindcss, pinia, autoprefixer, postcss）
6. 编写 `frontend/vite.config.js`（dev 代理 /api → 后端）
7. 编写 `frontend/tailwind.config.js` + `frontend/postcss.config.js`
8. 编写 `frontend/index.html`
9. 编写 `backend/app/__init__.py`, `backend/app/main.py`（FastAPI 空骨架 + CORS）

**验证：** `docker compose up -d` PostgreSQL 启动；后端 `uvicorn app.main:app` 启动无报错；前端 `npm run dev` 白页

---

## T2: 配置加载

**文件：** `backend/app/config/__init__.py`, `backend/app/config/settings.py`, `backend/app/config/model.py`, `backend/config/config.yaml`, `backend/config/.env.example`
**依赖：** T1
**步骤：**
1. 编写 `config.yaml`（数据库、邮箱 SMTP、DeepSeek API Key）
2. 编写 `.env.example`
3. 编写 `settings.py`：Pydantic Settings，读取 yaml + 环境变量覆盖
4. 编写 `model.py`：ModelConfig 数据类，DeepSeek v4 Flash

**验证：** 后端启动打印配置（不暴露密码），确认读取正确

---

## T3: 数据库模型

**文件：** `backend/app/db/session.py`, `backend/app/models/*.py`（8 个文件）
**依赖：** T2
**步骤：**
1. 编写 `session.py`（SQLAlchemy async engine + sessionmaker）
2. 编写 `User` 模型（id, email, onboarding_status, created_at, last_login）
3. 编写 `SoulTemplate` 模型
4. 编写 `UserSoul` 模型
5. 编写 `MemoryItem` 模型（含 embedding: Vector）
6. 编写 `ForbiddenTopic` 模型
7. 编写 `PendingAnchor` 模型
8. 编写 `VerificationCode` 模型
9. 编写 `InterviewSession` + `InterviewQuestion` 模型
10. 编写 `Reminder` 模型
11. 编写各 `__init__.py`

**验证：** 导入 models 包无报错

---

## T4: 邮箱验证码服务

**文件：** `backend/app/services/email_service.py`, `backend/app/services/auth_service.py`, `backend/app/api/auth.py`
**依赖：** T3
**步骤：**
1. 编写 `email_service.py`：通过 SMTP 发送 6 位随机码
2. 编写 `auth_service.py`：验证码写入 DB（5 分钟 TTL）、校验、JWT token
3. 编写 `auth.py` 路由：`POST /api/auth/send-code`, `POST /api/auth/verify-code`

**验证：** 调用 send-code → 邮箱接收验证码 → verify-code → 返回 token

---

## T5: SOUL 系统

**文件：** `backend/app/services/soul_service.py`, `backend/app/api/souls.py`, `backend/souls/*.md`（5 个）
**依赖：** T3
**步骤：**
1. 编写 5 个内置 SOUL.md（温柔陪伴 / 理性清醒 / 直率督促 / 活力同伴 / 耐心导师）
2. 编写 `soul_service.py`：模板列表、偏好规则推荐、预览、确认选择
3. 编写 `souls.py` 路由

**验证：** GET /templates → 5 条；POST /recommend → 2 个推荐；POST /preview → 对话；POST /users/me/soul → 保存

---

## T6: 记忆服务

**文件：** `backend/app/services/memory_service.py`, `backend/app/api/memories.py`
**依赖：** T3
**步骤：**
1. 编写 `memory_service.py`：
   - `search()` — pgvector 混合检索 + 禁区过滤
   - `add()` — 写入 + 向量化
   - `update()` / `delete()`
   - 禁区 CRUD + 锚点 CRUD
   - `extract_candidates()` — 对话后抽取
   - `update_anchors()` — 识别未完待续
2. 编写 `memories.py` 路由

**验证：** 写入 → 搜索召回 → 删除后不再召回

---

## T7: 模型网关

**文件：** `backend/app/services/model_gateway.py`
**依赖：** T2
**步骤：**
1. 编写 `model_gateway.py`：
   - `stream(prompt, system)` → async generator 逐 token
   - `chat(prompt, system)` → 完整文本
   - 错误重试（1 次）+ 超时处理

**验证：** stream("你好") → 逐 token；chat("你好") → 完整文本

---

## T8: 编排引擎（B+C 核心）

**文件：** `backend/app/graph/state.py`, `schemas.py`, `engine.py`, `nodes/*.py`
**依赖：** T6, T7
**步骤：**
1. 编写 `state.py`：ChatState 数据类
2. 编写 `schemas.py`：SSEEvent Pydantic 模型
3. 编写 `nodes/safety.py`：输入安全检查
4. 编写 `nodes/soul_loader.py`：读取用户 SOUL.md
5. 编写 `nodes/memory.py`：检索记忆 + 锚点 → memory_card
6. 编写 `nodes/router.py`：意图路由
7. 编写 `nodes/llm_call.py`：拼 prompt → stream → text_chunk
8. 编写 `nodes/safety_output.py`：输出安全检查
9. 编写 `nodes/postprocess.py`：异步抽取 + 更新锚点
10. 编写 `nodes/actions.py`：生成快捷按钮
11. 编写 `engine.py`：9 步编排主函数

**验证：** POST /api/chat/send → 完整 SSE 事件序列

---

## T9: 对话 API

**文件：** `backend/app/api/chat.py`
**依赖：** T8
**步骤：**
1. 编写 `chat.py`：`POST /api/chat/send` → StreamingResponse(SSE)
2. 编写 `GET /api/chat/history`

**验证：** curl POST SSE 端点，观察事件流

---

## T10: 面试场景

**文件：** `backend/app/services/interview_engine.py`, `backend/app/api/interview.py`
**依赖：** T7
**步骤：**
1. 编写 `interview_engine.py`：start_session, answer_question, generate_report
2. 编写 `interview.py` 路由

**验证：** 3 轮面试走完 → 生成报告

---

## T11: 提醒服务

**文件：** `backend/app/services/reminder_service.py`, `backend/app/api/reminders.py`
**依赖：** T3
**步骤：**
1. 编写 `reminder_service.py`：CRUD + 到期查询
2. 编写 `reminders.py` 路由

**验证：** 创建 → 列表 → 到期返回

---

## T12: 前端基础框架

**文件：** `frontend/src/main.js`, `App.vue`, `styles/main.css`, `stores/user.js`
**依赖：** T1
**步骤：**
1. 编写 `main.js`：Vue app + Pinia + 挂载
2. 编写 `main.css`：Tailwind 指令
3. 编写 `stores/user.js`：token, soul, onboarding 状态
4. 编写 `App.vue`：登录/主界面切换 + TabBar + 页面容器

**验证：** 前端启动，显示登录页

---

## T13: 前端 API 层

**文件：** `frontend/src/api/auth.js`, `chat.js`, `souls.js`, `memories.js`, `interview.js`, `reminders.js`
**依赖：** T12
**步骤：**
1. 编写 6 个 API 模块（fetch + 错误处理）
2. `chat.js` 需实现 `fetch + ReadableStream` 处理 SSE

**验证：** 调用各 API，Network 面板查看请求/响应

---

## T14: 前端登录页 + SOUL 选择

**文件：** `frontend/src/components/LoginForm.vue`, `SoulSelector.vue`, `SoulPreview.vue`, `PreferenceTest.vue`
**依赖：** T13
**步骤：**
1. 编写 `LoginForm.vue`：邮箱 → 验证码 → 登录
2. 编写 `SoulSelector.vue`：5 个模板卡片
3. 编写 `SoulPreview.vue`：预览对话展示
4. 编写 `PreferenceTest.vue`：5 题 → 推荐
5. 编写登录 → 选 SOUL → 进主界面的流程控制

**验证：** 完整注册/登录 → 选 SOUL → 进入对话页

---

## T15: 前端对话页（B+C 核心）

**文件：** `frontend/src/pages/ChatPage.vue`, `components/HeaderBar.vue`, `MessageBubble.vue`, `MemoryCard.vue`, `ActionButtons.vue`, `InputBar.vue`, `StatusIndicator.vue`, `stores/chat.js`
**依赖：** T13
**步骤：**
1. 编写 `stores/chat.js`
2. 编写 `HeaderBar.vue`（角色头像 + 名称 + 等级）
3. 编写 `StatusIndicator.vue`
4. 编写 `MemoryCard.vue`
5. 编写 `MessageBubble.vue`
6. 编写 `ActionButtons.vue`
7. 编写 `InputBar.vue`
8. 编写 `ChatPage.vue`：整合 + SSE 流处理

**验证：** 发消息 → 状态指示 → 记忆卡 → 文字流 → 按钮

---

## T16: 前端记忆页

**文件：** `frontend/src/pages/MemoryPage.vue`, `stores/memory.js`
**依赖：** T13
**步骤：**
1. 编写 `stores/memory.js`
2. 编写 `MemoryPage.vue`：三层展示 + 禁区 + 锚点 + 编辑/删除

**验证：** 三层数据 → 编辑 → 删除 → 禁区管理

---

## T17: 前端面试页 + 设置页

**文件：** `frontend/src/pages/InterviewPage.vue`, `SettingsPage.vue`
**依赖：** T13
**步骤：**
1. 编写 `InterviewPage.vue`：输入简历 → 面试 → 报告
2. 编写 `SettingsPage.vue`：当前 SOUL + 提醒管理

**验证：** 面试全流程可走通

---

## T18: 集成与 Docker 部署

**文件：** `backend/Dockerfile`, `frontend/Dockerfile`
**依赖：** T9, T15
**步骤：**
1. 编写后端 Dockerfile
2. 编写前端 Dockerfile（nginx serve dist/）
3. 更新 `docker-compose.yml`：加 backend + frontend service
4. 整体启动测试

**验证：** `docker compose up` → 全流程可走通
