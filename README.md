# 伴行agent — AI Emotional Companion

> 长期记忆驱动的场景化 AI 陪伴伙伴  
> 用户选择 SOUL → 长期记忆 → 真实场景 → 自主学习

---

## 📋 项目概述

伴行agent 是一款以 **SOUL 人格系统** 和 **三层记忆架构** 为核心的 AI 陪伴应用。用户首次使用时选择或自定义伙伴风格（SOUL），之后该风格作为长期身份基线。伴行agent 会在用户授权范围内持续记住用户的目标、经历和偏好，让记忆真正影响下一次交流。

### 核心亮点

- **SOUL 人格系统** — 5 种内置模板 + 偏好推荐，用户选择自己的陪伴风格
- **三层记忆架构** — 先验层 / 共建层 / 默契层，结合禁区锚点与未完待续锚点
- **动态场景引擎** — 连续面试训练（首发场景），基于 SOUL + 记忆 + 历史动态生成
- **B+C 消息流** — 后端多步骤编排（安全→SOUL→记忆→路由→模型→后处理），前端逐帧渲染
- **坏消息五幕剧** — 通知 → 共情 → 解释 → 行动 → 闭环，有温度的挫折场景
- **亲密度成长体系** — 关系可感知、可预期、有激励

## 🧱 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 前端 | Vue 3 + Vite + Tailwind CSS | 对话、场景、记忆管理等 UI |
| 后端 | FastAPI + Python 3.12+ | REST API + SSE 流式响应 |
| 数据库 | PostgreSQL 16 + pgvector | 关系型存储 + 向量检索 |
| 模型 | DeepSeek v4 Flash | 对话生成、场景评估 |
| 编排 | LangGraph 风格函数链 | B+C 多步骤消息编排 |
| 包管理 | uv（后端）/ npm（前端） | 依赖管理 |

## 🚀 快速启动

### 前置条件

- Python 3.12+
- Node.js 20+ / npm
- PostgreSQL 16 + pgvector（可选，v1 可用关键词搜索代替向量检索）

### 1. 克隆项目

```bash
git clone <repo-url>
cd comate-agent
```

### 2. 配置环境变量

```bash
cp backend/config/.env.example backend/config/.env
```

编辑 `.env`，填入以下配置：

```env
# DeepSeek API
DEEPSEEK_API_KEY=sk-your-key

# 邮箱 SMTP（用于验证码注册）
EMAIL_USER=your-email@qq.com
EMAIL_PASS=your-smtp-authorization-code

# JWT 密钥（任意随机字符串）
JWT_SECRET=your-random-secret
```

### 3. 启动数据库

确保 PostgreSQL 服务运行，然后创建数据库和表：

```bash
# 建库
psql -U postgres -c "CREATE DATABASE comate;"

# 建表
psql -U postgres -d comate -f backend/scripts/init.sql
```

### 4. 启动后端

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 6. 打开浏览器

访问 `http://localhost:5173`

## 📁 项目结构

