# 伴行agent — AI Emotional Companion

> 长期记忆驱动的场景化 AI 陪伴伙伴
> 用户选择 SOUL → 长期记忆 → 真实场景 → 自主学习

---

## 📋 项目概述

伴行agent 是一款以 **SOUL 人格系统** 和 **三层记忆架构** 为核心的 AI 陪伴应用。用户首次使用时选择或抽取自己的伙伴人格（SOUL），该人格作为长期身份基线；伴行agent 会在用户授权范围内持续记住用户的目标、经历与偏好，让记忆真正影响下一次交流。

除对话陪伴外，应用内置**工作台**，聚合面试训练、旅游规划、购物计划、记账四个 AI 工具，支持从聊天中快捷跳转。

## ✨ 核心功能

### 对话与人格

| 功能 | 说明 |
|------|------|
| **SOUL 人格系统** | 5 种内置模板 + 5 题偏好推荐 + 预览对话；支持随机抽取（人设球）与风格切换 |
| **人设抽取玩法** | 人设球随机抽取 SOUL，存入库存（`user_soul_inventory`），可随时切换使用 |
| **B+C 消息流** | 后端 9 步流水线（安全→SOUL→记忆→意图路由→工具调用→模型→后处理），前端逐帧渲染 |
| **LLM 工具调用** | function calling：实时时间、联网搜索（Firecrawl）、天气（和风天气） |
| **写作场景** | 创作 / 润色 / 邮件 / 与领导交流 / 朋友圈，多种写作模板 |

### 记忆系统

| 层级 | 说明 |
|------|------|
| **先验层** | 系统预置信息，不主动在对话中引用 |
| **共建层** | 用户主动告知或确认的记忆，可查看/编辑/删除 |
| **默契层** | 从交互中自然沉淀的推断，标记来源 |

附加机制：

- **默契画像（Tacit Profile）** — 独立画像机制：会话总结 → 证据收集 → 画像合并 / 衰减 / 版本快照
- **记忆文档工作区** — USER / MEMORY / BOUNDARY / DELTA 四类 Markdown 文档，可导出到文件、导入、手动编辑
- **禁区锚点** — 用户明示"不要提"的话题，Agent 绝不触碰
- **未完待续锚点** — 上次聊一半的事自动续上（保质期 3-7 天）
- **向量检索就绪** — `memory_items.embedding` 向量字段已建（pgvector），待切换正式向量检索

### 工作台（AI 工具集）

聊天页可一键跳转，工具页支持返回来源（聊天/工作台）感知与状态保持：

| 工具 | 交互 | 能力 |
|------|------|------|
| **面试训练** | 表单 + 问答 | 3 轮递进面试（基线→针对→高压）+ 评估报告 + 思路提示 + 重出题 + 报告导出 |
| **旅游规划** | 需求表单 | AI 生成行程 + 预算校验自动重试 + 单日重生成 + 预算明细 |
| **购物计划** | 对话式 | LLM 拆解需求 → Firecrawl 实时比价 → 多套方案 + SSE 进度 + 历史收藏 |
| **记账** | AI 对话式 | 自然语言记账（"中午吃饭花了32"）→ 确认卡片 → 月度账单 + 分类统计 |

### 基础能力

- 邮箱验证码注册 / 密码登录 / JWT 刷新
- 会话管理（创建 / 重命名 / 删除）+ 消息编辑 / 删除后重新生成回答
- 主动提醒（自然语言时间推断："明早 / 后天 / 半小时后 / 睡前"）
- 头像上传（腾讯云 COS）
- 响应式 Web UI（Vue 3）

## 🧱 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 前端 | Vue 3 + Vite + Pinia | 对话、工作台、记忆管理等 UI |
| 后端 | FastAPI + Python 3.12+ | REST API + SSE 流式响应 |
| 数据库 | PostgreSQL 16 + pgvector | 关系型存储 + 向量字段 |
| 模型 | DeepSeek（兼容 OpenAI SDK） | 对话生成、工具调用、场景评估 |
| 检索 | Firecrawl | 联网搜索、商品比价 |
| 外部服务 | 和风天气 / 腾讯云 COS / QQ 邮箱 SMTP | 天气、头像存储、验证码邮件 |
| 包管理 | uv（后端）/ npm（前端） | 依赖管理 |

## 🚀 快速启动

### 前置条件

- Python 3.12+ / uv
- Node.js 20+ / npm
- PostgreSQL 16 + pgvector

