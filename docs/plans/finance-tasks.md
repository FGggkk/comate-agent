# 记账模块 — 执行任务（确认版）

## P0 — 基础框架

### 0.1 数据库模型
- 新建 `backend/app/models/finance.py`
- `FinanceRecord` 表：id(UUID), user_id(FK→users), type(VARCHAR), category(VARCHAR), amount(BIGINT 单位:分), note(TEXT), record_date(DATE), source(VARCHAR 默认'manual'), created_at, updated_at
- `FinanceMessage` 表：id(UUID), user_id(FK), role(VARCHAR user/assistant), content(TEXT), record_id(UUID 可空→关联已确认的记账), created_at
- 迁移 SQL 添加到 `backend/app/db/session.py`

### 0.2 后端 API
- 新建 `backend/app/api/finance.py`，前缀 `/api/finance`
- `POST /record` — 新增一笔
- `GET /records?year=&month=` — 按月查询
- `PUT /record/:id` — 修改
- `DELETE /record/:id` — 删除
- `GET /summary?year=&month=` — 月度汇总
- `POST /ai-parse` — AI解析自然语言
- `GET /messages` — 获取会话历史
- `POST /messages` — 保存会话消息
- 新建 `backend/app/services/finance_service.py`

### 0.3 前端 FinancePage.vue
- 新建 `frontend/src/pages/FinancePage.vue`
- 双标签切换：💬会话 / 📊账单
- 顶部返回工作台按钮（复用 .back-bar）
- 标签滑动指示器

### 0.4 工作台入口
- 更新 `frontend/src/pages/WorkbenchPage.vue` 添加入口

### 0.5 前端 API 封装
- `frontend/src/api/index.js` 新增 apiFinanceXXX

## P1 — 账单标签（📊）

### 1.1 月度概览卡片
- 大号结余数字（等宽字体）
- 收入/支出对比双色条
- 环比箭头

### 1.2 收支列表
- 按日期分组
- 每条：图标 + 分类 + 备注(小字) + 金额(收入绿/支出橙)
- 编辑：点击 `⋯` → 弹出操作菜单（编辑/删除）
- 编辑 → 弹出修改面板

### 1.3 分类统计
- 8个分类彩色圆角进度条 + 占比 + 金额

### 1.4 「记一笔」底部面板
- spring 弹性弹出 + 背景遮罩
- 金额输入（大号数字键盘）
- 收支切换（支出/收入）
- 分类横向滚动
- 备注输入
- 保存 → 面板关闭，列表淡入新记录

## P2 — 会话标签（💬）

### 2.1 AI 对话界面
- 消息气泡（用户/AI）
- 消息持久化存数据库，刷新不丢失

### 2.2 确认卡片
- AI 识别结果：分类图标 + 分类名 + 金额 + 备注
- 三按钮：确认 / 修改 / 取消
- 确认 → 写入数据库 + 记录关联 + 卡片打勾
- 修改 → 弹出编辑面板
- 取消 → 卡片消失

### 2.3 AI 解析
- `POST /api/finance/ai-parse`
- 调用 DeepSeek 提取金额/分类/收支类型
- 返回结构化结果

### 2.4 数据同步
- 会话确认 → 账单列表自动出现
- 账单编辑/删除 → 会话消息状态同步更新

## P3 — 交互打磨
- spring 弹出动画 / fade-in & slide-down 新增 / slide-out 删除
- 数字滚动动画 / 毛玻璃卡片 / 渐变进度条