```
comate-agent/
├── docs/
│   └── v1/                          # 设计文档（Spec / Plan / Task / Checklist）
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口
│   │   ├── api/                     # REST + SSE 路由
│   │   │   ├── auth.py              # 注册 / 登录
│   │   │   ├── chat.py              # 对话 SSE 流
│   │   │   ├── souls.py             # SOUL 模板 / 选择
│   │   │   ├── memories.py          # 记忆 CRUD
│   │   │   ├── interview.py         # 面试场景
│   │   │   └── reminders.py         # 提醒
│   │   ├── graph/                   # B+C 编排引擎
│   │   │   ├── engine.py            # 9 步流水线
│   │   │   ├── state.py             # 对话状态
│   │   │   ├── schemas.py           # SSE 事件格式
│   │   │   └── nodes/               # 8 个处理节点
│   │   ├── services/                # 业务服务层
│   │   │   ├── auth_service.py      # 认证
│   │   │   ├── soul_service.py      # SOUL 管理
│   │   │   ├── memory_service.py    # 三层记忆
│   │   │   ├── interview_engine.py  # 面试状态机
│   │   │   ├── model_gateway.py     # LLM 网关
│   │   │   ├── email_service.py     # 邮件发送
│   │   │   └── reminder_service.py  # 提醒
│   │   └── models/                  # SQLAlchemy 模型（8 张表）
│   ├── souls/                       # 5 种内置 SOUL.md
│   ├── config/                      # 配置文件
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── api/                     # 后端接口客户端
│       ├── components/              # 通用组件
│       │   ├── LoginForm.vue        # 登录 / 注册
│       │   ├── MessageBubble.vue    # 消息气泡
│       │   ├── MemoryCard.vue       # 记忆卡片
│       │   ├── ActionButtons.vue    # 快捷操作
│       │   ├── InputBar.vue         # 输入框
│       │   ├── StatusIndicator.vue  # 状态指示
│       │   ├── TabBar.vue           # 底部导航
│       │   └── QuickBar.vue         # 快捷栏
│       ├── pages/                   # 页面
│       │   ├── ChatPage.vue         # 对话
│       │   ├── MemoryPage.vue       # 记忆管理
│       │   ├── InterviewPage.vue    # 面试训练
│       │   └── SettingsPage.vue     # 设置
│       └── stores/                  # Pinia 状态
└── docker-compose.yml               # PostgreSQL 容器
```

## 🎯 核心功能

### SOUL 选择

用户首次进入时从 5 种内置 SOUL 中选择：
- 温柔陪伴型 · 理性清醒型 · 直率督促型 · 活力同伴型 · 耐心导师型

支持偏好测试推荐（5 题）和 2-3 轮预览对话。

### 对话消息流 (B+C)

```
用户发送消息
  → 安全检查        → 前端显示"安全检查中"
  → 加载 SOUL       → 前端显示"加载风格中"
  → 读取记忆        → 前端弹出记忆卡片
  → 意图路由        → 前端显示"日常/面试模式"
  → 模型生成回复     → 前端逐 token 流式显示
  → 输出安全检查
  → 异步后处理       → 抽取记忆候选 / 更新锚点
  → 生成快捷按钮     → 前端显示操作按钮
  → 完成
```

### 三层记忆

| 层级 | 说明 |
|------|------|
| **先验层** | 系统预置信息，不主动在对话中引用 |
| **共建层** | 用户主动告诉或确认的记忆，可查看/编辑/删除 |
| **默契层** | 从交互中自然沉淀的推断，标记来源 |

附加：
- **禁区锚点** — 用户明示"不要提"，Agent 绝不触碰
- **未完待续锚点** — 上次聊一半的事，下次对话主动续上（保质期 3-7 天）

### 连续面试场景

```
基线模拟 → 写入问题 → 第二次针对训练 → 第三次高压模拟 → 面试报告
```

报告含：问题列表 + 回答记录 + 改善趋势

## 📐 设计参考

本项目设计参考自 [Emotional Companion Agent 设计手册](https://jackychen-12.github.io/Emotional-Companion-Agent/) 的 6 章设计原则：

- 三层记忆架构
- 三序取舍原则（用户自主 > 系统建议 > 商业目标）
- 坏消息五幕剧
- 三模态情绪表达
- 关系成长体系
- 禁区锚点与未完待续锚点

## 🗺️ 开发路线

### v1（当前）— 8 周 MVP

- [x] 邮箱验证码注册 / 密码登录
- [x] SOUL 选择系统（5 种模板 + 预览）
- [x] 日常对话（基于 SOUL 人格）
- [x] 三层记忆 + 禁区锚点 + 未完待续锚点
- [x] 连续面试场景（3 轮训练 + 报告）
- [x] 主动提醒
- [x] 响应式 Web UI

### v1.1（规划中）

- [ ] 自定义 SOUL（维度滑块 + SOUL.md 编辑）
- [ ] 成长时间线 / 周报
- [ ] 考研搭子场景
- [ ] 口语社交场景
- [ ] Hermes 离线学习 + Skill 治理
- [ ] pgvector 向量检索

## 🤝 团队协作

### 分支规范

```
main        — 稳定版本
develop     — 日常开发
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