### 1. 克隆项目

```bash
git clone <repo-url>
cd comate-agent
```

### 2. 配置环境变量

```bash
cp backend/config/.env.example backend/config/.env
```

编辑 `.env`，至少填入：

```env
# 数据库（默认连远程实例）
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/comate

# DeepSeek API
DEEPSEEK_API_KEY=sk-your-key

# 邮箱 SMTP（验证码注册）
EMAIL_USER=your-email@qq.com
EMAIL_PASS=your-smtp-authorization-code

# JWT 密钥
JWT_SECRET=your-random-secret
```

### 3. 启动数据库

```bash
# Docker（推荐）
docker compose up -d

# 或手动建库建表
psql -U postgres -c "CREATE DATABASE comate;"
psql -U postgres -d comate -f backend/scripts/init.sql
```

### 4. 启动后端

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

启动时自动执行数据库迁移（`db/session.py` 内置迁移列表）。

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 6. 打开浏览器

访问 `http://localhost:5173`（Vite 已代理 `/api` → `http://localhost:8000`）

## 📁 项目结构

```
comate-agent/
├── docs/
│   ├── v1/                          # v1 设计文档（Spec / Plan / Task / Checklist）
│   ├── plans/                       # 模块设计（记账 / 旅游）
│   └── agents/                      # Agent 技能说明（domain / issue-tracker）
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口（12 个路由注册）
│   │   ├── api/                     # REST + SSE 路由
│   │   │   ├── auth.py              # 注册 / 登录 / 刷新
│   │   │   ├── chat.py              # 对话 SSE 流
│   │   │   ├── souls.py             # SOUL 模板 / 推荐 / 抽取 / 切换
│   │   │   ├── memories.py          # 记忆 CRUD + 文档工作区 + 锚点
│   │   │   ├── interview.py         # 面试场景
│   │   │   ├── reminders.py         # 提醒
│   │   │   ├── user.py              # 资料 / 头像
│   │   │   ├── sessions.py          # 会话管理
│   │   │   ├── messages.py          # 消息编辑 / 删除重答
│   │   │   ├── finance.py           # 记账
│   │   │   ├── travel.py            # 旅游规划
│   │   │   └── shopping.py          # 购物计划
│   │   ├── graph/                   # B+C 编排引擎
│   │   │   ├── engine.py            # 9 步流水线
│   │   │   ├── nodes/               # 安全 / SOUL / 记忆 / 路由 / LLM / 后处理
│   │   │   ├── tools/               # function calling（时间 / 搜索 / 天气）
│   │   │   └── schemas.py           # SSE 事件格式
│   │   ├── services/                # 业务服务层（19 个）
│   │   │   ├── memory_service.py        # 三层记忆
│   │   │   ├── tacit_profile_service.py # 默契画像
│   │   │   ├── memory_document_service.py # 记忆文档
│   │   │   ├── interview_engine.py  # 面试状态机
│   │   │   ├── finance_service.py   # 记账解析
│   │   │   ├── travel_service.py    # 行程生成
│   │   │   ├── shopping_service.py  # 购物比价流水线
│   │   │   ├── model_gateway.py     # LLM 网关
│   │   │   ├── search_service.py    # Firecrawl 搜索
│   │   │   └── ...                  # weather / embedding / cos / email 等
│   │   └── models/                  # SQLAlchemy 模型（23 张表）
│   ├── souls/                       # 5 种内置 SOUL.md
│   ├── config/                      # 配置文件
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── api/                     # 后端接口客户端（401 自动刷新）
│       ├── components/              # 12 个通用组件
│       ├── pages/                   # 9 个页面
│       │   ├── ChatPage.vue         # 对话 + 会话管理 + 写作场景
│       │   ├── MemoryPage.vue       # 三层记忆 + 文档工作区
│       │   ├── InterviewPage.vue    # 面试训练
│       │   ├── WorkbenchPage.vue    # 工作台（四工具聚合 + 状态保持）
│       │   ├── FinancePage.vue      # 记账
│       │   ├── TravelPage.vue       # 旅游规划
│       │   ├── ShoppingPage.vue     # 购物计划
│       │   ├── SettingsPage.vue     # 设置
│       │   └── PersonaPage.vue      # 人设抽取 / 库存 / 切换
│       └── stores/                  # Pinia（user / chat / memory / shopping）
└── docker-compose.yml               # PostgreSQL 容器
```

## 🎯 核心机制详解

### 对话消息流（B+C）

```
用户发送消息
  → 安全检查        → 前端显示"安全检查中"
  → 加载 SOUL       → 前端显示"加载风格中"
  → 读取记忆        → 前端弹出记忆卡片
  → 意图路由        → 前端显示"日常/面试模式"
  → LLM 两轮调用    → 第一轮带 tools 决策执行 → 第二轮流式生成
  → 输出安全检查
  → 异步后处理       → 抽取记忆候选 / 更新锚点 / 调度默契画像刷新
  → 生成快捷按钮     → 前端显示操作按钮
  → 完成
```

### 连续面试场景

```
基线模拟 → 写入问题 → 第二次针对训练 → 第三次高压模拟 → 面试报告
```

报告含：问题列表 + 回答记录 + 改善趋势；支持答题思路提示与重出题。

### 购物比价流水线

```
对话确认需求 → LLM 拆解商品清单 → Firecrawl 逐项实时搜索 → LLM 生成 2-3 套方案 → SSE 推送进度
```

## 📐 设计参考

本项目设计参考自 [Emotional Companion Agent 设计手册](https://jackychen-12.github.io/Emotional-Companion-Agent/) 的设计原则：

- 三层记忆架构
- 三序取舍原则（用户自主 > 系统建议 > 商业目标）
- 坏消息五幕剧
- 三模态情绪表达
- 关系成长体系
- 禁区锚点与未完待续锚点

## 🗺️ 开发路线

### v1（当前基线）— 已完成

- [x] 邮箱验证码注册 / 密码登录 / JWT 刷新
- [x] SOUL 人格系统（5 模板 + 推荐 + 预览 + 随机抽取 + 库存切换）
- [x] 日常对话（B+C 九步流水线 + 工具调用 + 写作场景）
- [x] 三层记忆 + 禁区锚点 + 未完待续锚点 + 默契画像 + 记忆文档工作区
- [x] 工作台：面试训练 / 旅游规划 / 购物计划 / 记账
- [x] 主动提醒（自然语言时间推断）
- [x] 会话 / 消息管理（编辑重答、重命名、删除）
- [x] 响应式 Web UI

### v1.1 — 体验打磨与工程加固（建议下一个版本）

- [ ] 购物/记账/旅游交互范式统一（当前购物与记账为对话式、旅游为表单式）
- [ ] 购物进度存储从进程内存迁移 Redis，`favorited` 字段类型修正（Text→Boolean）
- [ ] `models/__init__.py` 补全导出（MemoryObservation / ShoppingPlan）
- [ ] 面试 `reroll` 复用公开接口，移除对私有函数 `_generate_question` 的直接引用
- [ ] 记忆文档编辑器 Markdown 实时预览
- [ ] 加载态 / 骨架屏 / 错误态全局统一

### v1.2 — 个人化深化

- [ ] 自定义 SOUL（维度滑块 + SOUL.md 编辑）
- [ ] 成长时间线 / 每周回忆报告
- [ ] 亲密值体系可视化（基于默契画像数据）
- [ ] 新场景：考研搭子、口语社交

### v1.3 — 多模态与智能体能力

- [ ] 语音输入 / 输出（Web Speech API / TTS）
- [ ] 图片理解（多模态模型）
- [ ] 正式启用 pgvector 向量检索（embedding 字段已就绪）
- [ ] 定时任务（记忆衰减 / 画像刷新 / 提醒触发，当前依赖请求触发）

### v1.4 — 分享与导出

- [ ] 面试报告 / 旅行方案导出 PDF
- [ ] 购物清单、旅行行程分享链接
- [ ] 记账月度账单导出

### v2.0 — 规模化

- [ ] 异步任务队列（Celery）+ Redis 缓存
- [ ] 完整 Docker Compose（前后端 + 数据库 + Redis）+ CI/CD
- [ ] 监控 / 日志 / 告警
- [ ] 多设备登录与数据同步

## 🤝 团队协作

### 分支规范

```
main        — 稳定版本（PR 合入）
dev         — 日常开发
feat/*      — 功能分支
fix/*       — 修复分支
```

### 提交信息格式

```
<type>(<scope>): <description>

feat(chat): 添加 SSE 流式消息渲染
fix(auth): 修复验证码过期时间计算
refactor(memory): 重构三层记忆检索
```

## 📄 许可证

MIT
